"""Live data sources that work WITHOUT credentials (verified reachable).

Connectivity matrix verified from this deployment (2026-10, curl probes):

| Source              | Endpoint                                        | Result          |
|---------------------|--------------------------------------------------|-----------------|
| Reddit archive      | arctic-shift.photon-reddit.com/api/*             | LIVE (200)      |
| Hacker News         | hn.algolia.com/api/v1/*                          | LIVE (200)      |
| YouTube comments    | www.youtube.com/youtubei/v1 search + next        | LIVE (200)      |
| Daraz PK storefront | www.daraz.pk/catalog/?q=...&ajax=true            | LIVE (200)      |
| Daraz review TEXT   | acs-m.daraz.pk mtop gateway / getReviewList      | IP-blocked (RGV587 cloud_ip_bl) |
| reddit.com JSON     | www.reddit.com/*.json (unauthenticated)          | 403 datacenter  |
| X / eBay            | api.x.com / api.ebay.com                         | reachable, needs key |
| YouTube Data API v3 | googleapis.com (official, when key configured)   | reachable, needs key |
| Daraz Open Platform | open.daraz.com                                   | needs app key   |

Everything collected here comes VERBATIM from the upstream platform APIs.
No synthetic content is produced by this module, ever.

Reddit access rationale: reddit.com blocks datacenter IPs for unauthenticated
JSON, so we use the Arctic-Shift public archive of Reddit submissions and
comments (complete Reddit history, served read-only). When official OAuth
credentials are configured, the Reddit adapter uses the official API instead
(richer ranking, same schema).
"""
from __future__ import annotations

import html
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import requests

from app.core.config import settings
from app.integrations.base import AdapterResult, AdapterStatus, BaseAdapter, ReviewItem

log = logging.getLogger("live_sources")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

REMOVED_BODIES = {"[deleted]", "[removed]", ""}


# ---------------------------------------------------------------- arctic-shift
class ArcticShiftClient:
    """Thin client for the public Arctic-Shift Reddit archive API.

    The archive's server-side text search (body=/title= params) is heavy and
    aggressively rate-limited (HTTP 422 + "Timeout. Maybe slow down a bit")
    under bursts, while plain per-subreddit fetches are cheap and reliable.
    Strategy: fetch recent posts/comments per subreddit (light endpoints) and
    filter for product mentions locally; text search is only an opportunistic
    booster and is disabled for the rest of the job once throttled.
    """

    BASE = "https://arctic-shift.photon-reddit.com/api"

    def __init__(self) -> None:
        self._last_call = 0.0
        self._calls = 0
        self.text_search_available = True  # flips False on first 422 throttle

    def get(self, path: str, params: dict, retries: int = 2,
            text_search: bool = False) -> list | None:
        wait = settings.ARCTIC_MIN_INTERVAL_SECONDS - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        if text_search and not self.text_search_available:
            return None
        backoff = 4.0
        for attempt in range(retries + 1):
            self._calls += 1
            self._last_call = time.time()
            try:
                resp = requests.get(
                    f"{self.BASE}/{path}", params=params,
                    headers={"User-Agent": settings.REDDIT_USER_AGENT},
                    timeout=40,
                )
                if resp.status_code == 422 or (
                    resp.status_code == 200 and "Timeout" in (resp.json() or {}).get("error", "")
                    if resp.headers.get("content-type", "").startswith("application/json")
                    else False
                ):
                    # rate-limited / server-side search timeout
                    if text_search:
                        self.text_search_available = False
                        log.info("arctic text search throttled; falling back to fetch-and-filter")
                        return None
                    if attempt < retries:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    return None
                if resp.status_code != 200:
                    log.warning("arctic %s HTTP %s", path, resp.status_code)
                    return None
                payload = resp.json()
                data = payload.get("data")
                if data is None:
                    err = payload.get("error", "")
                    if err:
                        log.warning("arctic %s error: %s", path, err)
                    return []
                return data
            except requests.RequestException as exc:
                log.warning("arctic %s network error: %s", path, exc)
                if attempt < retries:
                    time.sleep(backoff)
                    backoff *= 2
            except ValueError:  # non-JSON body
                return None
        return None


