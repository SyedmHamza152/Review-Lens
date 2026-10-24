"""Sample corpus loader (DEMONSTRATION DATA ONLY).

Chooses the closest product archetype for the search query and returns
clearly-labelled sample reviews so the full pipeline (collection -> language
detection -> sentiment -> aspects -> dashboard) can be exercised end-to-end
even when no platform API credentials are configured.

Everything returned here is marked data_source="sample" and is displayed with
a SAMPLE badge. It is never mixed silently with real data.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.integrations.base import AdapterResult, AdapterStatus, ReviewItem
from app.integrations.sample_data_audio import EARBUDS_ITEMS
from app.integrations.sample_data_fashion import SNEAKERS_ITEMS, SPAM_ITEMS
from app.integrations.sample_data_phone import PHONE_ITEMS

ARCHETYPES: dict[str, list[tuple[str, str, float | None, int, str | None]]] = {
    "phone": PHONE_ITEMS,
    "earbuds": EARBUDS_ITEMS,
    "sneakers": SNEAKERS_ITEMS,
}

# tokens used to swap the archetype noun with the searched product name
_NOUN_SUBS = {
    "phone": ["phone", "mobile", "set", "فون"],
    "earbuds": ["buds", "earbuds", "airpods"],
    "sneakers": ["shoes", "joggers", "sneakers"],
}

_ARCHETYPE_KEYWORDS = {
    "phone": {"phone", "mobile", "samsung", "galaxy", "iphone", "redmi", "note",
              "infinix", "techno", "tecno", "oppo", "vivo", "pixel", "xiaomi",
              "poco", "realme", "honour", "honor", "pro", "ultra", "max", "a54", "s25"},
    "earbuds": {"earbuds", "buds", "airpods", "headphone", "headphones", "earphone",
                "earphones", "tws", "audio", "sound", "bass", "galaxy buds"},
    "sneakers": {"shoes", "shoe", "sneaker", "sneakers", "trainers", "joggers",
                 "footwear", "kicks", "running", "nike", "adidas", "puma"},
}


def _pick_archetype(product_name: str, description: str | None) -> str:
    text = f"{product_name} {description or ''}".lower()
    scores = {k: sum(1 for kw in kws if kw in text) for k, kws in _ARCHETYPE_KEYWORDS.items()}
    best = max(scores, key=lambda k: scores[k])  # type: ignore[arg-type]
    return best if scores[best] > 0 else "phone"


def _substitute_noun(text: str, archetype: str, product_name: str) -> str:
    """Swap archetype nouns with the searched product for coherent demo data."""
    short = product_name.strip()
    # Cap length so sentences remain readable
    if len(short) > 42:
        short = short[:42].rsplit(" ", 1)[0]
    for noun in _NOUN_SUBS[archetype]:
        if noun in text:
            text = text.replace(noun, short.lower() if noun.islower() and not noun.startswith("فون") else short)
            break
    return text


def build_sample_result(platform: str, product_name: str, description: str | None,
                        max_items: int, seed: int = 7) -> AdapterResult:
    """Return sample items for one platform for the given product query."""
    if not settings.ALLOW_SAMPLE_DATA:
        return AdapterResult(platform, status=AdapterStatus.NO_RESULTS,
                             message="Sample data disabled by configuration.")
    archetype = _pick_archetype(product_name, description)
    pool = [it for it in ARCHETYPES[archetype] if it[0] == platform]
    pool += [it for it in SPAM_ITEMS if it[0] == platform]

    now = datetime.now(timezone.utc)
    rng = random.Random(seed)
    is_marketplace = platform in {"daraz", "amazon", "alibaba", "aliexpress", "temu", "shein"}
    hint = 0.85 if is_marketplace else 0.75
    items: list[ReviewItem] = []
    for idx, (plat, text, rating, days_ago, variant) in enumerate(pool):
        adjusted = _substitute_noun(text, archetype, product_name)
        items.append(ReviewItem(
            external_id=f"sample-{archetype}-{plat}-{idx}",
            text=adjusted,
            rating=rating,
            review_date=now - timedelta(days=days_ago, hours=rng.randint(0, 20)),
            variant=variant,
            author=f"sample_user_{rng.randint(100, 999)}",
            source_url=None,  # synthetic data has no real source link - shown as N/A
            relevance_hint=hint,
        ))
    return AdapterResult(
        platform=platform,
        status=AdapterStatus.SUCCESS,
        message="Curated SAMPLE dataset (synthetic, demonstration only - not real reviews).",
        items=items[:max_items],
        is_sample=True,
        data_source="sample",
    )


def get_archetype_name(product_name: str, description: str | None) -> str:
    return _pick_archetype(product_name, description)
