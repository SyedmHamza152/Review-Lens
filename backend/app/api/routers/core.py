"""Health, auth (demo user), and settings endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import constants
from app.core.config import settings
from app.core.db import check_database, get_db
from app.integrations import google_ads_client, llm_client, youtube_client
from app.models.user import User
from app.schemas.common import SettingsUpdate
from app.services.demo_seeder import ensure_demo_user, reseed
from app.services.google_ads_service import integration_status

router = APIRouter(tags=["health", "settings"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "ok" if check_database() else "error",
        "youtube": {"configured": youtube_client.is_configured(),
                    "quota_used_process": youtube_client.quota_state.used},
        "google_ads": integration_status(),
        "google_oauth": {"configured": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)},
        "llm": {"engine": "ollama" if llm_client.ollama_available() else "rule_based_fallback",
                "model": llm_client.ollama_model_name() if llm_client.ollama_available() else None},
        "task_queue": settings.TASK_QUEUE,
    }


@router.get("/auth/me")
def auth_me(db: Session = Depends(get_db)):
    user = ensure_demo_user(db)
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "mode": "single-user demo (OAuth identity flow implemented for Google connection)",
    }


def _get_user(db: Session) -> User:
    return ensure_demo_user(db)


@router.get("/settings")
def get_settings_api(db: Session = Depends(get_db)):
    user = _get_user(db)
    return {
        "currency": user.currency,
        "market": user.market,
        "supported_currencies": constants.SUPPORTED_CURRENCIES,
        "supported_markets": list(constants.MARKET_CITIES.keys()),
        "google_ads": integration_status(),
        "youtube": {"configured": youtube_client.is_configured()},
        "oauth": {"configured": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
                  "redirect_uri": settings.OAUTH_REDIRECT_URI},
    }


@router.put("/settings")
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    user = _get_user(db)
    if payload.currency:
        if payload.currency not in constants.SUPPORTED_CURRENCIES:
            raise HTTPException(422, f"Unsupported currency. Choose one of {constants.SUPPORTED_CURRENCIES}")
        user.currency = payload.currency
    if payload.market:
        if payload.market not in constants.MARKET_CITIES:
            raise HTTPException(422, f"Unsupported market. Choose one of {list(constants.MARKET_CITIES.keys())}")
        user.market = payload.market
    db.add(user)
    db.commit()
    return {"currency": user.currency, "market": user.market}


@router.post("/demo/seed")
def demo_seed(db: Session = Depends(get_db)):
    n = reseed(db)
    return {"status": "ok", "campaigns": n, "label": "SYNTHETIC DEMO DATA"}
