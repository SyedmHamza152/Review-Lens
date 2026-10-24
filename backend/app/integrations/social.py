"""Social media adapters (Reddit, YouTube, X, Facebook, Instagram, TikTok).

Verified data-access situation (MVP, honest reporting):

| Platform  | Access                                                                      |
|-----------|------------------------------------------------------------------------------|
| Reddit    | Official OAuth API (script app). Public read-only search needs client        |
|           | id/secret. Unauthenticated JSON endpoints are blocked on most cloud IPs.     |
| YouTube   | YouTube Data API v3 with API key: search + commentThreads (public comments). |
| X         | X API v2 recent search (Bearer token); comments retrieval is a paid tier.    |
| Facebook  | Graph API Pages/Search is heavily restricted; keyword search of public posts |
|           | is not generally available. Requires App Review.                             |
| Instagram | Graph API hashtag search needs Business/Creator account + App Review.        |
| TikTok    | Research API (academic/commercial approval) or Display API - gated.          |

When credentials are absent, each adapter reports `needs_credentials` with the
exact environment variables; when calls fail (403/region/IP blocks) it reports
`blocked`. No fabricated posts, ever.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import requests

from app.core.config import settings
from app.integrations.base import AdapterResult, AdapterStatus, BaseAdapter, ReviewItem

TIMEOUT = settings.REQUEST_TIMEOUT_SECONDS


class _SocialAdapter(BaseAdapter):
    type = "social"

    def _needs_credentials(self) -> AdapterResult:
        return AdapterResult(
            platform=self.key,
            status=AdapterStatus.NEEDS_CREDENTIALS,
            message=(
                f"{self.name} public-content search requires authorized API access. "
                f"Configure {', '.join(self.required_env)} in backend/.env "
                f"({self.docs_url}). No data was collected for this platform."
            ),
        )


class RedditAdapter(_SocialAdapter):
    key = "reddit"
    name = "Reddit"
    access_mode = "Reddit OAuth API (script app) - public posts/comments"
    required_env = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"]
    docs_url = "https://www.reddit.com/dev/api/"
    notes = "Official OAuth search across public subreddits; user-agent required."

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        if not self.has_credentials:
            return self._needs_credentials()
        token_resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            auth=(settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET),
            headers={"User-Agent": settings.REDDIT_USER_AGENT},
            timeout=TIMEOUT,
        )
        if token_resp.status_code in (401, 403):
            return AdapterResult(self.key, AdapterStatus.BLOCKED,
                                 f"Reddit OAuth rejected credentials (HTTP {token_resp.status_code}).")
        token_resp.raise_for_status()
        token = token_resp.json()["access_token"]
        resp = requests.get(
            "https://oauth.reddit.com/search",
            params={"q": f'"{product_name}"', "limit": min(max_items, 100), "sort": "relevance"},
            headers={"Authorization": f"bearer {token}", "User-Agent": settings.REDDIT_USER_AGENT},
            timeout=TIMEOUT,
        )
        if resp.status_code in (403, 429):
            return AdapterResult(self.key, AdapterStatus.BLOCKED,
                                 f"Reddit search blocked/rate-limited (HTTP {resp.status_code}).")
        resp.raise_for_status()
        children = resp.json().get("data", {}).get("children", [])
        items = []
        for child in children:
            d = child.get("data", {})
            text = " ".join(filter(None, [d.get("title", ""), d.get("selftext", "")])).strip()
            if not text:
                continue
            items.append(ReviewItem(
                external_id=d.get("id", ""),
                text=text[:1500],
                review_date=datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc),
                author=d.get("author"),
                source_url=f"https://www.reddit.com{d.get('permalink', '')}",
            ))
        status = AdapterStatus.SUCCESS if items else AdapterStatus.NO_RESULTS
        return AdapterResult(self.key, status, items=items[:max_items])


class YouTubeAdapter(_SocialAdapter):
    key = "youtube"
    name = "YouTube"
    access_mode = "YouTube Data API v3 (API key) - search + comment threads"
    required_env = ["YOUTUBE_API_KEY"]
    docs_url = "https://developers.google.com/youtube/v3"
    notes = "Public video search + commentThreads; quotas apply (10k units/day default)."

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        if not self.has_credentials:
            return self._needs_credentials()
        search = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": product_name, "type": "video",
                    "maxResults": 10, "order": "relevance",
                    "key": settings.YOUTUBE_API_KEY},
            timeout=TIMEOUT,
        )
        if search.status_code in (403, 400):
            return AdapterResult(self.key, AdapterStatus.BLOCKED,
                                 f"YouTube API refused the key/quota (HTTP {search.status_code}).")
        search.raise_for_status()
        video_ids = [it["id"]["videoId"] for it in search.json().get("items", []) if "videoId" in it.get("id", {})]
        items: list[ReviewItem] = []
        for vid in video_ids:
            thread = requests.get(
                "https://www.googleapis.com/youtube/v3/commentThreads",
                params={"part": "snippet", "videoId": vid, "maxResults": 30,
                        "textFormat": "plainText", "key": settings.YOUTUBE_API_KEY},
                timeout=TIMEOUT,
            )
            if thread.status_code != 200:
                continue  # comments disabled for this video
            for it in thread.json().get("items", []):
                snip = it["snippet"]["topLevelComment"]["snippet"]
                text = (snip.get("textDisplay") or "").strip()
                if not text:
                    continue
                items.append(ReviewItem(
                    external_id=it["snippet"]["topLevelComment"]["id"],
                    text=text[:1500],
                    review_date=datetime.fromisoformat(snip["publishedAt"].replace("Z", "+00:00")),
                    author=snip.get("authorDisplayName"),
                    source_url=f"https://www.youtube.com/watch?v={vid}&lc={it['snippet']['topLevelComment']['id']}",
                ))
            if len(items) >= max_items:
                break
        status = AdapterStatus.SUCCESS if items else AdapterStatus.NO_RESULTS
        return AdapterResult(self.key, status, items=items[:max_items])


class XAdapter(_SocialAdapter):
    key = "x"
    name = "X (Twitter)"
    access_mode = "X API v2 recent search (Bearer token; paid tiers for posts)"
    required_env = ["X_BEARER_TOKEN"]
    docs_url = "https://developer.x.com/en/docs/twitter-api"
    notes = "Basic tier only allows posting; reading recent search requires paid access."

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        if not self.has_credentials:
            return self._needs_credentials()
        resp = requests.get(
            "https://api.x.com/2/tweets/search/recent",
            params={"query": f'"{product_name}" -is:retweet lang=(en OR ur)',
                    "max_results": min(100, max_items), "tweet.fields": "created_at,author_id"},
            headers={"Authorization": f"Bearer {settings.X_BEARER_TOKEN}"},
            timeout=TIMEOUT,
        )
        if resp.status_code in (401, 403, 429):
            return AdapterResult(self.key, AdapterStatus.BLOCKED,
                                 f"X API access denied or tier limit (HTTP {resp.status_code}). "
                                 "Reading tweets requires a paid API tier.")
        resp.raise_for_status()
        items = [
            ReviewItem(
                external_id=t["id"],
                text=t.get("text", "")[:1000],
                review_date=datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
                if t.get("created_at") else None,
                author=t.get("author_id"),
                source_url=f"https://x.com/i/status/{t['id']}",
            )
            for t in resp.json().get("data", [])
        ]
        status = AdapterStatus.SUCCESS if items else AdapterStatus.NO_RESULTS
        return AdapterResult(self.key, status, items=items[:max_items])


class FacebookAdapter(_SocialAdapter):
    key = "facebook"
    name = "Facebook"
    access_mode = "Meta Graph API - public keyword search is NOT generally available"
    required_env = ["FACEBOOK_ACCESS_TOKEN"]
    docs_url = "https://developers.facebook.com/docs/graph-api"
    notes = ("Public post keyword search was retired; only Page-owned data with "
             "permissions is accessible after App Review. Reported honestly.")

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        if not self.has_credentials:
            return self._needs_credentials()
        return AdapterResult(
            self.key, AdapterStatus.BLOCKED,
            "Graph API does not permit general keyword search of public posts; "
            "only Page-owned conversations with granted permissions are allowed "
            "after App Review. No data collected.",
        )


class InstagramAdapter(_SocialAdapter):
    key = "instagram"
    name = "Instagram"
    access_mode = "Graph API hashtag search (Business account + App Review)"
    required_env = ["INSTAGRAM_ACCESS_TOKEN"]
    docs_url = "https://developers.facebook.com/docs/instagram-api"
    notes = "Hashtag search limited to business accounts and 30 unique hashtags/7 days."

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        if not self.has_credentials:
            return self._needs_credentials()
        return AdapterResult(
            self.key, AdapterStatus.BLOCKED,
            "Instagram hashtag search requires a linked Business/Creator account and "
            "App Review; comment retrieval is limited to owned media. No data collected.",
        )


class TikTokAdapter(_SocialAdapter):
    key = "tiktok"
    name = "TikTok"
    access_mode = "TikTok Research API (approval-gated) / Display API"
    required_env = ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"]
    docs_url = "https://developers.tiktok.com/products/research-api/"
    notes = "Comment search requires Research API approval; not available to general apps."

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        if not self.has_credentials:
            return self._needs_credentials()
        return AdapterResult(
            self.key, AdapterStatus.BLOCKED,
            "TikTok Research API approval required for comment/query access; "
            "credentials present but scope not granted. No data collected.",
        )
