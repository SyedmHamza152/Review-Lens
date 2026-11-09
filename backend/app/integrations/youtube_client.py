"""YouTube Data API v3 client — public content research only.

What this client provides: product-related video search, video metadata,
public view/like/comment counts, channel statistics, publish dates.

What it does NOT provide (and must never be claimed): advertising spend,
paid conversions, competitor ROAS. Public organic stats != paid performance.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings

logger = logging.getLogger(__name__)


def _clean(text: str) -> str:
    """YouTube API returns HTML-escaped snippets (&quot;, &amp;) — unescape."""
    import html

    return html.unescape(text or "")

# Quota costs (units): search.list = 100, videos.list / channels.list = 1
QUOTA_COST = {"search": 100, "videos": 1, "channels": 1}


class YouTubeNotConfigured(Exception):
    pass


@dataclass
class QuotaState:
    used: int = 0
    limit: int = 10000  # default daily quota for new projects

    def spend(self, units: int) -> None:
        self.used += units


# In-process quota tracker (resets with the process; honest per-process view).
quota_state = QuotaState()


def is_configured() -> bool:
    return bool(settings.YOUTUBE_API_KEY)


def _client():
    if not is_configured():
        raise YouTubeNotConfigured(
            "YOUTUBE_API_KEY is not configured — add it to backend/.env to enable live research."
        )
    return build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY, cache_discovery=False)


def _with_backoff(fn, *, retries: int = 3, base_delay: float = 1.0):
    """Retry with exponential backoff on transient errors (403 quota / 429 / 5xx)."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return fn()
        except HttpError as e:  # noqa: PERF203
            status = e.resp.status
            if status in (403, 429, 500, 503):
                last_exc = e
                delay = base_delay * (2 ** attempt)
                logger.warning("YouTube API %s — backing off %.1fs (attempt %d)", status, delay, attempt + 1)
                time.sleep(delay)
                continue
            raise
    raise last_exc  # type: ignore[misc]


def search_videos(query: str, *, limit: int = 12, order: str = "relevance") -> list[dict]:
    """Search public videos. Returns raw items (videoId, title, channel)."""
    svc = _client()
    try:
        resp = _with_backoff(lambda: svc.search().list(
            q=query, part="snippet", type="video", maxResults=min(limit, 25),
            order=order, relevanceLanguage="en", safeSearch="moderate",
        ).execute())
        quota_state.spend(QUOTA_COST["search"])
        out = []
        for item in resp.get("items", []):
            vid = item.get("id", {}).get("videoId")
            sn = item.get("snippet", {})
            if not vid:
                continue
            out.append({
                "video_id": vid,
                "title": _clean(sn.get("title", "")),
                "channel_id": sn.get("channelId", ""),
                "channel_title": _clean(sn.get("channelTitle", "")),
                "published_at": sn.get("publishedAt", ""),
                "thumbnail_url": (sn.get("thumbnails", {}).get("medium", {}) or {}).get("url", ""),
            })
        return out
    finally:
        svc.close()


def get_video_details(video_ids: list[str]) -> list[dict]:
    """statistics.contentDetails for up to 50 ids per call (organic public stats)."""
    if not video_ids:
        return []
    svc = _client()
    out: list[dict] = []
    try:
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i:i + 50]
            resp = _with_backoff(lambda chunk=chunk: svc.videos().list(
                id=",".join(chunk), part="statistics,contentDetails,snippet",
            ).execute())
            quota_state.spend(QUOTA_COST["videos"])
            for item in resp.get("items", []):
                st = item.get("statistics", {})
                cd = item.get("contentDetails", {})
                sn = item.get("snippet", {})
                out.append({
                    "video_id": item.get("id", ""),
                    "views": int(st.get("viewCount", 0) or 0),
                    "likes": int(st.get("likeCount", 0) or 0),
                    "comments": int(st.get("commentCount", 0) or 0),
                    "duration_seconds": _parse_duration(cd.get("duration", "")),
                    "title": _clean(sn.get("title", "")),
                    "channel_id": sn.get("channelId", ""),
                    "tags": sn.get("tags", [])[:10],
                })
    finally:
        svc.close()
    return out


