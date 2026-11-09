from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class MLPrediction(Base):
    """One model prediction stored for auditability (labeled MODEL PREDICTION)."""

    __tablename__ = "ml_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("product_analyses.id"), nullable=True, index=True)
    format_key: Mapped[str] = mapped_column(String(20), default="")
    target: Mapped[str] = mapped_column(String(40), default="")
    model_name: Mapped[str] = mapped_column(String(60), default="")
    predicted_value: Mapped[float] = mapped_column(Float, default=0.0)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    data_source_label: Mapped[str] = mapped_column(String(40), default="MODEL PREDICTION")
    trained_on: Mapped[str] = mapped_column(String(40), default="synthetic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelRegistryEntry(Base):
    """Registry of trained models + evaluation metrics (mirrors metrics.json)."""

    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(40), index=True)
    model_name: Mapped[str] = mapped_column(String(60))
    is_best: Mapped[bool] = mapped_column(default=False)
    mae: Mapped[float] = mapped_column(Float, default=0.0)
    rmse: Mapped[float] = mapped_column(Float, default=0.0)
    r2: Mapped[float] = mapped_column(Float, default=0.0)
    train_rows: Mapped[int] = mapped_column(default=0)
    test_rows: Mapped[int] = mapped_column(default=0)
    trained_on: Mapped[str] = mapped_column(String(40), default="synthetic")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
