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

    # --- Sample corpus (tests/eval ONLY; the live app never uses it) ---
    ALLOW_SAMPLE_DATA: bool = True

    # --- Live credential-free sources (verified reachable from deployment) ---
    # Reddit text searches go through the public Arctic-Shift Reddit archive.
    REDDIT_SUBREDDITS: str = (
        "pakistan,PakGamers,Karachi,Lahore,Islamabad,pcgamingindia,"
        "gadgets,Android,apple,headphones,sneakers,technology"
    )
    REDDIT_LOOKBACK_DAYS: int = 540
    ARCTIC_MAX_REQUESTS: int = 16          # politeness cap per search job
    ARCTIC_MIN_INTERVAL_SECONDS: float = 2.0

    HN_MAX_STORIES: int = 8
    HN_COMMENTS_PER_STORY: int = 40

    DARAZ_CATALOG_MAX_ITEMS: int = 40

    # --- 50-comment minimum (product requirement) ---
    # A platform with fewer than this many REAL comments cannot support
    # reliable sentiment analysis; the report states that explicitly instead
    # of pretending. Platforms below the minimum are shown in the Comments
    # tab but excluded from verdict/aspects/comparison aggregation.
    MIN_COMMENTS_FOR_ANALYSIS: int = 50

    # --- YouTube live collection (public web API; official v3 when key set) ---
    YOUTUBE_MAX_VIDEOS: int = 10
    YOUTUBE_COMMENTS_PER_VIDEO: int = 40
    YOUTUBE_MAX_PAGES_PER_VIDEO: int = 6
    INNERTUBE_MIN_INTERVAL_SECONDS: float = 1.0

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

    # --- Daraz Open Platform (official seller-authorized review APIs) ---
    # Register at open.daraz.com: Create Account -> apply for an API category
    # -> App Console -> App Key/App Secret -> seller authorization -> token.
    # With all three set, real buyer reviews are fetched via
    # /review/seller/history/list + /review/seller/list/v2 (HMAC-SHA256
    # signed per the LAZOP protocol). Without them the platform shows
    # catalog aggregates only and says exactly what is missing.
    DARAZ_APP_KEY: str | None = None
    DARAZ_APP_SECRET: str | None = None
    DARAZ_ACCESS_TOKEN: str | None = None
    DARAZ_COUNTRY: str = "pk"          # pk | bd | lk | np | mm
    DARAZ_SIGN_METHOD: str = "sha256"  # sha256 (HMAC-SHA256) | hmac (HMAC-MD5)
    DARAZ_REVIEWS_TARGET: int = 50
    DARAZ_LOOKBACK_DAYS: int = 90      # platform limit for review history

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