GENERIC_TOKENS = {"the", "and", "for", "with", "new", "pro", "max", "mini",
                  "plus", "air", "one", "two", "series", "edition", "version"}


def _mention_tokens(product_name: str) -> list[str]:
    """Distinctive lowercase tokens used for local mention filtering."""
    words = re.findall(r"[a-z0-9]{3,}", product_name.lower())
    strong = [w for w in words if w not in GENERIC_TOKENS] or words
    return strong or [product_name.lower()]


def _mentions(text: str, tokens: list[str]) -> bool:
    low = f" {re.sub(r'[^a-z0-9]+', ' ', text.lower())} "
    strong = [t for t in tokens if t not in GENERIC_TOKENS]
    if strong:
        return any(f" {t} " in low for t in strong)
    # generic-only product name (e.g. "Pro Max"): require the full phrase
    return f" {' '.join(tokens)} " in low


def collect_reddit(product_name: str, description: str | None,
                   max_items: int) -> AdapterResult:
    """Collect REAL Reddit posts + comments mentioning the product.

    Primary path: fetch the latest posts and comments of each configured
    subreddit and match product tokens locally - light on the archive API.
    Booster: the archive's server-side text search (when not throttled) and
    comment-thread expansion for matched posts.
    """
    client = ArcticShiftClient()
    after = (datetime.now(timezone.utc) - timedelta(days=settings.REDDIT_LOOKBACK_DAYS)) \
        .strftime("%Y-%m-%d")
    subreddits = [s.strip() for s in settings.REDDIT_SUBREDDITS.split(",") if s.strip()]
    tokens = _mention_tokens(product_name)
    if not (product_name or "").strip():
        return AdapterResult("reddit", AdapterStatus.NO_RESULTS, "Empty product name.")

    items: list[ReviewItem] = []
    seen_ids: set[str] = set()
    matched_post_ids: list[str] = []

    def add(kind: str, d: dict, require_mention: bool = False) -> bool:
        ext = f"{kind}_{d.get('id', '')}"
        if ext in seen_ids:
            return False
        body = (d.get("body") or "").strip()
        title = (d.get("title") or "").strip()
        selftext = (d.get("selftext") or "").strip()
        # drop removal markers so 'SCAM ALERT [removed]' doesn't pollute text
        for marker in ("[removed]", "[deleted]"):
            body = body.replace(marker, "").strip()
            selftext = selftext.replace(marker, "").strip()
        text = " ".join(filter(None, [title, body, selftext])).strip()
        if text.lower() in REMOVED_BODIES or len(text) < 15:
            return False
        if (d.get("author") or "").lower().endswith("bot"):
            return False
        is_mention = _mentions(text, tokens)
        if require_mention and not is_mention:
            return False
        seen_ids.add(ext)
        link_id = (d.get("link_id") or "").replace("t3_", "")
        if kind == "t3" and is_mention:
            matched_post_ids.append(d.get("id", ""))
        permalink = d.get("permalink") or (
            f"/r/{d.get('subreddit', 'unknown')}/comments/{link_id}/_/{d.get('id', '')}/"
            if kind == "t1" else ""
        )
        created = d.get("created_utc")
        items.append(ReviewItem(
            external_id=ext,
            text=text[:1500],
            rating=None,
            review_date=datetime.fromtimestamp(created, tz=timezone.utc) if created else None,
            author=d.get("author"),
            source_url=f"https://www.reddit.com{permalink}" if permalink else None,
        ))
        return is_mention

    # ---- 1) light fetch-and-filter per subreddit (always runs) ----
    for sub in subreddits:
        if len(items) >= max_items:
            break
        data = client.get("posts/search", {
            "subreddit": sub, "limit": 100, "sort": "desc", "after": after})
        for d in (data or []):
            add("t3", d, require_mention=True)   # keep product mentions only
    for sub in subreddits:
        if len(items) >= max_items:
            break
        data = client.get("comments/search", {
            "subreddit": sub, "limit": 100, "sort": "desc", "after": after})
        for d in (data or []):
            add("t1", d, require_mention=True)   # keep product mentions only

    mentions_found = len(items)

    # ---- 2) opportunistic text-search booster (skipped when throttled) ----
    booster_note = ""
    if client.text_search_available and mentions_found < max_items:
        for sub in subreddits[:6]:
            data = client.get("comments/search", {
                "subreddit": sub, "body": product_name,
                "limit": 50, "sort": "desc", "after": after}, text_search=True)
            if data is None:  # throttled -> disabled for the rest of the job
                booster_note = " (archive text-search rate-limited; used recent-window fetch)"
                break
            for d in data:
                add("t1", d, require_mention=True)

    # ---- 3) expand matched posts' comment threads (light endpoint) ----
    # Thread comments are not pre-filtered: the pipeline's relevance scorer
    # decides what belongs to the product.
    for pid in matched_post_ids[:3]:
        if len(items) >= max_items:
            break
        data = client.get("comments/search", {"link_id": pid, "limit": 50, "sort": "asc"})
        for d in (data or []):
            add("t1", d)

    status = AdapterStatus.SUCCESS if items else AdapterStatus.NO_RESULTS
    msg = (f"Collected {len(items)} real Reddit item(s) mentioning '{product_name}' "
           f"via the public Arctic-Shift archive (recent window across "
           f"r/{', r/'.join(subreddits[:6])}"
           f"{'…' if len(subreddits) > 6 else ''}, lookback {settings.REDDIT_LOOKBACK_DAYS}d)"
           f"{booster_note}.")
    return AdapterResult("reddit", status, msg, items=items[:max_items], data_source="live")


