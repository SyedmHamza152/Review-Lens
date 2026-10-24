"""Live data sources that work WITHOUT credentials (verified reachable).

Connectivity matrix verified from this deployment (2026-10, curl probes):

| Source              | Endpoint                                        | Result          |
|---------------------|--------------------------------------------------|-----------------|
| Reddit archive      | arctic-shift.photon-reddit.com/api/*             | LIVE (200)      |
| Hacker News         | hn.algolia.com/api/v1/*                          | LIVE (200)      |
| Daraz PK storefront | www.daraz.pk/catalog/?q=...&ajax=true            | LIVE (200)      |
| reddit.com JSON     | www.reddit.com/*.json (unauthenticated)          | 403 datacenter  |
| YouTube / X / eBay  | googleapis / api.x.com / api.ebay.com            | reachable, needs key |
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
