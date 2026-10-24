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
    from app.integrations.registry import platform_listing
    listing = {p["key"]: p for p in platform_listing()}
    assert listing["reddit"]["live_capability"] == "live"
    assert listing["hackernews"]["live_capability"] == "live"
    assert listing["daraz"]["live_capability"] == "live"
    assert listing["youtube"]["live_capability"] == "requires_credentials"
    assert listing["temu"]["live_capability"] == "not_available"
    assert listing["temu"]["status"] == "unsupported"
    # live sources sort first
    assert platform_listing()[0]["live_capability"] == "live"
