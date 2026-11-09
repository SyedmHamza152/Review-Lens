from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.user import utcnow


class BudgetRecommendation(Base):
    """Final budget allocation produced by the optimization engine."""

    __tablename__ = "budget_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("product_analyses.id"), index=True)

    total_budget: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="PKR")
    objective: Mapped[str] = mapped_column(String(60), default="")

    allocations: Mapped[list] = mapped_column(JSON, default=list)
    # [{format_key,label,share,amount,predicted:{impressions,clicks,conversions,revenue,cpa,roas,ctr,cpc_or_cpv},reason,confidence}]
    predicted_totals: Mapped[dict] = mapped_column(JSON, default=dict)
    methodology: Mapped[str] = mapped_column(Text, default="")
    algorithm: Mapped[str] = mapped_column(String(80), default="")
    optimizer_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    cold_start: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    data_source_label: Mapped[str] = mapped_column(String(40), default="MODEL PREDICTION")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped["ProductAnalysis"] = relationship(back_populates="recommendation")  # noqa: F821


class OptimizationRun(Base):
    """Audit trail for one optimizer execution (inputs/outputs/iterations)."""

    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("product_analyses.id"), index=True)
    algorithm: Mapped[str] = mapped_column(String(80), default="")
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    objective_value: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
