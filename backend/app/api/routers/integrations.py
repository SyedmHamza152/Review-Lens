"""Google OAuth, Google Ads connection, and YouTube research endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.integrations import google_ads_client, google_oauth, youtube_client
from app.models.google_connection import GoogleConnection
from app.schemas.common import paginate
from app.services.google_ads_service import integration_status, sync_campaigns

router = APIRouter(prefix="/oauth/google", tags=["oauth"])
ads_router = APIRouter(prefix="/google-ads", tags=["google-ads"])
yt_router = APIRouter(prefix="/youtube", tags=["youtube"])


# ------------------------------------------------------------------ OAuth
@router.get("/start")
def oauth_start():
    try:
        url, state = google_oauth.build_authorization_url()
    except google_oauth.OAuthNotConfigured as e:
        raise HTTPException(409, str(e))
    return {"authorization_url": url, "state": state,
            "redirect_uri": google_oauth.settings.OAUTH_REDIRECT_URI,
            "note": "Register the redirect URI in Google Cloud Console → Credentials."}


@router.get("/callback")
def oauth_callback(code: str | None = None, state: str | None = None, error: str | None = None,
                   db: Session = Depends(get_db)):
    if error:
        return RedirectResponse(f"/?oauth=error&reason={error}")
    if not code or not state:
        raise HTTPException(422, "missing code/state")
    if not google_oauth.consume_state(state):
        raise HTTPException(400, "invalid or expired OAuth state")
    try:
        tokens = google_oauth.exchange_code(code)
    except Exception as e:
        raise HTTPException(502, f"Token exchange failed: {e}")
    userinfo = {}
    try:
        userinfo = google_oauth.fetch_userinfo(tokens["access_token"])
    except Exception:
        pass

    conn = db.execute(select(GoogleConnection).order_by(GoogleConnection.id.desc())).scalars().first()
    if conn is None:
        conn = GoogleConnection()
    enc = google_oauth.encrypt_tokens(tokens)
    conn.google_email = userinfo.get("email", "")
    conn.scopes = tokens.get("scope", "")
    conn.access_token_encrypted = enc["access_token_encrypted"]
    if tokens.get("refresh_token"):  # Google only returns it on first consent
        conn.refresh_token_encrypted = enc["refresh_token_encrypted"]
    conn.token_expiry = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() + tokens.get("expires_in", 3600), tz=timezone.utc)
    conn.status = "connected"
    conn.is_active = True
    conn.last_checked_at = datetime.now(timezone.utc)
    db.add(conn)
    db.commit()
    return RedirectResponse("/?oauth=success")


@router.get("/status")
def oauth_status(db: Session = Depends(get_db)):
    conn = db.execute(select(GoogleConnection).order_by(GoogleConnection.id.desc())).scalars().first()
    base = {
        "oauth_client_configured": bool(google_oauth.is_configured()),
        "refresh_token_in_env": bool(google_oauth.get_stored_refresh_token()),
        "ads": integration_status(),
    }
    if not conn:
        return {**base, "connected": False, "status": "not_connected",
                "note": "No Google connection stored. Complete the OAuth flow or set GOOGLE_REFRESH_TOKEN."}
    return {**base, "connected": bool(conn.is_active), "status": conn.status,
            "google_email": conn.google_email,
            "scopes": conn.scopes.split(" ") if conn.scopes else [],
            "last_checked_at": str(conn.last_checked_at or "")}


@router.post("/disconnect")
def oauth_disconnect(db: Session = Depends(get_db)):
    conn = db.execute(select(GoogleConnection).order_by(GoogleConnection.id.desc())).scalars().first()
    if conn:
        conn.is_active = False
        conn.status = "disconnected"
        conn.access_token_encrypted = ""
        conn.refresh_token_encrypted = ""
        db.add(conn)
        db.commit()
    return {"status": "disconnected"}


@router.post("/test-connection")
def oauth_test():
    """Attempts a real minimal Google Ads call. Honest result only."""
    return google_ads_client.test_connection()


# ------------------------------------------------------------------ Google Ads
@ads_router.get("/status")
def ads_status():
    return integration_status()


@ads_router.post("/sync")
def ads_sync(db: Session = Depends(get_db)):
    try:
        n = sync_campaigns(db)
    except google_ads_client.GoogleAdsNotConfigured as e:
        raise HTTPException(409, str(e))
    except google_ads_client.GoogleAdsError as e:
        raise HTTPException(502, str(e))
    return {"status": "ok", "rows_synced": n, "label": "LIVE DATA" if n else "no rows"}


@ads_router.get("/campaigns")
def ads_campaigns(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db)):
    from app.models.campaign import Campaign

    camps = db.execute(select(Campaign).order_by(Campaign.id.desc())).scalars().all()
    items = []
    for c in camps:
        items.append({
            "id": c.id, "external_id": c.external_id, "name": c.name,
            "format_key": c.format_key, "status": c.status,
            "channel_type": c.channel_type, "objective": c.objective,
            "data_source_label": c.data_source_label,
        })
    return paginate(items, page, size)


@ads_router.get("/campaigns/{campaign_id}/performance")
def campaign_performance(campaign_id: int, db: Session = Depends(get_db)):
    from app.models.campaign import CampaignPerformance

    perfs = db.execute(
        select(CampaignPerformance)
        .where(CampaignPerformance.campaign_id == campaign_id)
        .order_by(CampaignPerformance.date)
    ).scalars().all()
    from app.services.metrics import MetricSet, merge_metric_sets

    daily: dict[str, MetricSet] = {}
    for p in perfs:
        ms = MetricSet(impressions=p.impressions, clicks=p.clicks, cost=p.cost_micros / 1e6,
                       conversions=p.conversions, conversion_value=p.conversion_value,
                       video_views=p.video_views, video_impressions=p.video_impressions)
        key = p.date.isoformat()
        if key in daily:
            daily[key] = merge_metric_sets([daily[key], ms])
        else:
            daily[key] = ms
    series = [{"date": k, **v.to_dict()} for k, v in sorted(daily.items())]
    label = perfs[0].data_source_label if perfs else "SYNTHETIC DEMO DATA"
    return {"campaign_id": campaign_id, "series": series, "data_source_label": label}


# ------------------------------------------------------------------ YouTube research
@yt_router.get("/research")
def youtube_research(product: str = Query(min_length=2), limit: int = Query(10, ge=1, le=25)):
    """LIVE public YouTube research for a product name (organic metrics only)."""
    try:
        return youtube_client.research_product(product, limit=limit)
    except youtube_client.YouTubeNotConfigured as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(502, f"YouTube Data API error: {str(e)[:300]}")


@yt_router.post("/research/{analysis_id}/refresh")
def youtube_research_refresh(analysis_id: int, db: Session = Depends(get_db)):
    """Re-run live YouTube research for an existing analysis and replace its rows."""
    from app.models.analysis import ProductAnalysis
    from app.models.research import ResearchVideo

    a = db.get(ProductAnalysis, analysis_id)
    if not a:
        raise HTTPException(404, "analysis not found")
    try:
        payload = youtube_client.research_product(a.product.name, a.product.description or "")
    except youtube_client.YouTubeNotConfigured as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(502, f"YouTube Data API error: {str(e)[:300]}")

    db.query(ResearchVideo).filter(ResearchVideo.analysis_id == analysis_id).delete()
    for v in payload.get("videos", [])[:15]:
        db.add(ResearchVideo(analysis_id=analysis_id, **{
            k: v[k] for k in (
                "video_id", "title", "channel_id", "channel_title", "published_at",
                "thumbnail_url", "views", "likes", "comments", "duration_seconds",
                "channel_subscribers", "engagement_rate", "data_source_label",
            ) if k in v}))
    a.competitor_summary = payload.get("summary", {})
    a.youtube_research_status = "live"
    db.add(a)
    db.commit()
    return {"status": "refreshed", "videos": len(payload.get("videos", [])),
            "data_source_label": "LIVE DATA"}
