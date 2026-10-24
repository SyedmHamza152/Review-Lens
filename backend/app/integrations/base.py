"""Integration adapter contract.

Every platform implements BaseAdapter. A failed integration NEVER prevents
other platforms from returning results: adapters catch their own errors and
report honest status instead of raising.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AdapterStatus(str, Enum):
    SUCCESS = "success"
    NO_RESULTS = "no_results"
    NEEDS_CREDENTIALS = "needs_credentials"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


@dataclass
class ReviewItem:
    external_id: str
    text: str
    rating: float | None = None
    review_date: datetime | None = None
    variant: str | None = None
    author: str | None = None
    source_url: str | None = None
    # Marketplace items are collected from the product's own page (inherently
    # product-scoped); social items are keyword-matched and scored instead.
    relevance_hint: float | None = None


@dataclass
class AdapterResult:
    platform: str
    status: AdapterStatus
    message: str = ""
    items: list[ReviewItem] = field(default_factory=list)
    is_sample: bool = False
    data_source: str = "live"  # live | sample
    # Product LISTINGS with rating aggregates (e.g. Daraz storefront catalog:
    # name, avg rating, review count, price). NOT reviews - never scored for
    # sentiment; stored separately and shown as platform-side rating context.
    aggregate_items: list[dict] = field(default_factory=list)


class BaseAdapter(ABC):
    key: str = ""
    name: str = ""
    type: str = "marketplace"          # marketplace | social
    access_mode: str = ""              # human explanation of how data is accessed
    required_env: list[str] = []
    notes: str = ""
    docs_url: str = ""
    # honest capability without any credentials:
    #   live                  -> collects real data right now
    #   requires_credentials  -> real client coded; activates with env keys
    #   not_available         -> no compliant public API exists
    live_capability: str = "requires_credentials"

    # ------------------------------------------------------------------
    @property
    def has_credentials(self) -> bool:
        from app.core.config import settings
        if not self.required_env:
            return False
        return all(getattr(settings, env, None) for env in self.required_env)

    def status_for_listing(self) -> AdapterStatus:
        """Coarse status shown on the platforms page before any search."""
        if self.live_capability == "not_available":
            return AdapterStatus.UNSUPPORTED
        if self.required_env and not self.has_credentials:
            return AdapterStatus.NEEDS_CREDENTIALS
        return AdapterStatus.SUCCESS

    def search_with_retry(self, product_name: str, description: str | None,
                          max_items: int, retries: int = 2) -> AdapterResult:
        last: AdapterResult | None = None
        for attempt in range(retries + 1):
            try:
                return self.search(product_name, description, max_items)
            except Exception as exc:  # adapter isolation guarantee
                last = AdapterResult(
                    platform=self.key, status=AdapterStatus.ERROR,
                    message=f"{type(exc).__name__}: {exc}"[:400],
                )
                if attempt < retries:
                    time.sleep(0.6 * (2 ** attempt))  # exponential backoff
        return last  # type: ignore[return-value]

    @abstractmethod
    def search(self, product_name: str, description: str | None,
               max_items: int) -> AdapterResult:
        """Collect review items or report an honest, non-fatal status."""
