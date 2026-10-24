"""Marketplace adapters (Daraz, Amazon, Alibaba, AliExpress, Temu, SHEIN).

Verified data-access situation (re-verified from this deployment, 2026-10):

| Platform   | Review access                                                               |
|------------|------------------------------------------------------------------------------|
| Daraz      | LIVE rating AGGREGATES from the public storefront catalog JSON (avg rating,  |
|            | review count, price, seller - the same data daraz.pk search renders). Review |
|            | TEXT is currently blocked for datacenter deployments by Alibaba anti-bot     |
|            | (mtop RGV587 / cloud_ip_bl); an authorized Daraz Open Platform app           |
|            | (DARAZ_APP_KEY/DARAZ_APP_SECRET) unlocks it - implemented, activates w/ creds.|
| Amazon     | Product Advertising API 5 (Associate tag + keys) exposes ratings/review      |
|            | COUNTS; full review text retrieval is restricted by policy.                  |
| Alibaba    | Alibaba Open Platform (App Key). B2B trade data; buyer reviews limited.      |
| AliExpress | AliExpress Open Platform / Dropshipping API (App Key); product feedback API  |
|            | endpoints require approved app.                                              |
| Temu       | No public review API is offered. Scraping violates ToS - not implemented.    |
| SHEIN      | No public review API is offered. Scraping violates ToS - not implemented.    |

Adapters report honest status (`needs_credentials` with the exact env vars,
`blocked`, or `unsupported`) when access is not available. Data is never invented.
"""
from __future__ import annotations

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
    access_mode = ("LIVE rating aggregates from the public daraz.pk storefront catalog; "
                   "review TEXT via the official Daraz Open Platform API "
                   "(/review/seller/history/list + /review/seller/list/v2, "
                   "signed with HMAC-SHA256 per the LAZOP protocol)")
    required_env: list[str] = []   # catalog aggregates need no credentials
    # Review TEXT via the Open Platform needs a full seller-authorized app:
    optional_env = ["DARAZ_APP_KEY", "DARAZ_APP_SECRET", "DARAZ_ACCESS_TOKEN"]
    docs_url = "https://open.daraz.com/doc/api.htm"
    notes = ("Real product listings with average rating + review counts + prices "
             "collected live. Written review text uses the official Daraz Open "
             "Platform API and needs your authorized app credentials - set "
             "DARAZ_APP_KEY, DARAZ_APP_SECRET and DARAZ_ACCESS_TOKEN in "
             "backend/.env (register at open.daraz.com: Create Account -> "
             "apply for an API category -> App Console -> App Key/Secret -> "
             "seller authorization -> access token). Open Platform review APIs "
             "are seller-scoped: they return buyer reviews for the authorized "
             "seller's own listings.")
    live_capability = "live"

    @property
    def open_platform_ready(self) -> bool:
        return bool(settings.DARAZ_APP_KEY and settings.DARAZ_APP_SECRET
                    and settings.DARAZ_ACCESS_TOKEN)

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        from app.integrations.live_sources import fetch_daraz_catalog
        listings, err = fetch_daraz_catalog(product_name,
                                            settings.DARAZ_CATALOG_MAX_ITEMS)

        # ---- Official Open Platform review-text path (activates with creds) --
        if self.open_platform_ready:
            return self._search_open_platform(product_name, max_items, listings)

        # ---- No Open Platform credentials: aggregates + honest setup path ----
        if err and not listings:
            return AdapterResult(self.key, AdapterStatus.BLOCKED, err)

        result = AdapterResult(
            self.key,
            AdapterStatus.SUCCESS if listings else AdapterStatus.NO_RESULTS,
            (f"Collected {len(listings)} real Daraz PK catalog listing(s) with "
             "aggregate ratings/review counts from the public storefront JSON. "
             "Written review text is not shown because Daraz Open Platform "
             "credentials are not configured: Daraz only serves review text "
             "through its official Open Platform API. To enable real Daraz "
             "comments, set DARAZ_APP_KEY, DARAZ_APP_SECRET and "
             "DARAZ_ACCESS_TOKEN in backend/.env (register an app at "
             "open.daraz.com, then complete seller authorization).")
            if listings else "Daraz catalog returned no listings for this query.",
            data_source="live",
        )
        result.aggregate_items = listings

        if not listings:
            return result

        # Self-healing storefront attempt (currently blocked by Alibaba
        # anti-bot for datacenter IPs - reported honestly; resumes
        # automatically if Daraz reopens the endpoint).
        from app.integrations.live_sources import fetch_daraz_reviews
        review_items, note = fetch_daraz_reviews(listings, max_items)
        if review_items:
            result.items = review_items
            result.message += (f" | {len(review_items)} written review(s) collected "
                               "from the product pages.")
        elif note:
            result.message += f" | Written reviews: {note}"
        return result

    def _search_open_platform(self, product_name: str, max_items: int,
                              listings: list[dict] | None = None) -> AdapterResult:
        """Official signed Open Platform review collection (real comments)."""
        from app.integrations.daraz_open_platform import (
            DarazOpenPlatformClient, DarazOpenPlatformError,
        )
        client = DarazOpenPlatformClient(
            app_key=settings.DARAZ_APP_KEY or "",
            app_secret=settings.DARAZ_APP_SECRET or "",
            access_token=settings.DARAZ_ACCESS_TOKEN or "",
            country=settings.DARAZ_COUNTRY,
            sign_method=settings.DARAZ_SIGN_METHOD,
        )
        try:
            items, diag = client.collect_review_items(
                product_name, target=max(settings.DARAZ_REVIEWS_TARGET, max_items))
        except DarazOpenPlatformError as exc:
            return AdapterResult(
                self.key, AdapterStatus.BLOCKED,
                f"Daraz Open Platform rejected the {exc.api_path or 'API'} call: "
                f"[{exc.code}] {exc.message} Check that your app is approved for "
                "the Product Review API category and the access token is valid "
                "and not expired.",
                data_source="live",
            )
        except Exception as exc:  # network etc. - never lose catalog aggregates
            result = AdapterResult(
                self.key, AdapterStatus.SUCCESS,
                f"Open Platform collection error: {type(exc).__name__}: {exc}"[:220],
                data_source="live",
            )
            result.aggregate_items = listings or []
            return result

        result = AdapterResult(
            self.key,
            AdapterStatus.SUCCESS if items else AdapterStatus.NO_RESULTS,
            message="", data_source="live",
        )
        result.aggregate_items = listings or []
        if items:
            result.items = items
            result.message = (
                f"Collected {len(items)} REAL buyer review(s) through the official "
                f"Daraz Open Platform API ({diag['products_matched']} of the "
                "authorized seller's products matched, "
                f"{diag['review_ids']} review ids, {diag['review_batches']} "
                "batched lookups). Reviews are seller-scoped: they belong to the "
                "authorized seller's own listings, exactly as Daraz's Product "
                "Review API defines.")
        elif diag["products_matched"] == 0:
            result.message = (
                "Open Platform connected successfully, but the authorized "
                "seller has no products matching this keyword "
                f"('{product_name}'). Daraz review APIs are seller-scoped: "
                "reviews can only be fetched for the authorized seller's own "
                "listings. Daraz offers no cross-seller public review API.")
        else:
            result.message = (
                f"Open Platform connected successfully: {diag['products_matched']} "
                f"matching product(s), {diag['review_ids']} review id(s) found, "
                f"but 0 written review bodies (reviews older than 90 days are "
                "not served by /review/seller/history/list, or all matched "
                "reviews have no text).")
        return result


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
    live_capability = "not_available"
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
    live_capability = "not_available"
    notes = ("SHEIN does not offer a public review API; automated scraping violates its "
             "Terms of Service, so this integration is intentionally NOT implemented.")

    def search(self, product_name: str, description: str | None, max_items: int) -> AdapterResult:
        return AdapterResult(
            self.key, AdapterStatus.UNSUPPORTED,
            "SHEIN provides no authorized review API and its ToS forbids scraping; "
            "this adapter reports status only and never invents data.",
        )
