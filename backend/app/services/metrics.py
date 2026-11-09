"""Performance metric calculations with safe zero-denominator handling.

Google Ads returns cost in *micros* (1 currency unit = 1,000,000 micros).
All conversions happen at the ingestion boundary; MetricSet always carries
currency units.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

MICROS = 1_000_000


def micros_to_units(micros: int | float) -> float:
    return float(micros) / MICROS


def units_to_micros(units: float) -> int:
    return int(round(float(units) * MICROS))


def safe_div(numerator: float, denominator: float) -> float | None:
    """Division that returns None instead of raising/inf on zero denominators."""
    if denominator is None or denominator == 0 or math.isnan(denominator):
        return None
    result = float(numerator) / float(denominator)
    if math.isnan(result) or math.isinf(result):
        return None
    return result


@dataclass
class MetricSet:
    """A bundle of raw advertising metrics plus derived KPIs.

    `impressions` here are ad impressions; for CPV-style view metrics use
    `video_impressions` (eligible impressions) and `video_views`.
    """

    impressions: float = 0.0
    clicks: float = 0.0
    cost: float = 0.0  # currency units (already converted from micros)
    conversions: float = 0.0
    conversion_value: float = 0.0
    video_views: float = 0.0
    video_impressions: float = 0.0

    source: str = "unknown"  # live | synthetic | predicted
    extras: dict = field(default_factory=dict)

    # --- derived metrics (spec section 8) -----------------------------------
    @property
    def ctr(self) -> float | None:
        """CTR % = clicks / impressions × 100"""
        v = safe_div(self.clicks, self.impressions)
        return None if v is None else v * 100.0

    @property
    def cpc(self) -> float | None:
        """CPC = cost / clicks"""
        return safe_div(self.cost, self.clicks)

    @property
    def cpa(self) -> float | None:
        """CPA = cost / conversions"""
        return safe_div(self.cost, self.conversions)

    @property
    def conversion_rate(self) -> float | None:
        """Conversion rate % = conversions / clicks × 100"""
        v = safe_div(self.conversions, self.clicks)
        return None if v is None else v * 100.0

    @property
    def roas(self) -> float | None:
        """ROAS = conversion value / cost"""
        return safe_div(self.conversion_value, self.cost)

    @property
    def cpv(self) -> float | None:
        """Average CPV = cost / video views"""
        return safe_div(self.cost, self.video_views)

    @property
    def video_view_rate(self) -> float | None:
        """View rate % = video views / eligible video impressions × 100"""
        v = safe_div(self.video_views, self.video_impressions)
        return None if v is None else v * 100.0

    @property
    def engagement_per_impression(self) -> float | None:
        return safe_div(self.clicks + self.video_views, self.impressions)

    def to_dict(self) -> dict:
        return {
            "impressions": self.impressions,
            "clicks": self.clicks,
            "cost": round(self.cost, 2),
            "conversions": round(self.conversions, 2),
            "conversion_value": round(self.conversion_value, 2),
            "video_views": self.video_views,
            "video_impressions": self.video_impressions,
            "ctr": round_or_none(self.ctr),
            "cpc": round_or_none(self.cpc),
            "cpa": round_or_none(self.cpa),
            "conversion_rate": round_or_none(self.conversion_rate),
            "roas": round_or_none(self.roas),
            "cpv": round_or_none(self.cpv),
            "video_view_rate": round_or_none(self.video_view_rate),
            "source": self.source,
        }


def round_or_none(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def merge_metric_sets(sets: list[MetricSet]) -> MetricSet:
    """Aggregate many metric bundles by summing raw counters, then derive."""
    total = MetricSet(source=sets[0].source if sets else "unknown")
    for s in sets:
        total.impressions += s.impressions
        total.clicks += s.clicks
        total.cost += s.cost
        total.conversions += s.conversions
        total.conversion_value += s.conversion_value
        total.video_views += s.video_views
        total.video_impressions += max(s.video_impressions, s.impressions if s.video_views else 0.0)
    return total
