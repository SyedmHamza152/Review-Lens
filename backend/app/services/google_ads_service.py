"""Google Ads sync service — pulls VIDEO campaign performance into the DB.

Only callable when the Google Ads integration is fully configured; otherwise
raises with the exact missing prerequisites so the UI can display honest
setup instructions instead of pretending.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations import google_ads_client
from app.models.campaign import Campaign, CampaignPerformance

logger = logging.getLogger(__name__)


def sync_campaigns(db: Session, days: int = 90) -> int:
    """Fetch daily VIDEO campaign rows and upsert them. Returns row count."""
    start = (date.today() - timedelta(days=days)).isoformat()
    end = (date.today() - timedelta(days=1)).isoformat()
    rows = google_ads_client.fetch_daily_performance(start, end)
    if not rows:
        return 0

    campaigns: dict[str, Campaign] = {}
    n_perf = 0
    for r in rows:
        camp = campaigns.get(r.campaign_id)
        if camp is None:
            camp = db.execute(
                select(Campaign).where(Campaign.external_id == r.campaign_id,
                                       Campaign.data_source_label == "LIVE DATA")
            ).scalar_one_or_none()
            if camp is None:
                camp = Campaign(
                    external_id=r.campaign_id, name=r.campaign_name,
                    channel_type=r.channel_type, channel_subtype=r.channel_subtype,
                    format_key=r.format_key, status=r.status,
                    objective="", data_source_label="LIVE DATA",
                )
                db.add(camp)
                db.flush()
            campaigns[r.campaign_id] = camp

        existing = db.execute(
            select(CampaignPerformance).where(
                CampaignPerformance.campaign_id == camp.id,
                CampaignPerformance.date == date.fromisoformat(r.date) if r.date else date.today(),
                CampaignPerformance.age_group == "unknown",
            )
        ).scalar_one_or_none()
        if existing:
            existing.impressions = r.impressions
            existing.clicks = r.clicks
            existing.cost_micros = int(round(r.cost_units * 1_000_000))
            existing.conversions = r.conversions
            existing.conversion_value = r.conversion_value
            existing.video_views = r.video_views
            existing.video_impressions = r.impressions
        else:
            db.add(CampaignPerformance(
                campaign_id=camp.id,
                date=date.fromisoformat(r.date) if r.date else date.today(),
                impressions=r.impressions, clicks=r.clicks,
                cost_micros=int(round(r.cost_units * 1_000_000)),
                conversions=r.conversions, conversion_value=r.conversion_value,
                video_views=r.video_views, video_impressions=r.impressions,
                age_group="unknown", gender="unknown", device="unknown",
                data_source_label="LIVE DATA",
            ))
        n_perf += 1
    db.commit()
    return n_perf


def integration_status() -> dict:
    """Honest status for Settings/Health endpoints."""
    missing = google_ads_client.missing_requirements()
    return {
        "configured": google_ads_client.is_configured(),
        "missing": missing,
        "customer_id": settings.GOOGLE_ADS_CUSTOMER_ID or settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID or "",
        "note": (
            "Google Ads API additionally requires an approved developer token "
            "(Basic access) and account linkage — see README §Google Ads setup."
            if missing else
            "All env vars present. Connection is verified by POST /api/v1/oauth/google/test-connection."
        ),
    }
