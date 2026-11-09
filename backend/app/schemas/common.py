"""Shared API schemas and helpers (Pydantic v2)."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


def paginate(items: list[Any], page: int = 1, size: int = 20) -> dict:
    total = len(items)
    start = (max(page, 1) - 1) * size
    return {"items": items[start:start + size], "total": total,
            "page": max(page, 1), "size": size}


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=300)
    total_budget: float = Field(gt=0, description="Total advertising budget in the selected currency")
    description: str = Field(default="", max_length=2000)
    currency: str = Field(default="PKR", max_length=8)
    market: str = Field(default="PK", max_length=4)


class SettingsUpdate(BaseModel):
    currency: str | None = None
    market: str | None = None


class ReoptimizeRequest(BaseModel):
    strategy: str = Field(default="balanced", pattern="^(balanced|performance|exploratory)$")


class BenchmarkRequest(BaseModel):
    rows: int = Field(ge=1000, le=10_000_000)
    engines: list[str] = Field(default=["pandas", "mapreduce", "spark"])


class GenerateDatasetRequest(BaseModel):
    rows: int = Field(ge=1000, le=10_000_000)
    seed: int = 42


class PredictRequest(BaseModel):
    format_key: str = Field(pattern="^(in_stream|shorts|in_feed)$")
    objective: str = "Sales / Conversions"
    category_key: str = "general"


class ReportRequest(BaseModel):
    analysis_id: int
    format: str = Field(pattern="^(pdf|xlsx|csv)$")
