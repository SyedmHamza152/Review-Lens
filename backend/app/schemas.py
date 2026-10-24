"""Pydantic request/response schemas (API contracts)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PlatformStatusLiteral = Literal[
    "pending", "searching", "success", "success_sample", "no_results",
    "needs_credentials", "blocked", "unsupported", "error",
]
SentimentLiteral = Literal["positive", "negative", "neutral", "mixed"]


# ---------- Meta ----------
class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    nlp_pipeline: str
    database: str
    task_queue: str
    sample_data_allowed: bool
    time: str


class PlatformInfo(BaseModel):
    key: str
    name: str
    type: Literal["marketplace", "social"]
    status: PlatformStatusLiteral
    has_credentials: bool
    required_env: list[str]
    access_mode: str
    notes: str


# ---------- Search ----------
class SearchRequest(BaseModel):
    product_name: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    platforms: list[str] | None = None  # None / ["all"] -> all platforms
    include_sample: bool = True


class PlatformStatusOut(BaseModel):
    platform: str
    platform_name: str
    status: PlatformStatusLiteral
    message: str
    items_collected: int
    is_sample: bool
    requires_credentials: list[str] = []
    collected_at: datetime | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    product_name: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: str
    progress: int
    data_mode: str
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    platforms: list[PlatformStatusOut]
    totals: dict | None = None


# ---------- Report ----------
class VerdictOut(BaseModel):
    score: float
    label: str
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    mixed_pct: float
    avg_confidence: float
    methodology_note: str


class AspectOut(BaseModel):
    aspect: str
    label: str
    scope: Literal["product", "seller", "marketplace"]
    mentions: int
    positive: int
    negative: int
    neutral: int
    mixed: int
    avg_polarity: float


class ComparisonRowOut(BaseModel):
    platform: str
    platform_name: str
    total: int
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    mixed_pct: float
    avg_rating: float | None
    low_sample: bool
    is_sample: bool
    rank_by_positive: int | None
    top_positive_aspect: str | None
    top_complaint_aspect: str | None
    top_drivers: list[str] = []
    status: PlatformStatusLiteral
    message: str
    collected_at: datetime | None = None


class LanguageRowOut(BaseModel):
    language: str
    count: int
    pct: float
    positive: int
    negative: int
    neutral: int
    mixed: int


class TrendPointOut(BaseModel):
    period: str
    score: float
    count: int


class PhraseCount(BaseModel):
    phrase: str
    count: int
    detail: str = ""


class ReportResponse(BaseModel):
    job: dict
    platform_statuses: list[PlatformStatusOut]
    totals: dict
    verdict: VerdictOut
    distribution: list[dict]
    summary: str
    aspects: list[AspectOut]
    advantages: list[PhraseCount]
    complaints: list[PhraseCount]
    comparison: list[ComparisonRowOut]
    languages: list[LanguageRowOut]
    trends: list[TrendPointOut]
    methodology: dict


# ---------- Reviews ----------
class ReviewOut(BaseModel):
    id: int
    platform: str
    platform_name: str
    text_original: str
    translation: str | None
    language: str
    language_confidence: float
    language_uncertain: bool
    sentiment: SentimentLiteral
    sentiment_score: float
    sentiment_confidence: float
    sentiment_uncertain: bool
    sarcasm_suspect: bool
    complaint_scope: str
    aspects: list[dict]
    drivers: list[str]
    rating: float | None
    review_date: datetime | None
    variant: str | None
    source_url: str | None
    is_spam: bool
    relevance: float
    data_source: str


class PaginatedReviews(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ReviewOut]


class ChatContextRequest(BaseModel):
    job_id: str
    question: str = ""
