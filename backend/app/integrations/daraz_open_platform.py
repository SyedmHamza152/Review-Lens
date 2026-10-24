"""Official Daraz Open Platform API client (real review text via authorized app).

This module implements the Daraz Open Platform protocol exactly as documented
at https://open.daraz.com (Daraz mirrors the Lazada Open Platform "LAZOP"
protocol - same signature algorithm, same common parameters, same request URL
layout; the doc node IDs are shared between the two platforms).

Protocol summary (verified against the official docs, 2026-10):

* Request URL:   https://api.daraz.pk/rest/{api_path}?{signed query}
  - Pakistan  https://api.daraz.pk/rest        Bangladesh https://api.daraz.com.bd/rest
  - Sri Lanka https://api.daraz.lk/rest        Nepal      https://api.daraz.com.np/rest
  - Myanmar   https://api.shop.com.mm/rest
* Common parameters (required on every call):
  app_key      - issued by the Open Platform console
  access_token - seller-authorization token (required for seller-scoped APIs)
  timestamp    - epoch MILLISECONDS, within 7200s of UTC server time
  sign_method  - hash algorithm used for the signature (sha256 / hmac)
  sign         - uppercase-hex HMAC signature
* Signature algorithm (official Python sample, transcribed):
      sort_dict = sorted(parameters)
      parameters_str = api + ''.join(f'{k}{parameters[k]}' for k in sort_dict)
      hmac_sha256(secret, parameters_str).hexdigest().upper()
  1. sort all params (except "sign" and byte-array params) by name, ASCII order
  2. concatenate key+value pairs -> "key1value1key2value2..."
  3. prepend the API path (e.g. "/review/seller/list/v2")
  4. HMAC with the App Secret (HMAC-SHA256 when sign_method=sha256,
     HMAC-MD5 when sign_method=hmac)
  5. uppercase hex digest
  Official worked example (Lazada/Daraz shared doc): with app_secret
  "helloworld", API "/order/get", params access_token=test app_key=123456
  order_id=1234 sign_method=sha256 timestamp=1517820392000  ->
  sign = 4190D32361CFB9581350222F345CB77F3B19F0E31D162316848A2C1FFD5FAB4A
  (reproduced verbatim by the unit test suite).

Seller-scoped review flow (the "Product Review API" section):

1. GET /products/get  (filter=search)      -> the seller's products matching
   the keyword, with item_id list. NOTE: Open Platform review APIs are
   seller-scoped - they return buyer reviews for the AUTHORIZED SELLER'S OWN
   listings. Cross-seller marketplace-wide review text is not offered by
   Daraz; the adapter reports this scope honestly.
2. GET /review/seller/history/list          -> review ID list per product
   (item_id required, start_time/end_time in ms - max 7-day span per call,
   history limited to the last 90 days, max 50 pages)
3. GET /review/seller/list/v2 (id_list)     -> full review bodies, max 10 ids
   per call: review_content, ratings.overall_rating, submit_time, id,
   product_id, review_type (PRODUCT_REVIEW | FOLLOW_UP_REVIEW)

Error handling: business errors come back as HTTP 200 with code != "0"
(JSON body: code, type ISV|ISP|platform, message). Signature problems
surface as ISV MissingParameter/IncompleteSignature style messages. We
surface the raw code+message to the user instead of guessing.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from app.core.config import settings
from app.integrations.base import ReviewItem

# ----------------------------------------------------------------------------
# Endpoints (official table, Daraz Open Platform API reference)
DARAZ_ENDPOINTS: dict[str, str] = {
    "pk": "https://api.daraz.pk/rest",       # Pakistan
    "bd": "https://api.daraz.com.bd/rest",   # Bangladesh
    "lk": "https://api.daraz.lk/rest",       # Sri Lanka
    "np": "https://api.daraz.com.np/rest",   # Nepal
    "mm": "https://api.shop.com.mm/rest",    # Myanmar
}

# Politeness / robustness
_CALL_INTERVAL_SECONDS = 0.35
_TRAFFIC_CONTROL_RETRIES = 2
_PDP_URL_TEMPLATE = "https://www.daraz.pk/products/-i-{item_id}.html"

# Window walk parameters (official limits: 7-day span, 90-day history)
_WINDOW_DAYS = 7
_LOOKBACK_DAYS_DEFAULT = 90
_MAX_PAGES_PER_WINDOW = 6


class DarazOpenPlatformError(Exception):
    """Business/API error returned by Daraz Open Platform (HTTP 200 + code!=0)."""

    def __init__(self, code: str, message: str, api_path: str = "",
                 http_status: int | None = None):
        self.code = str(code)
        self.message = message
        self.api_path = api_path
        self.http_status = http_status
        super().__init__(f"Daraz API {api_path} failed: [{code}] {message}")


def sign_request(secret: str, api_path: str, params: dict[str, Any]) -> str:
    """Official signature algorithm (documented Python sample, verbatim).

    Sorts parameter NAMES in ASCII order, concatenates key+value pairs,
    prepends the API path, HMACs with the app secret, uppercases the hex.
    `params` must already exclude "sign" (it is never part of its own
    signature) and contain only scalar values.
    """
    sorted_params = sorted(params)
    concatenated = "".join(f"{key}{params[key]}" for key in sorted_params)
    base = f"{api_path}{concatenated}"
    digest = hmac.new(secret.encode("utf-8"), base.encode("utf-8"),
                      digestmod=hashlib.sha256)
    return digest.hexdigest().upper()


def sign_request_hmac_md5(secret: str, api_path: str, params: dict[str, Any]) -> str:
    """sign_method=hmac variant (HMAC-MD5) - the value used in the official
    API-Explorer example URL (sign_method=hmac&sign=0CBC5F17...C3CF)."""
    sorted_params = sorted(params)
    concatenated = "".join(f"{key}{params[key]}" for key in sorted_params)
    base = f"{api_path}{concatenated}"
    digest = hmac.new(secret.encode("utf-8"), base.encode("utf-8"),
                      digestmod=hashlib.md5)
    return digest.hexdigest().upper()


class DarazOpenPlatformClient:
    """Signed HTTP client for the Daraz Open Platform (LAZOP protocol)."""

    def __init__(self, app_key: str, app_secret: str, access_token: str,
                 country: str = "pk", sign_method: str = "sha256",
                 session: requests.Session | None = None):
        if country not in DARAZ_ENDPOINTS:
            raise ValueError(
                f"Unsupported Daraz country '{country}'. "
                f"Valid: {', '.join(sorted(DARAZ_ENDPOINTS))}")
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self.country = country
        self.base_url = DARAZ_ENDPOINTS[country]
        self.sign_method = sign_method if sign_method in ("sha256", "hmac") else "sha256"
        self._session = session or requests.Session()
        self._last_call_ts = 0.0

    # ------------------------------------------------------------------ core
    def _sign(self, api_path: str, params: dict[str, Any]) -> str:
        if self.sign_method == "hmac":
            return sign_request_hmac_md5(self.app_secret, api_path, params)
        return sign_request(self.app_secret, api_path, params)

    def _pace(self) -> None:
        elapsed = time.monotonic() - self._last_call_ts
        if elapsed < _CALL_INTERVAL_SECONDS:
            time.sleep(_CALL_INTERVAL_SECONDS - elapsed)

    def get(self, api_path: str, **business_params: Any) -> dict[str, Any]:
        """Signed GET; returns the parsed JSON body; raises on API error."""
        params: dict[str, Any] = {
            "app_key": self.app_key,
            "access_token": self.access_token,
            "timestamp": str(int(time.time() * 1000)),
            "sign_method": self.sign_method,
        }
        params.update({k: v for k, v in business_params.items() if v is not None})

        sign = self._sign(api_path, params)
        query = urlencode({**{k: str(v) for k, v in params.items()}, "sign": sign})
        url = f"{self.base_url}{api_path}?{query}"

        last_error: Exception | None = None
        for attempt in range(_TRAFFIC_CONTROL_RETRIES + 1):
            self._pace()
            self._last_call_ts = time.monotonic()
            try:
                resp = self._session.get(url, timeout=settings.REQUEST_TIMEOUT_SECONDS + 10,
                                         headers={"Accept": "application/json"})
            except requests.RequestException as exc:
                last_error = exc
                if attempt < _TRAFFIC_CONTROL_RETRIES:
                    time.sleep(1.5 * (2 ** attempt))
                continue

            if resp.status_code in (401, 403):
                raise DarazOpenPlatformError(
                    str(resp.status_code),
                    "HTTP 401/403 - the endpoint refused the credentials or the "
                    "app lacks the API category approval for this call.",
                    api_path, resp.status_code)
            try:
                payload = resp.json()
            except ValueError as exc:
                raise DarazOpenPlatformError(
                    "BAD_JSON", f"Non-JSON response (HTTP {resp.status_code}).",
                    api_path) from exc

            code = str(payload.get("code", ""))
            if code not in ("0", "SUCCESS"):
                # TRAFFIC_CONTROL: back off and retry transparently
                if "TRAFFIC_CONTROL" in str(payload.get("message", "")) and \
                        attempt < _TRAFFIC_CONTROL_RETRIES:
                    time.sleep(2.0 * (2 ** attempt))
                    continue
                raise DarazOpenPlatformError(
                    code, str(payload.get("message", "Unknown error")),
                    api_path)
            return payload
        raise DarazOpenPlatformError(
            "NETWORK", f"Request failed after retries: {last_error}", api_path)

    # ------------------------------------------------------- seller products
    def search_products(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        """The authorized seller's own products matching `keyword`
        (GET /products/get, filter=search -> then filter_by? Daraz/Lazada
        GetProducts supports filter=search + search=<name>)."""
        payload = self.get("/products/get", filter="search", search=keyword,
                           limit=str(limit))
        data = payload.get("data") or {}
        products = data.get("products") or []
        out: list[dict[str, Any]] = []
        for p in products:
            item_id = p.get("item_id")
            if item_id is None:
                continue
            out.append({
                "item_id": str(item_id),
                "name": (p.get("attributes", {}) or {}).get("name")
                        or p.get("name") or "",
                "status": p.get("status"),
                "price": (p.get("skus", [{}])[0].get("price")
                          if p.get("skus") else None),
                "url": _PDP_URL_TEMPLATE.format(item_id=item_id),
            })
        return out

    # ----------------------------------------------------------- review APIs
    def list_review_ids(self, item_id: str, start_ms: int, end_ms: int,
                        current: int = 1) -> dict[str, Any]:
        """/review/seller/history/list - review id list for one product.
        start/end in epoch ms; span must be <= 7 days; history <= 90 days."""
        return self.get("/review/seller/history/list", item_id=str(item_id),
                        start_time=start_ms, end_time=end_ms, current=current)

    def get_reviews_by_ids(self, id_list: list[int | str]) -> list[dict[str, Any]]:
        """/review/seller/list/v2 - full review bodies for up to 10 ids."""
        if not id_list:
            return []
        payload = self.get("/review/seller/list/v2",
                           id_list=json.dumps([int(i) for i in id_list]))
        data = payload.get("data") or {}
        return data.get("review_list") or []

    # ----------------------------------------------------------- collection
    def collect_review_items(self, product_name: str,
                             target: int = 50,
                             lookback_days: int = _LOOKBACK_DAYS_DEFAULT,
                             product_limit: int = 10) -> tuple[list[ReviewItem], dict[str, Any]]:
        """Orchestrate products -> review-id windows -> review bodies.

        Returns (items, diagnostics). Diagnostics includes counts per stage so
        the adapter can tell the user exactly what happened (e.g. 'seller has
        no products matching the keyword' vs 'products found but 0 reviews in
        the last 90 days').
        """
        diag: dict[str, Any] = {
            "products_matched": 0, "id_windows_scanned": 0,
            "review_ids": 0, "review_batches": 0, "reviews": 0,
            "lookback_days": lookback_days,
        }
        products = self.search_products(product_name, limit=product_limit)
        diag["products_matched"] = len(products)
        if not products:
            return [], diag

        now = datetime.now(timezone.utc)
        earliest = now - timedelta(days=lookback_days)

        review_ids: list[int] = []
        for product in products:
            window_end = now
            while window_end > earliest:
                window_start = max(window_end - timedelta(days=_WINDOW_DAYS),
                                   earliest)
                page = 1
                while page <= _MAX_PAGES_PER_WINDOW:
                    result = self.list_review_ids(
                        product["item_id"],
                        int(window_start.timestamp() * 1000),
                        int(window_end.timestamp() * 1000),
                        current=page)
                    data = result.get("data") or {}
                    ids = [int(i) for i in (data.get("id_list") or [])]
                    diag["id_windows_scanned"] += 1
                    review_ids.extend(ids)
                    total = int(data.get("total") or 0)
                    page_size = int(data.get("page_size") or 10) or 10
                    if page * page_size >= total or not ids:
                        break
                    page += 1
                window_end = window_start

            if len(review_ids) >= target * 2:   # enough ids; stop walking products
                break

        # dedupe, keep order
        seen: set[int] = set()
        unique_ids = [i for i in review_ids if not (i in seen or seen.add(i))]
        diag["review_ids"] = len(unique_ids)
        if not unique_ids:
            return [], diag

        items: list[ReviewItem] = []
        product_names = {p["item_id"]: p.get("name") or "" for p in products}
        for offset in range(0, len(unique_ids), 10):
            if len(items) >= target:
                break
            batch = unique_ids[offset:offset + 10]
            reviews = self.get_reviews_by_ids(batch)
            diag["review_batches"] += 1
            for r in reviews:
                text = str(r.get("review_content") or "").strip()
                if not text:
                    continue
                submit_ms = r.get("submit_time") or r.get("create_time")
                when = (datetime.fromtimestamp(submit_ms / 1000, tz=timezone.utc)
                        if submit_ms else None)
                ratings = r.get("ratings") or {}
                product_id = str(r.get("product_id") or "")
                items.append(ReviewItem(
                    external_id=str(r.get("id") or f"{product_id}-{offset}"),
                    text=text,
                    rating=(float(ratings["overall_rating"])
                            if ratings.get("overall_rating") is not None else None),
                    review_date=when,
                    variant=product_names.get(product_id) or None,
                    source_url=_PDP_URL_TEMPLATE.format(item_id=product_id)
                    if product_id.isdigit() else None,
                    relevance_hint=0.85,  # product-page reviews are product-scoped
                ))
        diag["reviews"] = len(items)
        return items[:target], diag
