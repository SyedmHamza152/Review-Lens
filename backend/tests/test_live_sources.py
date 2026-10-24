"""Tests for the live credential-free connectors (mocked HTTP - no network)."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.integrations.base import AdapterStatus
from app.integrations import live_sources as ls
from app.services.pipeline import process_adapter_result


def _arctic_posts(n=3):
    return [
        {"id": f"p{i}", "title": f"AirPods {i}", "selftext": "battery is great" if i else "",
         "author": f"user{i}", "created_utc": 1729000000 + i, "subreddit": "PakGamers",
         "num_comments": 5, "permalink": f"/r/PakGamers/comments/p{i}/x/"}
        for i in range(n)
    ]


def _arctic_comments(n=4):
    return [
        {"id": f"c{i}", "body": f"AirPods {i} battery life is {'great' if i % 2 else 'poor'}",
         "author": f"commenter{i}", "created_utc": 1729000000 + i,
         "subreddit": "pakistan", "link_id": "t3_p0"}
        for i in range(n)
    ]


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_mentions_filter():
    tokens = ls._mention_tokens("AirPods Pro")
    assert tokens == ["airpods"]
    assert ls._mentions("Just got my airpods today!", tokens)
    assert not ls._mentions("I love my pro controller", tokens)
    # generic-only product names require all tokens
    toks = ls._mention_tokens("Pro Max")
    assert ls._mentions("pro max is huge", toks)
    assert not ls._mentions("pro player max level", toks)


def test_reddit_fetch_and_filter_keeps_mentions_only():
    """Fetched-but-unrelated posts must be dropped; mentions kept."""
    unrelated = [{"id": "z1", "title": "Food prices in Lahore", "selftext": "",
                  "author": "a", "created_utc": 1729000000, "subreddit": "pakistan"}]

    def fake_get(self, path, params, retries=2, text_search=False):
        if path == "posts/search" and params.get("subreddit") == "pakistan":
            return _arctic_posts(2) + unrelated
        if path == "posts/search":
            return []
        if path == "comments/search" and "body" not in params:
            return _arctic_comments(2)
        return []  # text-search booster & thread expansion: empty

    with patch.object(ls.ArcticShiftClient, "get", fake_get):
        with patch.object(ls.settings, "REDDIT_SUBREDDITS", "pakistan"):
            res = ls.collect_reddit("AirPods Pro", None, max_items=50)

    assert res.status == AdapterStatus.SUCCESS
    assert res.data_source == "live"
    ids = {i.external_id for i in res.items}
    assert "t3_z1" not in ids, "unrelated post must be filtered out"
    assert any(i.external_id.startswith("t3_p") for i in res.items)
    assert all("airpods" in (i.text or "").lower() for i in res.items)


def test_reddit_throttled_text_search_degrades_gracefully():
    calls = {"n": 0}

    def fake_get(self, path, params, retries=2, text_search=False):
        if text_search:
            calls["n"] += 1
            return None  # simulate 422 throttle
        if path == "posts/search":
            return _arctic_posts(1)
        if path == "comments/search" and "body" not in params:
            return _arctic_comments(1)
        return []

    with patch.object(ls.ArcticShiftClient, "get", fake_get):
        with patch.object(ls.settings, "REDDIT_SUBREDDITS", "pakistan,pakgamers"):
            res = ls.collect_reddit("AirPods Pro", None, max_items=50)

    assert res.status == AdapterStatus.SUCCESS
    assert "rate-limited" in res.message
    assert len(res.items) >= 1


def test_hackernews_parses_comments_and_strips_html():
    story = {"objectID": "42", "title": "AirPods Pro review", "created_at": "2026-10-01T00:00:00Z",
             "author": "hnuser", "story_text": None}
    comment = {"objectID": "c1", "comment_text": "Battery <b>drains</b> fast &amp; case scratches",
               "created_at": "2026-10-02T00:00:00Z", "author": "cuser"}

    def fake_get(url, params=None, timeout=None):
        if "tags=story" in str(params.get("tags", "")) or params.get("tags") == "story":
            return _FakeResponse({"hits": [story]})
        return _FakeResponse({"hits": [comment]})

    with patch.object(ls.requests, "get", fake_get):
        with patch.object(ls.settings, "HN_MAX_STORIES", 2):
            with patch.object(ls.settings, "HN_COMMENTS_PER_STORY", 5):
                res = ls.HackerNewsAdapter().search("AirPods Pro", None, 20)

    assert res.status == AdapterStatus.SUCCESS
    texts = [i.text for i in res.items]
    assert any("Battery drains fast & case scratches" in t for t in texts)
    assert all("<b>" not in t for t in texts)


def test_daraz_catalog_parses_listings():
    payload = {"mods": {"listItems": [
        {"name": "AirPods Pro 2 Clone", "nid": "111", "ratingScore": "4.5", "review": "1,234",
         "priceShow": "Rs. 2,999", "sellerName": "TechPK", "brandName": "Generic",
         "location": "Karachi", "itemUrl": "//www.daraz.pk/products/x-111.html",
         "itemSoldCntShow": "500+ sold"},
        {"name": "", "nid": "222"},  # skipped: no name
    ]}}

    with patch.object(ls.requests, "get", lambda *a, **k: _FakeResponse(payload)):
        listings, err = ls.fetch_daraz_catalog("airpods pro", 40)

    assert err == ""
    assert len(listings) == 1
    l = listings[0]
    assert l["external_id"] == "111"
    assert l["rating"] == 4.5
    assert l["review_count"] == 1234
    assert l["url"] == "https://www.daraz.pk/products/x-111.html"


def test_daraz_catalog_network_error_is_honest():
    with patch.object(ls.requests, "get",
                      lambda *a, **k: (_ for _ in ()).throw(ls.requests.ConnectionError("down"))):
        listings, err = ls.fetch_daraz_catalog("airpods", 40)
    assert listings == [] and "unreachable" in err


def test_aggregate_items_persisted(db):
    """process_adapter_result must store listing aggregates, never sentiment-score them."""
    from app.models import PlatformListing, SearchJob
    job = SearchJob(id="aggtest1", product_name="AirPods Pro", platforms_requested='["daraz"]',
                    status="completed")
    db.add(job)
    db.commit()

    result = AdapterStatus  # noqa: F841  (import guard)
    from app.integrations.base import AdapterResult
    res = AdapterResult("daraz", AdapterStatus.SUCCESS, items=[], data_source="live")
    res.aggregate_items = [{
        "external_id": "999", "name": "AirPods Pro Copy", "rating": 4.2,
        "review_count": 77, "price_text": "Rs. 1,999", "seller": "S", "brand": "B",
        "location": "Lahore", "sold_count_text": "100+ sold", "url": "https://x/",
    }]
    stats = process_adapter_result(db, "aggtest1", res, {"airpods"})
    assert stats["listings_stored"] == 1

    row = db.query(PlatformListing).filter_by(job_id="aggtest1").one()
    assert row.rating == 4.2 and row.review_count == 77
    # re-running must not duplicate (unique constraint respected)
    stats2 = process_adapter_result(db, "aggtest1", res, {"airpods"})
    assert stats2["listings_stored"] == 0


def test_platform_listing_metadata():
    """YouTube-only product decision: only YouTube is registered/exposed."""
    from app.integrations.registry import platform_listing
    listing = platform_listing()
    assert {p["key"] for p in listing} == {"youtube"}
    assert listing[0]["live_capability"] == "live"
    assert listing[0]["status"] == "success"
    assert listing[0]["optional_env"] == []  # live credential-free, nothing to unlock


# ---------------------------------------------------------------- youtube

def test_parse_relative_time():
    from datetime import datetime, timezone
    dt = ls._parse_relative_time("7 months ago (edited)")
    assert dt is not None and dt.tzinfo is not None
    assert (datetime.now(timezone.utc) - dt).days >= 200
    assert ls._parse_relative_time("just now") is None


def _yt_search_payload():
    return {"contents": [{"twoColumnSearchResultsRenderer": {"primaryContents": {
        "sectionListRenderer": {"contents": [{"itemSectionRenderer": {"contents": [
            {"videoRenderer": {
                "videoId": "vid1",
                "title": {"runs": [{"text": "Best cricket bat review 2026"}]},
                "ownerText": {"runs": [{"text": "CricketGear PK"}]},
                "viewCountText": {"simpleText": "12,345 views"},
            }}]}}]}}}}]}


def _yt_next_payload(token="TOK"):
    return {"engagementPanels": [{"engagementPanelSectionListRenderer": {
        "panelIdentifier": "engagement-panel-comments-section",
        "content": {"continuationItemRenderer": {"continuationEndpoint": {
            "continuationCommand": {"token": token}}}}}}]}


def _yt_comments_payload(comments, next_token=None):
    mutations = [{"entityKey": f"comment:{c['id']}", "payload": {"commentEntityPayload": {
        "properties": {"commentId": c["id"], "content": {"content": c["text"]},
                       "publishedTime": c.get("when")},
        "author": {"displayName": c["author"]},
        "toolbar": {"likeCountNotliked": c.get("likes", "")},
    }}} for c in comments]
    out = {"frameworkUpdates": {"entityBatchUpdate": {"mutations": mutations}},
           "onResponseReceivedEndpoints": [{"appendContinuationItemsAction": {
               "continuationItems": [
                   {"commentThreadRenderer": {"comment": {}}},
                   *( [] if not next_token else [{"continuationItemRenderer": {
                       "continuationEndpoint": {"continuationCommand": {
                           "token": next_token}}}}]),
               ]}}]}
    return out


def test_youtube_innertube_collect_parses_real_payloads():
    """Mocked InnerTube payloads must yield real comment items end-to-end."""
    from app.integrations.live_sources import YouTubeInnertubeClient, collect_youtube

    page1 = _yt_comments_payload(
        [{"id": "c1", "text": "This bat has great ping and pickup.", "author": "A",
          "when": "2 months ago", "likes": "12"},
         {"id": "c2", "text": "Handle cracked after two weeks, poor quality.", "author": "B",
          "when": "3 weeks ago", "likes": "3"}],
        next_token="PAGE2")
    page2 = _yt_comments_payload(
        [{"id": "c3", "text": "Worth the price, will order again.", "author": "C",
          "when": "1 day ago", "likes": "1"}])

    client = YouTubeInnertubeClient()
    scripted = {"search": _yt_search_payload(), "next1": _yt_next_payload(),
                "page1": page1, "page2": page2}

    def fake_post(self, url, payload):
        if "/search?" in url:
            return scripted["search"]
        if "videoId" in payload:
            return scripted["next1"]
        return page1 if payload.get("continuation") == "TOK" else page2

    with patch.object(ls.settings, "YOUTUBE_MAX_VIDEOS", 3), \
            patch.object(ls.settings, "YOUTUBE_COMMENTS_PER_VIDEO", 10), \
            patch.object(ls.settings, "INNERTUBE_MIN_INTERVAL_SECONDS", 0.0), \
            patch.object(YouTubeInnertubeClient, "_post", fake_post):
        res = collect_youtube("cricket bat", None, 50)

    assert res.status == AdapterStatus.SUCCESS
    assert res.data_source == "live"
    texts = [i.text for i in res.items]
    assert len(texts) == 3
    assert "This bat has great ping and pickup." in texts
    authors = [i.author for i in res.items]
    assert "A" in authors
    assert res.items[0].external_id.startswith("yt_")
    assert res.items[0].source_url == "https://www.youtube.com/watch?v=vid1"


def test_daraz_review_text_blocked_note_is_honest():
    """HTML (non-JSON) review endpoint responses must produce the honest block note."""
    class _HTMLResponse:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html>error page</html>"

        def json(self):
            raise ValueError("not json")

    listings = [{"external_id": "123", "name": "Bat", "url": "https://x/"}]
    with patch.object(ls.requests, "get", lambda *a, **k: _HTMLResponse()):
        items, note = ls.fetch_daraz_reviews(listings, 50)
    assert items == []
    assert "not accessible" in note and "anti-bot" in note


def test_no_minimum_and_source_videos(db):
    """The 50-comment minimum is REMOVED: every analyzed comment counts toward
    the verdict regardless of sample size, and YouTube source videos (with
    links + per-video counts) are part of the report."""
    from app.models import SearchJob
    from app.services import aggregation

    job = SearchJob(id="nomin", product_name="cricket bat",
                    platforms_requested='["youtube"]', status="completed")
    db.add(job)
    db.commit()

    from app.integrations.base import AdapterResult
    # Only 7 comments - far below the old minimum of 50; must still be analyzed.
    yt_items = [ls.ReviewItem(external_id=f"y{i}", text=f"bat {i} is {'nice' if i % 2 else 'bad'}",
                              source_url="https://www.youtube.com/watch?v=vid1",
                              variant="Best cricket bat review", relevance_hint=0.9)
                for i in range(7)]
    result = AdapterResult("youtube", AdapterStatus.SUCCESS, items=yt_items)
    result.aggregate_items = [{"external_id": "vid1",
                               "name": "Best cricket bat review",
                               "url": "https://www.youtube.com/watch?v=vid1",
                               "seller": "CricketGear PK",
                               "sold_count_text": "12,345 views",
                               "review_count": 7}]
    process_adapter_result(db, "nomin", result, {"bat", "cricket"})

    report = aggregation.analyze(db, "nomin")

    verdict = report["verdict"]
    assert verdict["label"] != "Insufficient Data"
    assert verdict["basis"]["platforms_included"] == ["youtube"]
    assert verdict["basis"]["platforms_excluded"] == []
    assert verdict["basis"]["analyzed_comments_for_verdict"] == 7
    assert report["totals"]["analyzed_for_verdict"] == 7
    assert "min_comments_required" not in report["totals"]
    assert "below_minimum_platforms" not in report

    comp = report["comparison"][0]
    assert comp["platform"] == "youtube"
    assert comp["analysis_processed"] is True
    assert comp["positive_pct"] is not None

    # source videos: metadata + per-video analyzed counts + working link
    vids = report["source_videos"]
    assert len(vids) == 1
    v = vids[0]
    assert v["url"] == "https://www.youtube.com/watch?v=vid1"
    assert v["title"] == "Best cricket bat review"
    assert v["channel"] == "CricketGear PK"
    assert v["comments_analyzed"] == 7
    assert v["comments_collected"] == 7


def test_youtube_collect_carries_video_metadata():
    """Every comment carries the source video URL + title; the result carries
    per-video metadata for the Source videos card."""
    from app.integrations.live_sources import YouTubeInnertubeClient, collect_youtube

    page1 = _yt_comments_payload(
        [{"id": "c1", "text": "Great ping on this bat.", "author": "A",
          "when": "2 months ago", "likes": "12"}])

    client = YouTubeInnertubeClient()

    def fake_post(self, url, payload):
        if "/search?" in url:
            return _yt_search_payload()
        if "videoId" in payload:
            return _yt_next_payload()
        return page1

    with patch.object(ls.settings, "YOUTUBE_MAX_VIDEOS", 3), \
            patch.object(ls.settings, "YOUTUBE_COMMENTS_PER_VIDEO", 10), \
            patch.object(ls.settings, "INNERTUBE_MIN_INTERVAL_SECONDS", 0.0), \
            patch.object(YouTubeInnertubeClient, "_post", fake_post):
        res = collect_youtube("cricket bat", None, 50)

    assert res.status == AdapterStatus.SUCCESS
    assert res.items
    item = res.items[0]
    assert item.source_url == "https://www.youtube.com/watch?v=vid1"
    assert item.variant == "Best cricket bat review 2026"
    assert res.aggregate_items, "video metadata missing"
    meta = res.aggregate_items[0]
    assert meta["external_id"] == "vid1"
    assert meta["name"] == "Best cricket bat review 2026"
    assert meta["url"] == "https://www.youtube.com/watch?v=vid1"
    assert meta["seller"] == "CricketGear PK"
    assert meta["sold_count_text"] == "12,345 views"
    assert meta["review_count"] == len(res.items)
