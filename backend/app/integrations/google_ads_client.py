"""Google Ads API client — YouTube video campaign reporting via GAQL.

Scope & honesty rules:
  * only VIDEO advertising channel campaigns are fetched (YouTube inventory);
    Search / Display / Performance Max rows are filtered OUT by the query.
  * cost arrives in micros and is converted at this boundary.
  * if credentials/developer token are missing or permission is denied, a
    typed error is raised — the app then uses clearly-labeled synthetic demo
    data instead of pretending to have live numbers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings
from app.core.constants import SUBTYPE_TO_FORMAT
from app.integrations.google_oauth import get_access_token_from_refresh

logger = logging.getLogger(__name__)

GAQL_DAILY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign.advertising_channel_type,
  campaign.advertising_channel_subtype,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value,
  metrics.video_views,
  metrics.video_view_rate,
  metrics.ctr,
  metrics.average_cpc,
  metrics.average_cpv,
  metrics.cost_per_conversion
FROM campaign
WHERE campaign.advertising_channel_type = 'VIDEO'
  AND metrics.impressions > 0
  AND segments.date BETWEEN '{start}' AND '{end}'
ORDER BY segments.date DESC
"""

GAQL_CAMPAIGN_SUMMARY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign.advertising_channel_type,
  campaign.advertising_channel_subtype,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value,
  metrics.video_views
FROM campaign
WHERE campaign.advertising_channel_type = 'VIDEO'
  AND metrics.impressions > 0
  AND segments.date DURING LAST_90_DAYS
"""


class GoogleAdsNotConfigured(Exception):
    """Raised when env credentials/developer token are missing."""


class GoogleAdsError(Exception):
    """Raised when the API rejects the call (auth, permission, quota)."""


def is_configured() -> bool:
    return bool(
        settings.GOOGLE_ADS_DEVELOPER_TOKEN
        and settings.GOOGLE_CLIENT_ID
        and settings.GOOGLE_CLIENT_SECRET
        and (settings.GOOGLE_REFRESH_TOKEN)
        and (settings.GOOGLE_ADS_CUSTOMER_ID or settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID)
    )


def missing_requirements() -> list[str]:
    checks = {
        "GOOGLE_ADS_DEVELOPER_TOKEN (Basic access approved)": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": settings.GOOGLE_CLIENT_SECRET,
        "GOOGLE_REFRESH_TOKEN (or complete OAuth flow)": settings.GOOGLE_REFRESH_TOKEN,
        "GOOGLE_ADS_CUSTOMER_ID": settings.GOOGLE_ADS_CUSTOMER_ID or settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
    }
    return [k for k, v in checks.items() if not v]


@dataclass
class AdsRow:
    campaign_id: str
    campaign_name: str
    status: str
    channel_type: str
    channel_subtype: str
    format_key: str
    date: str | None
    impressions: int
    clicks: int
    cost_units: float      # currency units (converted from micros)
    conversions: float
    conversion_value: float
    video_views: int
    video_view_rate: float
    ctr: float
    avg_cpc: float
    avg_cpv: float
    cost_per_conversion: float


def _load_client():
    if not is_configured():
        raise GoogleAdsNotConfigured(
            "Google Ads API not fully configured. Missing: " + "; ".join(missing_requirements())
        )
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError as e:  # pragma: no cover
        raise GoogleAdsError(
            "google-ads client library is not installed. Run: pip install google-ads"
        ) from e
    credentials = {
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": get_access_token_from_refresh.__globals__["get_stored_refresh_token"](),
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(credentials)


def _classify_format(subtype: str, name: str) -> str:
    base = SUBTYPE_TO_FORMAT.get(subtype, "in_stream")
    if base == "in_stream":
        lowered = name.lower()
        if "short" in lowered:
            return "shorts"
        if "feed" in lowered or "discovery" in lowered:
            return "in_feed"
    return base


def _row_to_ads_row(row, with_date: bool) -> AdsRow:
    camp = row.campaign
    met = row.metrics
    date = str(row.segments.date) if with_date else None
    return AdsRow(
        campaign_id=str(camp.id),
        campaign_name=str(camp.name),
        status=str(camp.status).split(".")[-1] if str(camp.status) else "UNKNOWN",
        channel_type=str(camp.advertising_channel_type),
        channel_subtype=str(camp.advertising_channel_subtype or ""),
        format_key=_classify_format(str(camp.advertising_channel_subtype or ""), str(camp.name)),
        date=date,
        impressions=int(met.impressions),
        clicks=int(met.clicks),
        cost_units=float(met.cost_micros) / 1_000_000.0,
        conversions=float(met.conversions),
        conversion_value=float(met.conversions_value),
        video_views=int(met.video_views),
        video_view_rate=float(met.video_view_rate),
        ctr=float(met.ctr),
        avg_cpc=float(met.average_cpc) / 1_000_000.0,
        avg_cpv=float(met.average_cpv) / 1_000_000.0,
        cost_per_conversion=float(met.cost_per_conversion) / 1_000_000.0,
    )


def fetch_daily_performance(start: str, end: str) -> list[AdsRow]:
    """Daily rows for all VIDEO campaigns between ISO dates (inclusive)."""
    client = _load_client()
    ga = client.get_service("GoogleAdsService")
    customer_id = (settings.GOOGLE_ADS_CUSTOMER_ID or settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID).replace("-", "")
    query = GAQL_DAILY.format(start=start, end=end)
    try:
        stream = ga.search(customer_id=customer_id, query=query)
        rows = [_row_to_ads_row(r, with_date=True) for r in stream]
        logger.info("Google Ads: fetched %d daily rows for %s..%s", len(rows), start, end)
        return rows
    except Exception as e:
        # google.ads.googleads.errors.GoogleAdsException exposes failure list
        msg = str(e)
        if "PERMISSION_DENIED" in msg or "USER_PERMISSION" in msg:
            raise GoogleAdsError(
                "Permission denied — the authenticated Google account cannot access this "
                "customer id, or the developer token lacks approved access."
            ) from e
        if "AUTHENTICATION_ERROR" in msg or "invalid_grant" in msg:
            raise GoogleAdsError("Authentication failed — refresh the OAuth connection.") from e
        if "QUOTA" in msg or "RESOURCE_EXHAUSTED" in msg:
            raise GoogleAdsError("Google Ads API quota exhausted — retry later.") from e
        raise GoogleAdsError(f"Google Ads API error: {msg[:400]}") from e


def test_connection() -> dict:
    """Attempt a minimal summary query; returns an honest status dict."""
    try:
        client = _load_client()
    except (GoogleAdsNotConfigured, GoogleAdsError) as e:
        return {"ok": False, "status": "not_configured", "detail": str(e)}
    ga = client.get_service("GoogleAdsService")
    customer_id = (settings.GOOGLE_ADS_CUSTOMER_ID or settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID).replace("-", "")
    try:
        stream = ga.search(customer_id=customer_id, query=GAQL_CAMPAIGN_SUMMARY)
        count = sum(1 for _ in stream)
        return {"ok": True, "status": "connected", "video_campaigns_last_90d": count,
                "customer_id": customer_id}
    except Exception as e:
        return {"ok": False, "status": "error", "detail": str(e)[:400]}