def _clean_comment_body(body: str | None) -> str:
    """HN comments carry HTML fragments; Reddit bodies are plain text."""
    if not body:
        return ""
    text = html.unescape(body)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- hacker news
class HackerNewsAdapter(BaseAdapter):
    """Hacker News discussions via the public Algolia search API (no auth)."""

    key = "hackernews"
    name = "Hacker News"
    type = "social"
    access_mode = "Public HN Algolia search API - no credentials required"
    required_env: list[str] = []
    docs_url = "https://hn.algolia.com/api"
    live_capability = "live"
    notes = ("Tech-product discussions and comments. Full-text search over stories "
             "and comment threads; strongest for electronics/software products.")

    BASE = "https://hn.algolia.com/api/v1"

    def search(self, product_name: str, description: str | None,
               max_items: int) -> AdapterResult:
        phrase = (product_name or "").strip()
        if not phrase:
            return AdapterResult(self.key, AdapterStatus.NO_RESULTS, "Empty product name.")
        try:
            stories = requests.get(
                f"{self.BASE}/search",
                params={"query": phrase, "tags": "story",
                        "hitsPerPage": settings.HN_MAX_STORIES},
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
            )
            stories.raise_for_status()
        except requests.RequestException as exc:
            return AdapterResult(self.key, AdapterStatus.BLOCKED,
                                 f"HN Algolia unreachable: {exc}"[:300])

        items: list[ReviewItem] = []
        seen: set[str] = set()

        def add(ext: str, text: str, created: str | None, author: str | None, url: str | None):
            text = _clean_comment_body(text)
            if ext in seen or len(text) < 15:
                return
            seen.add(ext)
            dt = None
            if created:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            items.append(ReviewItem(
                external_id=ext, text=text[:1500], rating=None,
                review_date=dt, author=author, source_url=url,
            ))

        for hit in stories.json().get("hits", []):
            sid = hit.get("objectID", "")
            title = hit.get("title") or ""
            story_text = hit.get("story_text") or ""
            add(f"story_{sid}", f"{title}. {story_text}",
                hit.get("created_at"), hit.get("author"),
                f"https://news.ycombinator.com/item?id={sid}")
            if len(items) >= max_items:
                break
            try:
                comments = requests.get(
                    f"{self.BASE}/search",
                    params={"tags": f"comment,story_{sid}",
                            "hitsPerPage": settings.HN_COMMENTS_PER_STORY},
                    timeout=settings.REQUEST_TIMEOUT_SECONDS,
                )
                comments.raise_for_status()
            except requests.RequestException:
                continue
            for c in comments.json().get("hits", []):
                add(f"c_{c.get('objectID', '')}", c.get("comment_text") or "",
                    c.get("created_at"), c.get("author"),
                    f"https://news.ycombinator.com/item?id={c.get('objectID', '')}")
                if len(items) >= max_items:
                    break

        status = AdapterStatus.SUCCESS if items else AdapterStatus.NO_RESULTS
        msg = (f"Collected {len(items)} real Hacker News story/comment item(s) via the "
               f"public Algolia API for '{phrase}'.")
        return AdapterResult(self.key, status, msg, items=items[:max_items], data_source="live")


