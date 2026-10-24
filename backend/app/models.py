"""SQLAlchemy ORM models.

Design notes:
- Source data (text_original), normalized analysis text (text_normalized),
  translation, and AI/derived results are stored SEPARATELY so the original
  collected comment is always preserved verbatim.
- (job_id, platform, external_id) unique constraint + normalized-text hash
  prevent the same review being counted twice.
- All types are portable between SQLite (sandbox) and PostgreSQL (production).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SearchJob(Base):
    __tablename__ = "search_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    platforms_requested: Mapped[str] = mapped_column(Text, default='["all"]')  # JSON list
    include_sample: Mapped[bool] = mapped_column(Boolean, default=True)

    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|completed|failed
    stage: Mapped[str] = mapped_column(String(60), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    data_mode: Mapped[str] = mapped_column(String(12), default="sample")  # live|sample|mixed|none

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobPlatformStatus(Base):
    __tablename__ = "job_platform_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("search_jobs.id"), index=True)
    platform_key: Mapped[str] = mapped_column(String(40))
    platform_name: Mapped[str] = mapped_column(String(80))
    # pending|searching|success|success_sample|no_results|needs_credentials|blocked|unsupported|error
    status: Mapped[str] = mapped_column(String(24), default="pending")
    message: Mapped[str] = mapped_column(Text, default="")
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of env vars
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("job_id", "platform_key", name="uq_job_platform"),)


class ProductMatch(Base):
    __tablename__ = "product_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("search_jobs.id"), index=True)
    canonical_name: Mapped[str] = mapped_column(String(300))
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tokens_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("search_jobs.id"), index=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    external_id: Mapped[str] = mapped_column(String(240), default="")
    dedup_hash: Mapped[str] = mapped_column(String(64), index=True)

    # Layered text: original (verbatim) -> normalized (analysis) -> translation (gloss)
    text_original: Mapped[str] = mapped_column(Text)
    text_normalized: Mapped[str] = mapped_column(Text, default="")
    translation: Mapped[str | None] = mapped_column(Text, nullable=True)

    language: Mapped[str] = mapped_column(String(16), default="unknown", index=True)
    language_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    language_uncertain: Mapped[bool] = mapped_column(Boolean, default=False)

    sentiment: Mapped[str] = mapped_column(String(12), index=True)  # positive|negative|neutral|mixed
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)  # -1..1
    sentiment_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sentiment_uncertain: Mapped[bool] = mapped_column(Boolean, default=False)
    sarcasm_suspect: Mapped[bool] = mapped_column(Boolean, default=False)

    complaint_scope: Mapped[str] = mapped_column(String(12), default="none")  # product|seller|both|none
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)

    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    variant: Mapped[str | None] = mapped_column(String(200), nullable=True)
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    aspects_json: Mapped[str] = mapped_column(Text, default="[]")
    drivers_json: Mapped[str] = mapped_column(Text, default="[]")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    data_source: Mapped[str] = mapped_column(String(12), default="live")  # live|sample

    __table_args__ = (
        UniqueConstraint("job_id", "platform", "external_id", name="uq_review_external"),
        Index("ix_reviews_job_sentiment", "job_id", "sentiment"),
        Index("ix_reviews_job_platform", "job_id", "platform"),
    )


class ReportCache(Base):
    __tablename__ = "report_cache"

    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("search_jobs.id"), primary_key=True)
    report_json: Mapped[str] = mapped_column(Text)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
