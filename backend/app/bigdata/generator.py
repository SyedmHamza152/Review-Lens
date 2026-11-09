"""Synthetic YouTube advertising dataset generator.

Streams rows to CSV (constant memory) at 10k / 100k / 1M / 10M scale.
Realistic-but-explicitly-synthetic: only eligible YouTube formats appear.

Fields:
  date, campaign_id, campaign_name, platform, ad_format, impressions, clicks,
  spend, conversions, revenue, video_views, age_group, gender, city, device,
  marketing_objective
"""
from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

from app.core.constants import AGE_GROUPS, DEVICES, MARKET_CITIES, SUPPORTED_FORMATS

CAMPAIGN_OBJECTIVES = [
    "Brand Awareness", "Video Views", "Website Traffic", "Leads", "Sales / Conversions",
]

BRANDS = ["Zenith", "Karachi Kicks", "LahoreLuxe", "IndusMart", "DesiDukaan",
          "PakStyle", "RaviRetail", "SialkotSports", "MohenjoMart", "BazaarBright"]

HEADER = [
    "date", "campaign_id", "campaign_name", "platform", "ad_format",
    "impressions", "clicks", "spend", "conversions", "revenue", "video_views",
    "age_group", "gender", "city", "device", "marketing_objective",
]

# Per-format economic regimes (documented assumptions, PKR):
FORMAT_REGIMES = {
    "in_stream": {"impr_mu": 5.6, "view_rate": 0.29, "click_per_view": 0.062, "cvr": 0.014, "cpc_mult": 1.0},
    "shorts":    {"impr_mu": 6.1, "view_rate": 0.21, "click_per_view": 0.030, "cvr": 0.011, "cpc_mult": 0.75},
    "in_feed":   {"impr_mu": 5.2, "view_rate": 0.00, "click_per_view": 0.0, "cvr": 0.009, "cpc_mult": 1.35},
}
IN_FEED_CTR = 0.011          # clicks per impression for in-feed
BASE_CPC = 9.5               # PKR per click baseline
AOV_RANGE = (700.0, 9000.0)  # product-agnostic AOV spread


def _campaign_pool(n_campaigns: int, market: str = "PK") -> list[dict]:
    rng = random.Random(1234)
    cities = MARKET_CITIES.get(market, MARKET_CITIES["PK"])
    pool = []
    formats = list(SUPPORTED_FORMATS.keys())
    for i in range(n_campaigns):
        fmt = formats[i % len(formats)]
        obj = CAMPAIGN_OBJECTIVES[i % len(CAMPAIGN_OBJECTIVES)]
        brand = BRANDS[i % len(BRANDS)]
        pool.append({
            "campaign_id": f"C-{1000 + i}",
            "campaign_name": f"YT {fmt} | {obj} | {brand} Q{i % 4 + 1}",
            "ad_format": fmt,
            "marketing_objective": obj,
            "aov": rng.uniform(*AOV_RANGE),
            "quality": rng.uniform(0.75, 1.3),  # per-campaign efficiency factor
            "city_bias": rng.sample(cities, k=min(4, len(cities))),
        })
    return pool


def generate_dataset(
    rows: int,
    out_path: str | Path,
    *,
    seed: int = 42,
    n_campaigns: int = 40,
    days: int = 180,
    market: str = "PK",
    progress_cb=None,
) -> Path:
    """Stream `rows` rows to CSV. Returns the output path."""
    if rows <= 0:
        raise ValueError("rows must be positive")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    pool = _campaign_pool(n_campaigns, market)
    cities = MARKET_CITIES.get(market, MARKET_CITIES["PK"])
    end = date.today() - timedelta(days=1)

    generated = 0
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        while generated < rows:
            camp = pool[rng.randrange(len(pool))]
            day = end - timedelta(days=rng.randrange(days))
            regime = FORMAT_REGIMES[camp["ad_format"]]
            impressions = int(math.exp(rng.gauss(regime["impr_mu"], 0.35)) * camp["quality"])
            impressions = max(impressions, 5)
            if regime["click_per_view"] > 0:  # cpv-priced formats
                views = int(impressions * regime["view_rate"] * rng.uniform(0.8, 1.2))
                clicks = int(views * regime["click_per_view"] * rng.uniform(0.75, 1.25))
            else:  # in_feed: cpc-priced
                views = int(impressions * 0.06 * rng.uniform(0.5, 1.5))  # watch-page opens
                clicks = int(impressions * IN_FEED_CTR * rng.uniform(0.75, 1.25))
            clicks = max(clicks, 0)
            cpc = BASE_CPC * regime["cpc_mult"] * rng.uniform(0.7, 1.35)
            spend = round(clicks * cpc, 2)
            conversions = 0
            for _ in range(clicks):
                if rng.random() < regime["cvr"] * camp["quality"]:
                    conversions += 1
            revenue = round(conversions * camp["aov"] * rng.uniform(0.85, 1.15), 2) if conversions else 0.0
            writer.writerow([
                day.isoformat(), camp["campaign_id"], camp["campaign_name"], "YouTube",
                camp["ad_format"], impressions, clicks, spend, conversions, revenue,
                views, rng.choices(AGE_GROUPS, weights=[0.32, 0.36, 0.19, 0.09, 0.04])[0],
                rng.choices(["female", "male", "unknown"], weights=[0.42, 0.5, 0.08])[0],
                rng.choice(camp["city_bias"] + cities[:1]),
                rng.choices(DEVICES, weights=[0.68, 0.20, 0.07, 0.05])[0],
                camp["marketing_objective"],
            ])
            generated += 1
            if progress_cb and generated % 200_000 == 0:
                progress_cb(generated, rows)
    return out
