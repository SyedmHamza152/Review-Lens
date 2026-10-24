"""Adapter registry: all supported platforms with live capability metadata."""
from __future__ import annotations

from app.integrations.base import AdapterStatus, BaseAdapter
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
        # social
        RedditAdapter(), YouTubeAdapter(), XAdapter(),
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
            "has_credentials": adapter.has_credentials,
            "required_env": adapter.required_env,
            "access_mode": adapter.access_mode,
            "notes": adapter.notes,
            "docs_url": adapter.docs_url,
        })
    # order: marketplaces first (stable, readable)
    type_order = {"marketplace": 0, "social": 1}
    out.sort(key=lambda p: (type_order.get(p["type"], 9), p["name"]))
    return out
