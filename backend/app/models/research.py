from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class ResearchVideo(Base):
    """Public YouTube video discovered during competitor research (organic data)."""

    __tablename__ = "research_videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("product_analyses.id"), index=True)
    video_id: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(400), default="")
    channel_id: Mapped[str] = mapped_column(String(40), default="")
    channel_title: Mapped[str] = mapped_column(String(200), default="")
    published_at: Mapped[str] = mapped_column(String(40), default="")
    thumbnail_url: Mapped[str] = mapped_column(String(500), default="")

    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    channel_subscribers: Mapped[int] = mapped_column(Integer, default=0)

    # organic engagement (public stats) — NEVER ad spend/conversions
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    content_theme: Mapped[str] = mapped_column(String(120), default="")
    relevance: Mapped[float] = mapped_column(Float, default=0.0)

    data_source_label: Mapped[str] = mapped_column(String(40), default="LIVE DATA")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AudienceInsight(Base):
    """One inferred audience segment attached to an analysis."""

    __tablename__ = "audience_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("product_analyses.id"), index=True)
    segment_key: Mapped[str] = mapped_column(String(80), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    inference_method: Mapped[str] = mapped_column(String(60), default="rule_based")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
