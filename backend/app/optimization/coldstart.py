"""Cold-start priors for the budget optimizer.

When there is no (or too little) campaign history and no trained ML model,
the optimizer falls back to these transparent, hand-calibrated priors.
They are *assumptions*, tuned for the default Pakistan market in PKR and
documented in the README + surfaced in the UI methodology text. They are
blended with any real evidence via shrinkage, never silently substituted.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatPrior:
    format_key: str
    pricing_model: str      # "cpv" (pay per view) | "cpc" (pay per click)
    unit_cost: float        # currency per view (cpv) or per click (cpc)
    view_rate: float        # impressions -> views (cpv formats only)
    click_rate: float       # clicks per view (cpv) or per impression (cpc)
    cvr: float              # conversions per click
    aov_factor: float       # multiplier applied to the category AOV estimate
    risk: float             # 0 (safe) .. 1 (uncertain)
    notes: str = ""


# PKR market assumptions (2024–2026 SME campaigns). Every number here is a
# documented heuristic, not measured data.
FORMAT_PRIORS: dict[str, FormatPrior] = {
    "in_stream": FormatPrior(
        format_key="in_stream",
        pricing_model="cpv",
        unit_cost=1.10,      # PKR per view
        view_rate=0.28,      # ~28% of eligible impressions become views
        click_rate=0.06,     # ~6% of viewers click through
        cvr=0.012,           # ~1.2% of clicks convert
        aov_factor=1.00,
        risk=0.30,
        notes="Skippable in-stream: strong for storytelling and demos; pay per viewed impression.",
    ),
    "shorts": FormatPrior(
        format_key="shorts",
        pricing_model="cpv",
        unit_cost=0.55,      # cheaper views, younger reach
        view_rate=0.20,
        click_rate=0.03,     # swipe-heavy placement, fewer click-outs
        cvr=0.010,
        aov_factor=0.90,
        risk=0.40,
        notes="Shorts: cheapest incremental reach, best with young audiences and visual/impulse products.",
    ),
    "in_feed": FormatPrior(
        format_key="in_feed",
        pricing_model="cpc",
        unit_cost=10.0,      # PKR per click (thumbnail click to site/watch page)
        view_rate=0.0,       # not view-priced
        click_rate=0.010,    # clicks per impression (in-feed CTR)
        cvr=0.007,
        aov_factor=1.10,     # click-out traffic tends to be more deliberate
        risk=0.25,
        notes="In-feed: intent-flavored discovery next to organic content; steadier, lower volume.",
    ),
}

# Category average-order-value assumptions in PKR (documented heuristics).
AOV_BY_BAND = {
    "low": 900.0,
    "medium": 3500.0,
    "high": 12000.0,
    "premium": 30000.0,
}

# Exploration bonus: pseudo sample size attributed to priors themselves.
PRIOR_PSEUDO_SAMPLE = 25.0
