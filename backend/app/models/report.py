from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class GeneratedReport(Base):
    """An exported report artifact (PDF/XLSX/CSV) for an analysis."""

    __tablename__ = "generated_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("product_analyses.id"), index=True)
    format: Mapped[str] = mapped_column(String(10))  # pdf | xlsx | csv
    path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