# ---------------------------------------------------------------- daraz catalog
DARAZ_UA_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.daraz.pk/",
    "Origin": "https://www.daraz.pk",
}


def fetch_daraz_catalog(product_name: str, max_items: int) -> tuple[list[dict], str]:
    """Query the public Daraz PK storefront catalog JSON.

    Returns (listings, error). Each listing: external_id, name, rating,
    review_count, price_text, seller, location, brand, url. These are REAL
    aggregates Daraz serves for its own search UI; review TEXT is not part of
    this endpoint (needs the Daraz Open Platform API).
    """
    try:
        resp = requests.get(
            "https://www.daraz.pk/catalog/",
            params={"q": product_name, "ajax": "true"},
            headers=DARAZ_UA_HEADERS,
            timeout=settings.REQUEST_TIMEOUT_SECONDS + 8,
        )
        if resp.status_code != 200:
            return [], f"Daraz catalog HTTP {resp.status_code}"
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        return [], f"Daraz catalog unreachable: {exc}"[:200]

    listings: list[dict] = []
    for it in (payload.get("mods", {}) or {}).get("listItems", [])[:max_items]:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        try:
            rating = float(it.get("ratingScore")) if it.get("ratingScore") not in (None, "", 0) else None
        except (TypeError, ValueError):
            rating = None
        try:
            review_count = int(str(it.get("review", "0")).replace(",", "")) if it.get("review") else 0
        except (TypeError, ValueError):
            review_count = 0
        price_parts = [p for p in (it.get("priceShow"), it.get("currencyCode") or "PKR") if p]
        listings.append({
            "external_id": str(it.get("nid") or it.get("itemId") or name)[:240],
            "name": name[:280],
            "rating": rating,
            "review_count": review_count,
            "price_text": " ".join(str(p) for p in price_parts)[:120] or None,
            "seller": (it.get("sellerName") or None),
            "location": it.get("location"),
            "brand": it.get("brandName") or None,
            "url": ("https:" + it["itemUrl"] if str(it.get("itemUrl", "")).startswith("//")
                    else it.get("itemUrl")),
            "sold_count_text": it.get("itemSoldCntShow"),
        })
    return listings, ""


def collect_daraz_catalog(product_name: str, max_items: int) -> tuple[list[dict], str]:
    return fetch_daraz_catalog(product_name, max_items)