def get_channel_details(channel_ids: list[str]) -> dict[str, dict]:
    if not channel_ids:
        return {}
    svc = _client()
    out: dict[str, dict] = {}
    try:
        uniq = list(dict.fromkeys(channel_ids))
        for i in range(0, len(uniq), 50):
            chunk = uniq[i:i + 50]
            resp = _with_backoff(lambda chunk=chunk: svc.channels().list(
                id=",".join(chunk), part="statistics,snippet",
            ).execute())
            quota_state.spend(QUOTA_COST["channels"])
            for item in resp.get("items", []):
                st = item.get("statistics", {})
                out[item.get("id", "")] = {
                    "subscribers": int(st.get("subscriberCount", 0) or 0),
                    "total_views": int(st.get("viewCount", 0) or 0),
                    "video_count": int(st.get("videoCount", 0) or 0),
                    "title": _clean(item.get("snippet", {}).get("title", "")),
                }
    finally:
        svc.close()
    return out


def _parse_duration(iso: str) -> int:
    """PT12M34S -> seconds."""
    import re

    m = re.match(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def research_product(product_name: str, description: str = "", *, limit: int = 12) -> dict:
    """Full research bundle for a product: search + details + channels + analysis.

    Returned rows are ORGANIC content metrics. Engagement rate is computed
    from public stats only.
    """
    query = f"{product_name} review" if "review" not in product_name.lower() else product_name
    results = search_videos(query, limit=limit)
    ids = [r["video_id"] for r in results]
    details = {d["video_id"]: d for d in get_video_details(ids)}
    channel_ids = [r["channel_id"] for r in results if r.get("channel_id")]
    channels = get_channel_details(channel_ids)

    videos: list[dict] = []
    for r in results:
        d = details.get(r["video_id"], {})
        ch = channels.get(r.get("channel_id", ""), {})
        views = d.get("views", 0)
        likes = d.get("likes", 0)
        comments = d.get("comments", 0)
        engagement = ((likes + comments) / views) if views > 0 else 0.0
        videos.append({
            **r,
            "views": views,
            "likes": likes,
            "comments": comments,
            "duration_seconds": d.get("duration_seconds", 0),
            "channel_subscribers": ch.get("subscribers", 0),
            "engagement_rate": round(engagement, 5),
            "data_source_label": "LIVE DATA",
        })

    videos.sort(key=lambda v: v["views"], reverse=True)
    summary = {
        "videos_found": len(videos),
        "total_views": sum(v["views"] for v in videos),
        "median_views": _median([v["views"] for v in videos]),
        "avg_engagement_rate": _mean([v["engagement_rate"] for v in videos]),
        "shorts_share": _share_shorts(videos),
        "top_channels": [
            {"channel_id": cid, "title": ch.get("title", ""), "subscribers": ch.get("subscribers", 0)}
            for cid, ch in sorted(channels.items(), key=lambda kv: kv[1].get("subscribers", 0), reverse=True)[:5]
        ],
        "quota_used_process": quota_state.used,
        "note": (
            "Public organic YouTube statistics (views/likes/comments). These describe content "
            "engagement, NOT advertising spend, paid conversions or competitor ROAS."
        ),
    }
    return {"query": query, "videos": videos, "summary": summary, "source": "LIVE DATA"}


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    n = len(xs)
    return float((xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2))


def _mean(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 5) if xs else 0.0


def _share_shorts(videos: list[dict]) -> float:
    if not videos:
        return 0.0
    shorts = sum(1 for v in videos if 0 < v["duration_seconds"] <= 65)
    return round(shorts / len(videos), 2)
