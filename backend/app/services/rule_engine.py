"""Rule-based product intelligence engine (deterministic, explainable).

STEP 1  Product understanding   — category, type, features, value proposition
STEP 2  Audience intelligence   — inferred age/interest/geo segments
STEP 3  Marketing objective     — decision matrix over intent & price band

Every output is an *inference* (labeled in the UI), optionally enriched by a
local Ollama LLM when one is running. Inferred demographics are hypotheses —
never presented as verified personal data.
"""
from __future__ import annotations

from app.core.constants import MARKET_CITIES
from app.services.knowledge import (
    OBJECTIVE_DECISION_RULES,
    CategoryProfile,
    classify_category,
)

# Approximate AOV bands in PKR (documented assumptions; overridden by any
# real conversion-value evidence when available).
AOV_BANDS = {"low": 900.0, "medium": 3500.0, "high": 12000.0, "premium": 30000.0}


def understand_product(name: str, description: str, llm_result: dict | None = None) -> dict:
    text = f"{name} {description}".strip()
    profile, confidence = classify_category(text)
    product_type = _infer_product_type(name, description, profile)

    result = {
        "category": profile.label,
        "category_key": profile.key,
        "product_type": product_type,
        "features": _extract_features(name, description, profile),
        "value_proposition": _value_proposition(name, profile, product_type),
        "problems_solved": _problems_solved(profile),
        "intent": profile.intent,
        "aov_band": profile.avg_order_value_band,
        "aov_estimate": AOV_BANDS[profile.avg_order_value_band],
        "confidence": round(confidence, 2),
        "inference_method": "rule_based",
    }
    if llm_result:
        # LLM enrichment is merged conservatively: rules stay the backbone.
        for key in ("value_proposition", "product_type"):
            if isinstance(llm_result.get(key), str) and llm_result[key].strip():
                result[key] = llm_result[key].strip()
        if isinstance(llm_result.get("features"), list) and llm_result["features"]:
            merged = list(dict.fromkeys(result["features"] + [str(f) for f in llm_result["features"]][:6]))
            result["features"] = merged[:8]
        result["inference_method"] = "rule_based+ollama"
    return result


def infer_audience(profile: CategoryProfile, market: str = "PK", llm_result: dict | None = None) -> dict:
    cities = MARKET_CITIES.get(market, MARKET_CITIES["PK"])
    audience = {
        "age_weights": profile.age_weights,
        "gender_skew": profile.gender_skew,
        "interests": profile.interests,
        "geo": {
            "primary_market": market,
            "priority_cities": cities,
            "note": "City priorities are hypotheses derived from category demand patterns — validate with your own location analytics.",
        },
        "segments": profile.audience_segments,
        "intent": profile.intent,
        "disclaimer": (
            "Inferred from product language and category patterns. These are targeting "
            "hypotheses, not verified demographic data."
        ),
        "inference_method": "rule_based",
    }
    if llm_result:
        if isinstance(llm_result.get("interests"), list) and llm_result["interests"]:
            merged = list(dict.fromkeys(audience["interests"] + [str(i) for i in llm_result["interests"]][:5]))
            audience["interests"] = merged[:8]
        if isinstance(llm_result.get("segments"), list) and llm_result["segments"]:
            audience["segments"] = audience["segments"] + llm_result["segments"][:2]
        audience["inference_method"] = "rule_based+ollama"
    return audience


def select_objective(profile: CategoryProfile, budget: float) -> tuple[str, str]:
    """Decision matrix: score objectives from category intent + price band + budget."""
    scores: dict[str, float] = {}
    rationales: dict[str, list[str]] = {}
    for rule in OBJECTIVE_DECISION_RULES:
        cond = rule["conditions"]
        match = True
        if "intent" in cond and profile.intent not in cond["intent"]:
            match = False
        if "avg_order_value_band" in cond and profile.avg_order_value_band not in cond["avg_order_value_band"]:
            match = False
        if match:
            scores[rule["objective"]] = scores.get(rule["objective"], 0.0) + rule["weight"]
            rationales.setdefault(rule["objective"], []).append(rule["rationale"])

    # budget modulation: small budgets favor cheap, high-signal objectives
    if budget and budget < 15000:
        scores["Website Traffic"] = scores.get("Website Traffic", 0.0) + 1.0
        rationales.setdefault("Website Traffic", []).append(
            "Budget is small; traffic campaigns collect retargeting audiences cheaply before conversion optimization."
        )
    if not scores:
        scores["Sales / Conversions"] = 2.0
        rationales["Sales / Conversions"] = ["Default for shoppable products without stronger contrary signals."]

    best = max(scores.items(), key=lambda kv: kv[1])[0]
    why = " ".join(rationales.get(best, []))
    extra = (
        f" Category signals: intent={profile.intent}, price band={profile.avg_order_value_band} "
        f"(est. AOV ~{AOV_BANDS[profile.avg_order_value_band]:,.0f} PKR)."
    )
    return best, (why + extra)


