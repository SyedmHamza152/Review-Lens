"""Adapter registry.

Product decision (2026-10, user directive): the platform is YouTube-ONLY.
All other platform adapters were removed from the product surface - the
/api/platforms listing, the search form and every report draw exclusively
from YouTube. The other adapter modules remain in the codebase (unused,
unregistered) so they can be re-enabled later if the product scope changes.
"""
from __future__ import annotations

from app.integrations.base import AdapterStatus, BaseAdapter
from app.integrations.social import YouTubeAdapter


def build_adapters() -> dict[str, BaseAdapter]:
    adapters: list[BaseAdapter] = [
        YouTubeAdapter(),
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
            # baseline (none for YouTube - it is live credential-free).
            "optional_env": list(getattr(adapter, "optional_env", []) or []),
            "access_mode": adapter.access_mode,
            "notes": adapter.notes,
            "docs_url": adapter.docs_url,
        })
    cap_order = {"live": 0, "requires_credentials": 1, "not_available": 2}
    type_order = {"marketplace": 0, "social": 1}
    out.sort(key=lambda p: (cap_order.get(p["live_capability"], 9),
                            type_order.get(p["type"], 9), p["name"]))
    return out