def fetch_daraz_reviews(listings: list[dict], max_items: int) -> tuple[list[ReviewItem], str]:
    """Attempt REAL written reviews for Daraz listings via the PDP review API.

    Verified deployment reality: the storefront review endpoint
    (`/pdp/review/getReviewList`) currently routes to the SPA error page and
    the mtop gateway (`acs-m.daraz.pk`) answers RGV587_ERROR (cloud_ip_bl =
    datacenter IP blocklist), so text reviews are NOT obtainable from this
    deployment without Daraz Open Platform credentials. The attempt is kept
    so access resumes automatically if Daraz changes this - and the honest
    note travels back to the adapter either way.
    """
    if not listings:
        return [], "no catalog listings to look up"
    note = ""
    items: list[ReviewItem] = []
    probe = listings[:3]
    for l in probe:
        item_id = str(l.get("external_id") or "")
        if not item_id.isdigit():
            continue
        try:
            resp = requests.get(
                "https://www.daraz.pk/pdp/review/getReviewList/",
                params={"itemId": item_id, "pageSize": 20, "filter": 0,
                        "sort": 0, "pageNo": 1},
                headers=DARAZ_UA_HEADERS,
                timeout=settings.REQUEST_TIMEOUT_SECONDS + 8,
            )
            ctype = resp.headers.get("content-type", "")
            if resp.status_code != 200 or "json" not in ctype:
                note = ("Daraz written review text is not accessible from this "
                        "deployment: the storefront review API is protected by "
                        "Alibaba anti-bot (datacenter IP blocklist) and the review "
                        "endpoint returns an error page instead of review data.")
                break
            payload = resp.json()
            model = payload.get("model") or {}
            for r in model.get("items") or []:
                text = str(r.get("reviewContent") or "").strip()
                if not text:
                    continue
                when = None
                raw_time = r.get("reviewTime")
                if raw_time:
                    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d-%m-%Y"):
                        try:
                            when = datetime.strptime(str(raw_time)[:16], fmt)
                            break
                        except ValueError:
                            continue
                items.append(ReviewItem(
                    external_id=f"daz_{r.get('reviewId', len(items))}",
                    text=text[:1500],
                    rating=r.get("ratingStar"),
                    review_date=when,
                    author=r.get("buyerName"),
                    variant=str(r.get("skuInfo"))[:160] if r.get("skuInfo") else None,
                    source_url=l.get("url"),
                    relevance_hint=0.85,  # product-page reviews are product-scoped
                ))
                if len(items) >= max_items:
                    break
            if items:
                note = ""
                break
        except (requests.RequestException, ValueError) as exc:
            note = f"Daraz review endpoint unreachable: {exc}"[:200]
            break
    return items[:max_items], note


# ---------------------------------------------------------------- youtube innertube
# The public YouTube web client API (InnerTube) is the same endpoint every
# YouTube browser session uses (search + comments); it requires no user
# credentials and returns REAL comments verbatim. When YOUTUBE_API_KEY is
# configured, the official YouTube Data API v3 is used instead (YouTubeAdapter).
_INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"  # public web-client key
_INNERTUBE_CTX = {"client": {"clientName": "WEB", "clientVersion": "2.20241001.00.00",
                             "hl": "en", "gl": "PK"}}
