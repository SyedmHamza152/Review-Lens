"""Google OAuth 2.0 flow (authorization-code, offline access).

Scopes: userinfo.email (identity) + adwords (Google Ads reporting).
The refresh token is stored encrypted via app.core.security; it is never
returned to the frontend. The flow supports two redirect styles:
  * local development: http://localhost:8321/api/v1/oauth/google/callback
  * sandbox preview: set OAUTH_REDIRECT_URI to the preview URL + same path
"""
from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

import requests

from app.core.config import settings
from app.core.security import encrypt_secret, decrypt_secret

logger = logging.getLogger(__name__)

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/adwords",
]

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

_states: set[str] = set()


class OAuthNotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def build_authorization_url() -> tuple[str, str]:
    """Return (authorization_url, state). State is validated on callback."""
    if not is_configured():
        raise OAuthNotConfigured(
            "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not configured (backend/.env)."
        )
    state = secrets.token_urlsafe(24)
    _states.add(state)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}", state


def consume_state(state: str) -> bool:
    if state in _states:
        _states.discard(state)
        return True
    return False


def exchange_code(code: str) -> dict:
    """Exchange authorization code for tokens. Returns token payload."""
    if not is_configured():
        raise OAuthNotConfigured("OAuth client is not configured.")
    resp = requests.post(TOKEN_ENDPOINT, data={
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=15)
    resp.raise_for_status()
    tokens = resp.json()
    return {
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token", ""),
        "expires_in": int(tokens.get("expires_in", 3600)),
        "scope": tokens.get("scope", ""),
    }


def refresh_access_token(refresh_token: str) -> dict:
    if not is_configured():
        raise OAuthNotConfigured("OAuth client is not configured.")
    resp = requests.post(TOKEN_ENDPOINT, data={
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_userinfo(access_token: str) -> dict:
    resp = requests.get(USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_stored_refresh_token() -> str:
    return settings.GOOGLE_REFRESH_TOKEN or ""


def get_access_token_from_refresh() -> str:
    """Mint an access token from the configured/stored refresh token."""
    rt = get_stored_refresh_token()
    if not rt:
        raise OAuthNotConfigured("No refresh token available — complete the OAuth flow first.")
    return refresh_access_token(rt).get("access_token", "")


def encrypt_tokens(tokens: dict) -> dict:
    return {
        "access_token_encrypted": encrypt_secret(tokens.get("access_token", "")),
        "refresh_token_encrypted": encrypt_secret(tokens.get("refresh_token", "")),
    }


def decrypt_refresh_token(encrypted: str) -> str:
    return decrypt_secret(encrypted)
