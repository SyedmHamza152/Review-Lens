"""Application configuration.

All secrets are read from environment variables (or a backend/.env file).
Never hard-code credentials. See backend/.env.example for the full list.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "Product Review Intelligence API"
    APP_VERSION: str = "1.0.0-mvp"
    NLP_PIPELINE_VERSION: str = "lexicon-context-v1.3"
    LOG_LEVEL: str = "INFO"

    # --- Database ---
    # PostgreSQL example: postgresql+psycopg://user:pass@localhost:5432/review_intel
    # (named SQLALCHEMY_DATABASE_URL to avoid clashing with Prisma's DATABASE_URL)
    SQLALCHEMY_DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'review_intel.db'}"

    # --- Search / pipeline tuning ---
    MAX_REVIEWS_PER_PLATFORM: int = 120
    RELEVANCE_THRESHOLD: float = 0.12
    SPAM_SIMILARITY_THRESHOLD: float = 0.92
    MIN_ANALYZED_FOR_VERDICT: int = 5
    LOW_SAMPLE_PLATFORM_THRESHOLD: int = 10
    BACKGROUND_WORKERS: int = 4
    REQUEST_TIMEOUT_SECONDS: int = 12

    # --- Sample corpus (clearly-labelled demonstration data) ---
    ALLOW_SAMPLE_DATA: bool = True

    # --- Optional transformer second-opinion engine (off in sandbox) ---
    TRANSFORMER_SENTIMENT_ENABLED: bool = False
    TRANSFORMER_SENTIMENT_MODEL: str = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

    # --- Platform credentials (all optional; adapters degrade honestly) ---
    REDDIT_CLIENT_ID: str | None = None
    REDDIT_CLIENT_SECRET: str | None = None
    REDDIT_USER_AGENT: str = "ProductReviewIntelligence/1.0 (MVP)"

    YOUTUBE_API_KEY: str | None = None

    X_BEARER_TOKEN: str | None = None

    FACEBOOK_ACCESS_TOKEN: str | None = None
    INSTAGRAM_ACCESS_TOKEN: str | None = None

    TIKTOK_CLIENT_KEY: str | None = None
    TIKTOK_CLIENT_SECRET: str | None = None

    DARAZ_APP_KEY: str | None = None
    DARAZ_APP_SECRET: str | None = None

    AMAZON_PARTNER_TAG: str | None = None
    AMAZON_ACCESS_KEY: str | None = None
    AMAZON_SECRET_KEY: str | None = None

    ALIBABA_APP_KEY: str | None = None
    ALIBABA_APP_SECRET: str | None = None

    ALIEXPRESS_APP_KEY: str | None = None
    ALIEXPRESS_APP_SECRET: str | None = None

    # --- Background queue ---
    # "inline" runs jobs in in-process background threads (sandbox default).
    # "celery" is the production option (requires Redis + Celery workers).
    TASK_QUEUE: str = "inline"
    REDIS_URL: str = "redis://localhost:6379/0"

    @property
    def is_sqlite(self) -> bool:
        return self.SQLALCHEMY_DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