_RELATIVE_AGO = re.compile(
    r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", re.I)


def _parse_relative_time(text: str | None):
    """Best-effort parse of YouTube relative timestamps ('7 months ago')."""
    if not text:
        return None
    m = _RELATIVE_AGO.search(text)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    deltas = {"second": timedelta(seconds=n), "minute": timedelta(minutes=n),
              "hour": timedelta(hours=n), "day": timedelta(days=n),
              "week": timedelta(weeks=n), "month": timedelta(days=30 * n),
              "year": timedelta(days=365 * n)}
    return datetime.now(timezone.utc) - deltas[unit]


class YouTubeInnertubeClient:
    """Real YouTube comments via the public web client API (no credentials).

    Rate-limited politely (min interval between calls), retries transient
    failures with exponential backoff, and degrades gracefully: a video with
    comments disabled is skipped, a network error aborts with what was
    collected so far.
    """

    SEARCH_URL = f"https://www.youtube.com/youtubei/v1/search?key={_INNERTUBE_KEY}&prettyPrint=false"
    NEXT_URL = f"https://www.youtube.com/youtubei/v1/next?key={_INNERTUBE_KEY}&prettyPrint=false"

    def __init__(self) -> None:
        self._last_call = 0.0
        self.calls = 0

    def _post(self, url: str, payload: dict) -> dict | None:
        wait = settings.INNERTUBE_MIN_INTERVAL_SECONDS - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        backoff = 1.5
        for attempt in range(3):
            self.calls += 1
            self._last_call = time.time()
            try:
                resp = requests.post(
                    url, json=payload, timeout=settings.REQUEST_TIMEOUT_SECONDS + 10,
                    headers={"User-Agent": UA,
                             "Content-Type": "application/json",
                             "Accept-Language": "en-US,en;q=0.9",
                             "Origin": "https://www.youtube.com",
                             "Referer": "https://www.youtube.com/"},
                )
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code in (429, 500, 502, 503) and attempt < 2:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                log.warning("innertube HTTP %s on %s", resp.status_code, url.split("/v1/")[1][:20])
                return None
            except requests.RequestException as exc:
                log.warning("innertube network error: %s", exc)
                if attempt < 2:
                    time.sleep(backoff)
                    backoff *= 2
        return None

    @staticmethod
    def _walk(node, key: str):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == key:
                    yield v
                yield from YouTubeInnertubeClient._walk(v, key)
        elif isinstance(node, list):
            for it in node:
                yield from YouTubeInnertubeClient._walk(it, key)

    def search_videos(self, query: str, limit: int) -> list[dict]:
        payload = {"context": _INNERTUBE_CTX, "query": query}
        data = self._post(self.SEARCH_URL, payload)
        if not data:
            return []
        videos: list[dict] = []
        seen: set[str] = set()
        for vr in self._walk(data, "videoRenderer"):
            vid = vr.get("videoId")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            title = ""
            runs = ((vr.get("title") or {}).get("runs")) or []
            title = runs[0].get("text", "") if runs else ""
            owner_runs = ((vr.get("ownerText") or {}).get("runs")) or []
            videos.append({
                "video_id": vid,
                "title": title[:300],
                "channel": owner_runs[0].get("text", "")[:120] if owner_runs else None,
                "views_text": (vr.get("viewCountText") or {}).get("simpleText"),
                "published_text": (vr.get("publishedTimeText") or {}).get("simpleText"),
            })
            if len(videos) >= limit:
                break
        return videos

    def _comments_continuation(self, data: dict) -> str | None:
        """Find the comments-section continuation token in a /next response."""
        for ep in data.get("engagementPanels", []):
            panel = ep.get("engagementPanelSectionListRenderer", {})
            if panel.get("panelIdentifier") != "engagement-panel-comments-section":
                continue

            def find_cont(node):
                if isinstance(node, dict):
                    cir = node.get("continuationItemRenderer")
                    if cir:
                        tok = ((cir.get("continuationEndpoint") or {})
                               .get("continuationCommand", {}) or {}).get("token")
                        if tok:
                            return tok
                    for v in node.values():
                        found = find_cont(v)
                        if found:
                            return found
                elif isinstance(node, list):
                    for it in node:
                        found = find_cont(it)
                        if found:
                            return found
                return None

            token = find_cont(panel.get("content", {}))
            if token:
                return token
        return None

    def fetch_comments(self, video_id: str, want: int,
                       seen_ids: set[str] | None = None) -> tuple[list[dict], int]:
        """Collect real comments (top-level) for one video. Returns (comments, remaining_want)."""
        seen = seen_ids if seen_ids is not None else set()
        out: list[dict] = []
        token = None
        first = self._post(self.NEXT_URL, {"context": _INNERTUBE_CTX, "videoId": video_id})
        if not first:
            return out, want
        token = self._comments_continuation(first)
        pages = 0
        while token and pages < settings.YOUTUBE_MAX_PAGES_PER_VIDEO and len(out) < want:
            data = self._post(self.NEXT_URL, {"context": _INNERTUBE_CTX, "continuation": token})
            if not data:
                break
            pages += 1
            before = len(out)
            # New format: commentEntityPayload mutations (author, text, likes, time)
            for mut in ((data.get("frameworkUpdates") or {})
                        .get("entityBatchUpdate", {}) or {}).get("mutations", []):
                p = (mut.get("payload") or {}).get("commentEntityPayload")
                if not p:
                    continue
                cid = ((p.get("properties") or {}).get("commentId")) or mut.get("entityKey", "")
                if not cid or cid in seen:
                    continue
                text = (((p.get("properties") or {}).get("content") or {})
                        .get("content") or "").strip()
                if len(text) < 2:
                    continue
                seen.add(cid)
                author = ((p.get("author") or {}).get("displayName")) or None
                when = _parse_relative_time((p.get("properties") or {}).get("publishedTime"))
                likes_raw = ((p.get("toolbar") or {}).get("likeCountNotliked")) or ""
                try:
                    likes = int(str(likes_raw).replace(",", "")) if likes_raw else None
                except ValueError:
                    likes = None
                out.append({"id": f"yt_{cid[:200]}", "text": text, "author": author,
                            "likes": likes, "date": when, "video_id": video_id})
            # next page token: last continuationItemRenderer in the append action
            next_token = None
            for ep in data.get("onResponseReceivedEndpoints", []):
                action = ep.get("appendContinuationItemsAction") or \
                    ep.get("reloadContinuationItemsCommand") or {}
                items = action.get("continuationItems") or []
                if items:
                    cir = items[-1].get("continuationItemRenderer") or {}
                    tok = ((cir.get("continuationEndpoint") or {})
                           .get("continuationCommand", {}) or {}).get("token")
                    if tok:
                        next_token = tok
            token = next_token
            if len(out) == before:  # page yielded nothing new
                break
        return out, max(0, want - len(out))


def collect_youtube(product_name: str, description: str | None,
                    max_items: int) -> AdapterResult:
    """Collect REAL YouTube comments for the product via the public web API.

    Searches product review videos, then harvests top-level comments across
    the top videos until max_items is reached. No synthetic content.
    """
    if not (product_name or "").strip():
        return AdapterResult("youtube", AdapterStatus.NO_RESULTS, "Empty product name.")
    client = YouTubeInnertubeClient()
    query = f"{product_name} review" if len(product_name) < 25 else product_name
    videos = client.search_videos(query, settings.YOUTUBE_MAX_VIDEOS)
    if not videos:
        return AdapterResult(
            "youtube", AdapterStatus.BLOCKED,
            "YouTube web API unreachable from this deployment (no videos returned).")

    items: list[ReviewItem] = []
    seen_ids: set[str] = set()
    per_video = settings.YOUTUBE_COMMENTS_PER_VIDEO
    for v in videos:
        if len(items) >= max_items:
            break
        comments, _ = client.fetch_comments(v["video_id"],
                                            min(per_video, max_items - len(items)), seen_ids)
        for c in comments:
            if len(items) >= max_items:
                break
            url = f"https://www.youtube.com/watch?v={v['video_id']}"
            items.append(ReviewItem(
                external_id=c["id"],
                text=c["text"][:1500],
                review_date=c.get("date"),
                author=c.get("author"),
                source_url=url,
                # Comments were harvested from videos retrieved by a
                # product-scoped search ("{product} review"), so the product
                # context comes from the video level - the same rationale as
                # marketplace product-page items. Token-level relevance scoring
                # would wrongly discard e.g. "I love GM brava 808" under a
                # cricket-bat review video. Spam/promotional filtering and all
                # other pipeline quality gates still apply downstream.
                relevance_hint=0.6,
            ))

    status = AdapterStatus.SUCCESS if items else AdapterStatus.NO_RESULTS
    msg = (f"Collected {len(items)} real YouTube comments across {len(videos)} "
           f"review video(s) for '{query}' via the public YouTube web API.")
    return AdapterResult("youtube", status, msg, items=items[:max_items], data_source="live")
