"""Application configuration.

All settings come from environment variables (loaded from backend/.env when
present). Secrets are never hardcoded and never shipped to the frontend.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory (this file is backend/app/core/config.py)
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_NAME: str = "AdPilot AI"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "AI-powered Google & YouTube advertising budget optimizer"
    )
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "sandbox"  # sandbox | development | production

    # --- HTTP ---------------------------------------------------------------
    BACKEND_PORT: int = 8321

    # --- Database -----------------------------------------------------------
    # SQLite by default (zero-config development). For PostgreSQL use:
    
    SQLALCHEMY_DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'data' / 'adpilot.db'}"

    # --- Google / YouTube integrations --------------------------------------
    YOUTUBE_API_KEY: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REFRESH_TOKEN: str = ""
    GOOGLE_ADS_CUSTOMER_ID: str = ""
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str = ""
    # A Google Ads API developer token is still required by Google for any
    # API access (Basic access level is enough for reporting). See README.
    GOOGLE_ADS_DEVELOPER_TOKEN: str = ""
    OAUTH_REDIRECT_URI: str = "http://localhost:8321/api/v1/oauth/google/callback"

    # --- Security -----------------------------------------------------------
    # Used to derive the Fernet key that encrypts OAuth tokens at rest.
    SECRET_KEY: str = "adpilot-dev-secret-change-me"

    # --- Market defaults ------------------------------------------------------
    DEFAULT_CURRENCY: str = "PKR"
    DEFAULT_MARKET: str = "PK"  # Pakistan

    # --- AI ------------------------------------------------------------------
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "llama3.1"
    LLM_TIMEOUT_SECONDS: float = 2.5

    # --- Paths ---------------------------------------------------------------
    MODELS_DIR: str = str(PROJECT_ROOT / "models")
    DATA_DIR: str = str(BACKEND_DIR / "data")

    # --- Background work -----------------------------------------------------
    # inline  -> in-process thread pool (default; zero extra services)
    # celery  -> Celery workers (requires Redis; see docker-compose.yml)
    TASK_QUEUE: str = "inline"

    DEMO_USER_EMAIL: str = "demo@adpilot.ai"
    DEMO_USER_NAME: str = "AdPilot Demo User"

    @property
    def sqlalchemy_url(self) -> str:
        return self.SQLALCHEMY_DATABASE_URL


settings = Settings()
