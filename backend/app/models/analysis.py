from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.user import utcnow


class ProductAnalysis(Base):
    """Full output of the AI analysis + optimization pipeline for a product."""

    __tablename__ = "product_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)

    # STEP 1 — product understanding
    category: Mapped[str] = mapped_column(String(100), default="")
    product_type: Mapped[str] = mapped_column(String(100), default="")
    features: Mapped[list] = mapped_column(JSON, default=list)
    value_proposition: Mapped[str] = mapped_column(Text, default="")
    problems_solved: Mapped[list] = mapped_column(JSON, default=list)

    # STEP 2 — audience intelligence (inferences, not verified demographics)
    audience: Mapped[dict] = mapped_column(JSON, default=dict)

    # STEP 3 — marketing objective
    objective: Mapped[str] = mapped_column(String(60), default="")
    objective_rationale: Mapped[str] = mapped_column(Text, default="")

    # STEP 4 — competitor research summary
    competitor_summary: Mapped[dict] = mapped_column(JSON, default=dict)

    # STEP 5 — format suitability
    suitable_formats: Mapped[list] = mapped_column(JSON, default=list)

    # Provenance / honesty labels
    inference_method: Mapped[str] = mapped_column(String(60), default="rule_based")
    data_source_label: Mapped[str] = mapped_column(String(40), default="SYNTHETIC DEMO DATA")
    youtube_research_status: Mapped[str] = mapped_column(String(40), default="skipped")
    ads_history_status: Mapped[str] = mapped_column(String(40), default="skipped")

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped["Product"] = relationship()  # noqa: F821
    recommendation: Mapped["BudgetRecommendation | None"] = relationship(  # noqa: F821
        back_populates="analysis", uselist=False
    )


class AnalysisJob(Base):
    """Background analysis job with per-step progress (polled by the UI)."""

    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    analysis_id: Mapped[int | None] = mapped_column(nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|done|error
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    steps: Mapped[list] = mapped_column(JSON, default=list)  # [{key,label,status,detail}]
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
