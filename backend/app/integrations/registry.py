"""Adapter registry: all supported platforms with live capability metadata."""
from __future__ import annotations

from app.integrations.base import AdapterStatus, BaseAdapter
from app.integrations.live_sources import HackerNewsAdapter
from app.integrations.marketplaces import (
    AlibabaAdapter, AliExpressAdapter, AmazonAdapter, DarazAdapter,
    SheinAdapter, TemuAdapter,
)
from app.integrations.social import (
    FacebookAdapter, InstagramAdapter, RedditAdapter, TikTokAdapter,
    XAdapter, YouTubeAdapter,
)


def build_adapters() -> dict[str, BaseAdapter]:
    adapters: list[BaseAdapter] = [
        # marketplaces
        DarazAdapter(), AmazonAdapter(), AlibabaAdapter(),
        AliExpressAdapter(), TemuAdapter(), SheinAdapter(),
        # social / discussion
        RedditAdapter(), HackerNewsAdapter(), YouTubeAdapter(), XAdapter(),
        FacebookAdapter(), InstagramAdapter(), TikTokAdapter(),
    ]
    return {a.key: a for a in adapters}


ADAPTERS: dict[str, BaseAdapter] = build_adapters()


def platform_listing() -> list[dict]:
    """Static capability info for the /api/platforms endpoint."""
    out = []
    for adapter in ADAPTERS.values():
        status = adapter.status_for_listing()
        out.append({
            "key": adapter.key,
            "name": adapter.name,
            "type": adapter.type,
            "status": status.value if isinstance(status, AdapterStatus) else str(status),
            "live_capability": adapter.live_capability,
            "has_credentials": adapter.has_credentials,
            "required_env": adapter.required_env,
            # Env vars that unlock ADDITIONAL capability on top of a live
            # baseline (e.g. Daraz review TEXT via Open Platform).
            "optional_env": list(getattr(adapter, "optional_env", []) or []),
            "access_mode": adapter.access_mode,
            "notes": adapter.notes,
            "docs_url": adapter.docs_url,
        })
    # order: live sources first, then credential-gated, then unavailable
    cap_order = {"live": 0, "requires_credentials": 1, "not_available": 2}
    type_order = {"marketplace": 0, "social": 1}
    out.sort(key=lambda p: (cap_order.get(p["live_capability"], 9),
                            type_order.get(p["type"], 9), p["name"]))
    return out
