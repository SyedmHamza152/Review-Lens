"""Demo seeder — provisions the demo user and SYNTHETIC DEMO campaign history.

Synthetic demo data is what keeps the application fully functional when no
Google Ads connection exists. It is labeled `SYNTHETIC DEMO DATA` on every
row and in every API payload that carries it. It is never mixed into a
response without that label.
"""
from __future__ import annotations

import logging
import random
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AGE_GROUPS, DEVICES, MARKET_CITIES
from app.models.campaign import Campaign, CampaignPerformance
from app.models.user import User

logger = logging.getLogger(__name__)

# 12 demo campaigns: 3 formats × objectives, 180 days, segmented rows.
DEMO_CAMPAIGNS = [
    # (name, format_key, objective, status, scale)
    ("YT in_stream | Sales | Zenith Sports", "in_stream", "Sales / Conversions", "ENABLED", 1.4),
    ("YT shorts | Sales | Zenith Sports", "shorts", "Sales / Conversions", "ENABLED", 1.1),
    ("YT in_feed | Sales | Zenith Sports", "in_feed", "Sales / Conversions", "ENABLED", 0.8),
    ("YT in_stream | Awareness | Zenith Sports", "in_stream", "Brand Awareness", "ENABLED", 1.2),
    ("YT shorts | Awareness | LahoreLuxe", "shorts", "Brand Awareness", "ENABLED", 1.0),
    ("YT in_stream | Leads | IT Courses PK", "in_stream", "Leads", "ENABLED", 0.9),
    ("YT in_feed | Leads | IT Courses PK", "in_feed", "Leads", "ENABLED", 0.7),
    ("YT shorts | Traffic | DesiSnacks", "shorts", "Website Traffic", "ENABLED", 1.15),
    ("YT in_stream | Traffic | HomeGear PK", "in_stream", "Website Traffic", "ENABLED", 0.95),
    ("YT shorts | Views | FitNow PK", "shorts", "Video Views", "ENABLED", 1.3),
    ("YT in_feed | Views | FitNow PK", "in_feed", "Video Views", "PAUSED", 0.5),
    ("YT in_stream | Conversions | GadgetHub", "in_stream", "Sales / Conversions", "ENABLED", 1.25),
]

PERF_WEIGHTS = {"in_stream": {"impr_mu": 5.7, "vr": 0.29, "cpv_click": 0.062, "cvr": 0.015, "cpc_mult": 1.0},
                "shorts": {"impr_mu": 6.2, "vr": 0.21, "cpv_click": 0.031, "cvr": 0.011, "cpc_mult": 0.72},
                "in_feed": {"impr_mu": 5.3, "vr": 0.0, "cpv_click": 0.0, "cvr": 0.009, "cpc_mult": 1.4}}
BASE_CPC = 9.0
AOV = {"Sales / Conversions": 3800.0, "Leads": 2500.0, "Website Traffic": 1500.0,
       "Brand Awareness": 3000.0, "Video Views": 2000.0}


def ensure_demo_user(db: Session) -> User:
    user = db.execute(select(User).where(User.email == settings.DEMO_USER_EMAIL)).scalar_one_or_none()
    if not user:
        user = User(email=settings.DEMO_USER_EMAIL, name=settings.DEMO_USER_NAME,
                    currency=settings.DEFAULT_CURRENCY, market=settings.DEFAULT_MARKET)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def seed_if_empty(db: Session) -> None:
    ensure_demo_user(db)
    count = db.execute(select(func.count(Campaign.id))).scalar() or 0
    if count > 0:
        return
    logger.info("Seeding SYNTHETIC DEMO campaign history (first run)...")
    _seed_campaigns(db)


def reseed(db: Session) -> int:
    n = db.execute(select(func.count(Campaign.id))).scalar() or 0
    if n:
        db.query(CampaignPerformance).delete()
        db.query(Campaign).delete()
        db.commit()
    _seed_campaigns(db)
    return len(DEMO_CAMPAIGNS)


def _seed_campaigns(db: Session) -> None:
    rng = random.Random(777)
    cities = MARKET_CITIES.get(settings.DEFAULT_MARKET, MARKET_CITIES["PK"])
    end = date.today() - timedelta(days=1)
    for name, fmt, objective, status, scale in DEMO_CAMPAIGNS:
        camp = Campaign(
            external_id=f"demo-{abs(hash(name)) % 10 ** 8}",
            name=name, channel_type="VIDEO", format_key=fmt,
            status=status, objective=objective,
            data_source_label="SYNTHETIC DEMO DATA",
        )
        db.add(camp)
        db.flush()
        regime = PERF_WEIGHTS[fmt]
        for d in range(180, 0, -1):
            day = end - timedelta(days=d)
            # gentle upward trend + weekly seasonality
            trend = 1.0 + 0.15 * (180 - d) / 180.0
            weekend = 1.15 if day.weekday() in (5, 6) else 1.0
            impressions = int(rng.gauss(1900, 320) * scale * trend * weekend)
            impressions = max(impressions, 60)
            views = int(impressions * regime["vr"]) if regime["vr"] else int(impressions * 0.05)
            clicks = int(views * regime["cpv_click"]) if regime["cpv_click"] else int(impressions * 0.011)
            cost = clicks * BASE_CPC * regime["cpc_mult"] * rng.uniform(0.85, 1.2)
            conversions = 0
            for _ in range(clicks):
                if rng.random() < regime["cvr"]:
                    conversions += 1
            value = conversions * AOV[objective] * rng.uniform(0.8, 1.2)
            # split the day across 2 audience segments for dimension analytics
            for age, gender, share in [
                (AGE_GROUPS[0], "male", 0.34), (AGE_GROUPS[1], "female", 0.38),
                (AGE_GROUPS[2], "unknown", 0.28),
            ]:
                s = share * rng.uniform(0.85, 1.15)
                db.add(CampaignPerformance(
                    campaign_id=camp.id, date=day,
                    impressions=int(impressions * s), clicks=int(clicks * s),
                    cost_micros=int(round(cost * s * 1_000_000)),
                    conversions=round(conversions * s, 2),
                    conversion_value=round(value * s, 2),
                    video_views=int(views * s),
                    video_impressions=int(impressions * s),
                    age_group=age, gender=gender,
                    device=rng.choices(DEVICES, weights=[0.68, 0.2, 0.07, 0.05])[0],
                    city=rng.choice(cities),
                    data_source_label="SYNTHETIC DEMO DATA",
                ))
    db.commit()
    logger.info("Demo seeding complete: %d campaigns", len(DEMO_CAMPAIGNS))