def suitable_formats(profile: CategoryProfile) -> list[dict]:
    """Format suitability with evidence-based explanations."""
    formats = []
    notes = {
        "in_stream": "Skippable in-stream supports longer storytelling and product demos; strongest where buyers research before purchase.",
        "shorts": "Vertical Shorts deliver cheap incremental reach and strong discovery for visual, trend or impulse products.",
        "in_feed": "In-feed cards sit beside organic content; deliberate clickers, useful for considered or niche purchases.",
    }
    fit = profile.format_affinity
    for key in ("in_stream", "shorts", "in_feed"):
        mult = fit.get(key, 1.0)
        verdict = "Highly suitable" if mult >= 1.15 else ("Suitable" if mult >= 0.95 else "Support role")
        formats.append({
            "format_key": key,
            "label": {"in_stream": "YouTube In-Stream Ads", "shorts": "YouTube Shorts Ads",
                      "in_feed": "YouTube In-Feed Video Ads"}[key],
            "affinity": mult,
            "verdict": verdict,
            "rationale": f"{notes[key]} Category affinity multiplier: ×{mult:.2f}. {profile.notes}".strip(),
        })
    formats.sort(key=lambda f: f["affinity"], reverse=True)
    return formats


def _infer_product_type(name: str, description: str, profile: CategoryProfile) -> str:
    lowered = f"{name} {description}".lower()
    if any(w in lowered for w in ("professional", "pro ", "premium", "elite", "master")):
        return "Premium / professional tier"
    if any(w in lowered for w in ("mini", "compact", "portable", "travel")):
        return "Compact / portable variant"
    if any(w in lowered for w in ("kit", "set", "bundle", "pack")):
        return "Bundle / kit"
    if any(w in lowered for w in ("beginner", "starter", "basic", "entry")):
        return "Entry-level variant"
    return f"{profile.label.split('&')[0].strip()} product"


def _extract_features(name: str, description: str, profile: CategoryProfile) -> list[str]:
    base = [name.strip()]
    if description.strip():
        # split description into feature-ish clauses
        parts = [p.strip(" .-,;") for p in description.replace(";", ",").replace(" and ", ",").split(",")]
        base += [p for p in parts if 2 < len(p) < 90][:5]
    return base[:6]


def _value_proposition(name: str, profile: CategoryProfile, product_type: str) -> str:
    templates = {
        "sports_equipment": f"{name} targets players who need dependable equipment; the proposition centers on performance, durability and match-day confidence.",
        "electronics": f"{name} competes on features and reliability; the proposition should highlight the specs that matter and after-sales support.",
        "fashion_apparel": f"{name} sells identity and style; the proposition leans on look, trend fit and value for money.",
        "beauty_skincare": f"{name} promises visible results; the proposition should be ingredient- and outcome-led with social proof.",
        "food_beverage": f"{name} wins on taste and quality cues; the proposition emphasizes freshness and everyday value.",
        "fitness_health": f"{name} supports a transformation goal; the proposition centers on measurable progress and trust.",
        "home_kitchen": f"{name} improves daily life at home; the proposition stresses convenience, durability and demonstrated results.",
        "education_courses": f"{name} promises measurable learning outcomes; the proposition leads with results, mentors and proof.",
        "toys_kids": f"{name} must win parents' trust; the proposition highlights safety, development value and durability.",
        "automotive": f"{name} rides on enthusiasm and reliability; the proposition highlights performance and protection of the vehicle.",
        "jewelry_accessories": f"{name} sells emotion and occasion; the proposition emphasizes craftsmanship and authenticity.",
        "software_app": f"{name} removes friction from a workflow; the proposition focuses on time saved and measurable outcomes.",
        "services_local": f"{name} sells dependable outcomes nearby; the proposition stresses speed, trust and reviews.",
        "books_media": f"{name} promises knowledge or escape; the proposition centers on the transformation the reader gets.",
        "general": f"{name} communicates value through quality and price; the proposition should be sharpened with a clearer description.",
    }
    key = profile.key if profile.key in templates else "general"
    return templates[key]


def _problems_solved(profile: CategoryProfile) -> list[str]:
    mapping = {
        "sports_equipment": ["Unreliable gear that fails in play", "Uncertainty about the right grade/spec"],
        "electronics": ["Feature overload and confusing comparisons", "Fear of poor after-sales support"],
        "fashion_apparel": ["Difficulty judging fit and quality online", "Keeping up with trends affordably"],
        "beauty_skincare": ["Products that irritate or underdeliver", "Not knowing which ingredients matter"],
        "food_beverage": ["Inconsistent taste/quality", "Finding trustworthy everyday options"],
        "fitness_health": ["Lack of guided, sustainable routines", "Confusion about supplements"],
        "home_kitchen": ["Time-consuming chores", "Appliances that break quickly"],
        "education_courses": ["Exam anxiety and unstructured prep", "Skills gap for career growth"],
        "toys_kids": ["Safety concerns", "Toys that lose novelty quickly"],
        "automotive": ["Protecting vehicle value", "Finding trustworthy parts/accessories"],
        "jewelry_accessories": ["Authenticity doubts", "Finding designs for the right occasion"],
        "software_app": ["Manual, repetitive workflows", "Tool sprawl and cost"],
        "services_local": ["Finding reliable providers fast", "Fear of poor service"],
        "books_media": ["Choosing what to read next", "Access to quality content"],
        "general": ["Choosing between many similar options"],
    }
    return mapping.get(profile.key, ["Choosing between many similar options"])
