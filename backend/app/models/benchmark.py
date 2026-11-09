from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.user import utcnow


class DatasetBenchmark(Base):
    """One measured (never invented) benchmark result for one engine/size."""

    __tablename__ = "dataset_benchmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    engine: Mapped[str] = mapped_column(String(20))  # pandas | mapreduce | spark
    rows: Mapped[int] = mapped_column(Integer, default=0)
    dataset_size_mb: Mapped[float] = mapped_column(Float, default=0.0)
    generate_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    pipeline_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    peak_memory_mb: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok | error | skipped
    error: Mapped[str] = mapped_column(String(1000), default="")
    equivalence_ok: Mapped[bool] = mapped_column(default=True)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BenchmarkJob(Base):
    """Background benchmark job status (polled by the Big Data Lab UI)."""

    __tablename__ = "benchmark_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    rows: Mapped[int] = mapped_column(Integer, default=0)
    engines: Mapped[list] = mapped_column(JSON, default=list)
    current_step: Mapped[str] = mapped_column(String(200), default="")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(String(2000), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
