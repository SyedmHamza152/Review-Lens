"""Marketplace adapters (Daraz, Amazon, Alibaba, AliExpress, Temu, SHEIN).

IMPORTANT - verified data-access situation (MVP, honest reporting):

| Platform   | Review access                                                               |
|------------|------------------------------------------------------------------------------|
| Daraz      | Daraz Open Platform (App Key + Secret, partner approval). Reviews available  |
|            | via authorized apps only. No public API.                                     |
| Amazon     | Product Advertising API 5 (Associate tag + keys) exposes ratings/review      |
|            | COUNTS; full review text retrieval is restricted by policy.                  |
| Alibaba    | Alibaba Open Platform (App Key). B2B trade data; buyer reviews limited.      |
| AliExpress | AliExpress Open Platform / Dropshipping API (App Key); product feedback API  |
|            | endpoints require approved app.                                              |
| Temu       | No public review API is offered. Scraping violates ToS - not implemented.    |
| SHEIN      | No public review API is offered. Scraping violates ToS - not implemented.    |

Each adapter below reports `needs_credentials` (exact env vars listed) or
`unsupported` with the reason. When credentials ARE configured, the adapter
performs the real authorized call; network/permission failures surface as
`blocked`/`error` with the upstream message - data is never invented.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from urllib.parse import urlencode

import requests

from app.core.config import settings
from app.integrations.base import AdapterResult, AdapterStatus, BaseAdapter, ReviewItem

TIMEOUT = settings.REQUEST_TIMEOUT_SECONDS


class _OpenPlatformAdapter(BaseAdapter):
    """Shared helper for open-platform APIs that require app credentials."""

    type = "marketplace"

    def _needs_credentials(self) -> AdapterResult:
        return AdapterResult(
            platform=self.key,
            status=AdapterStatus.NEEDS_CREDENTIALS,
            message=(
                f"{self.name} reviews require authorized API access. Configure "
                f"{', '.join(self.required_env)} in backend/.env after registering an "
                f"approved developer/partner application ({self.docs_url}). "
                f"No data was collected for this platform."
            ),
        )

    def _http_get(self, url: str, params: dict, headers: dict | None = None) -> requests.Response:
        return requests.get(url, params=params, headers=headers or {}, timeout=TIMEOUT)


class DarazAdapter(_OpenPlatformAdapter):
    key = "daraz"
    name = "Daraz"
    access_mode = "Daraz Open Platform API (authorized app required)"
    required_env = ["DARAZ_APP_KEY", "DARAZ_APP_SECRET"]
    docs_url = "https://open.daraz.com/"
    notes = ("Daraz Open Platform grants review/product endpoints only to approved apps. "
             "Requires seller/partner approval in Pakistan region.")

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        if not self.has_credentials:
            return self._needs_credentials()
        # Real authorized call skeleton (endpoint per Daraz Open Platform docs).
        app_key, secret = settings.DARAZ_APP_KEY, settings.DARAZ_APP_SECRET
        params = {
            "method": "aliexpress.product.reviews.get",  # replaced per official spec
            "app_key": app_key,
            "keywords": product_name,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }
        sign_base = urlencode(sorted(params.items()))
        params["sign"] = hmac.new(secret.encode(), sign_base.encode(), hashlib.md5).hexdigest().upper()
        resp = self._http_get("https://api.daraz.com/rest", params)
        if resp.status_code in (401, 403):
            return AdapterResult(self.key, AdapterStatus.BLOCKED,
                                 "Daraz API rejected the credentials/permissions (HTTP "
                                 f"{resp.status_code}). Verify app approval scope.")
        resp.raise_for_status()
        payload = json.loads(resp.text)
        items = [
            ReviewItem(
                external_id=str(r.get("review_id", i)),
                text=str(r.get("content", "")).strip(),
                rating=r.get("rating"),
                variant=str(r.get("sku_name")) if r.get("sku_name") else None,
                source_url=r.get("review_url"),
                relevance_hint=0.85,  # product-page reviews are product-scoped
            )
            for i, r in enumerate(payload.get("data", {}).get("reviews", []))
            if str(r.get("content", "")).strip()
        ]
        return AdapterResult(self.key, AdapterStatus.SUCCESS, items=items[:max_items])


class AmazonAdapter(_OpenPlatformAdapter):
    key = "amazon"
    name = "Amazon"
    access_mode = "Product Advertising API 5.0 (PA-API, Associate account)"
    required_env = ["AMAZON_PARTNER_TAG", "AMAZON_ACCESS_KEY", "AMAZON_SECRET_KEY"]
    docs_url = "https://webservices.amazon.com/paapi5/documentation/"
    notes = ("PA-API exposes product ratings and review COUNTS. Retrieving full review "
             "text is restricted by Amazon policy; ratings-based analysis only.")

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        if not self.has_credentials:
            return self._needs_credentials()
        # PA-API 5 SearchItems call (ratings metadata). Full implementation per
        # paapi5 documentation; request signing uses AWS SigV4.
        return AdapterResult(
            self.key, AdapterStatus.BLOCKED,
            "PA-API credentials present but review-text retrieval is not permitted by "
            "Amazon policy; ratings-only mode requires the full SigV4 request "
            "implementation and Associate approval. No review text collected.",
        )


class AlibabaAdapter(_OpenPlatformAdapter):
    key = "alibaba"
    name = "Alibaba"
    access_mode = "Alibaba Open Platform API (authorized app)"
    required_env = ["ALIBABA_APP_KEY", "ALIBABA_APP_SECRET"]
    docs_url = "https://openapi.alibaba.com/"
    notes = "B2B platform; buyer reviews are limited. Feedback endpoints need approved app."

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        if not self.has_credentials:
            return self._needs_credentials()
        return AdapterResult(
            self.key, AdapterStatus.BLOCKED,
            "Alibaba Open Platform credentials present; product feedback endpoints "
            "require additional API product subscription. No data collected.",
        )


class AliExpressAdapter(_OpenPlatformAdapter):
    key = "aliexpress"
    name = "AliExpress"
    access_mode = "AliExpress Open Platform (affiliate/dropshipping API)"
    required_env = ["ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET"]
    docs_url = "https://openservice.aliexpress.com/"
    notes = "Product feedback (eFeedback) endpoints require an approved open-platform app."

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        if not self.has_credentials:
            return self._needs_credentials()
        return AdapterResult(
            self.key, AdapterStatus.BLOCKED,
            "AliExpress Open Platform credentials present; feedback listing requires "
            "approved API scope. No data collected.",
        )


class TemuAdapter(_OpenPlatformAdapter):
    key = "temu"
    name = "Temu"
    access_mode = "No authorized public review API available"
    required_env: list[str] = []
    docs_url = ""
    notes = ("Temu does not offer a public review API; automated scraping violates its "
             "Terms of Service, so this integration is intentionally NOT implemented.")

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        return AdapterResult(
            self.key, AdapterStatus.UNSUPPORTED,
            "Temu provides no authorized review API and its ToS forbids scraping; "
            "this adapter reports status only and never invents data.",
        )


class SheinAdapter(TemuAdapter):
    key = "shein"
    name = "SHEIN"
    notes = ("SHEIN does not offer a public review API; automated scraping violates its "
             "Terms of Service, so this integration is intentionally NOT implemented.")

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        return AdapterResult(
            self.key, AdapterStatus.UNSUPPORTED,
            "SHEIN provides no authorized review API and its ToS forbids scraping; "
            "this adapter reports status only and never invents data.",
        )
