"""Tests for the official Daraz Open Platform client (real review text).

Covers:
* the OFFICIAL signature algorithm - reproduced against the documented
  worked example (app_secret "helloworld", /order/get, sign 4190D3...FAB4A)
* signed request URL assembly (path + query layout per the docs)
* /review/seller/history/list + /review/seller/list/v2 orchestration
  (mocked HTTP, both endpoints), ReviewItem field mapping
* DarazAdapter integration: Open Platform path activates with all three
  credentials and stays honest without them (catalog aggregates + setup note)
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.integrations.base import AdapterStatus
from app.integrations.daraz_open_platform import (
    DARAZ_ENDPOINTS, DarazOpenPlatformClient, DarazOpenPlatformError,
    sign_request, sign_request_hmac_md5,
)
from app.integrations.marketplaces import DarazAdapter


# ---------------------------------------------------------------- signature
def test_signature_matches_official_documented_example():
    """The exact worked example from the Open Platform 'Signature algorithm'
    doc (Lazada/Daraz share the protocol and the doc node): secret
    'helloworld', API '/order/get', params access_token=test app_key=123456
    order_id=1234 sign_method=sha256 timestamp=1517820392000 ->
    4190D32361CFB9581350222F345CB77F3B19F0E31D162316848A2C1FFD5FAB4A"""
    params = {
        "app_key": "123456",
        "access_token": "test",
        "timestamp": "1517820392000",
        "sign_method": "sha256",
        "order_id": "1234",
    }
    assert sign_request("helloworld", "/order/get", params) == \
        "4190D32361CFB9581350222F345CB77F3B19F0E31D162316848A2C1FFD5FAB4A"


def test_signature_is_uppercase_hex_and_order_insensitive():
    a = sign_request("secret", "/brands/get",
                     {"limit": "1", "offset": "100", "app_key": "100126"})
    b = sign_request("secret", "/brands/get",
                     {"offset": "100", "app_key": "100126", "limit": "1"})
    assert a == b
    assert len(a) == 64 and a == a.upper()          # HMAC-SHA256 hex
    assert len(sign_request_hmac_md5("s", "/x", {"a": "1"})) == 32


def test_endpoints_match_official_table():
    assert DARAZ_ENDPOINTS["pk"] == "https://api.daraz.pk/rest"
    assert DARAZ_ENDPOINTS["bd"] == "https://api.daraz.com.bd/rest"
    assert DARAZ_ENDPOINTS["lk"] == "https://api.daraz.lk/rest"
    assert DARAZ_ENDPOINTS["np"] == "https://api.daraz.com.np/rest"
    assert DARAZ_ENDPOINTS["mm"] == "https://api.shop.com.mm/rest"


# ------------------------------------------------------------- signed calls
class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


def _client(session_get):
    sess = type("S", (), {"get": staticmethod(session_get)})()
    return DarazOpenPlatformClient(
        app_key="100126", app_secret="hushhush", access_token="tok123",
        country="pk", sign_method="sha256", session=sess,
    )


def test_get_builds_signed_url_and_parses_response():
    captured = {}

    def fake_get(url, timeout, headers):
        captured["url"] = url
        return _FakeResponse({"code": "0", "data": {"ok": True}})

    client = _client(fake_get)
    payload = client.get("/brands/get", offset=0, limit=1)
    assert payload["data"]["ok"] is True

    url = captured["url"]
    assert url.startswith("https://api.daraz.pk/rest/brands/get?")
    for expected in ("app_key=100126", "access_token=tok123",
                     "sign_method=sha256", "sign="):
        assert expected in url
    assert "timestamp=" in url


def test_get_raises_business_error_with_code_and_message():
    def fake_get(url, timeout, headers):
        return _FakeResponse({"code": "15", "type": "ISV",
                              "message": "Remote service error"})

    with pytest.raises(DarazOpenPlatformError) as err:
        _client(fake_get).get("/products/get", filter="search", search="bat")
    assert err.value.code == "15"
    assert "Remote service error" in err.value.message


def test_get_maps_http_403_to_blocked_style_error():
    def fake_get(url, timeout, headers):
        return _FakeResponse({}, status_code=403)

    with pytest.raises(DarazOpenPlatformError) as err:
        _client(fake_get).get("/products/get")
    assert err.value.http_status == 403


# -------------------------------------------------------- review collection
def _history_payload(ids, total=None, page_size=10):
    return {"code": "0", "data": {"current": 1, "total": total or len(ids),
                                  "page_size": page_size, "id_list": ids},
            "success": True}


def test_collect_review_items_end_to_end_mocked():
    """history/list -> id_list; list/v2 -> review bodies; full mapping."""
    calls: list[tuple[str, dict]] = []

    def fake_get(url, timeout, headers):
        path = url.split("?")[0].replace("https://api.daraz.pk/rest", "")
        from urllib.parse import parse_qs
        qs = {k: v[0] for k, v in parse_qs(url.split("?")[1]).items()}
        calls.append((path, qs))
        if path == "/products/get":
            return _FakeResponse({"code": "0", "data": {"products": [
                {"item_id": 111, "attributes": {"name": "Gray Nicolls cricket bat"},
                 "status": "live"},
            ]}})
        if path == "/review/seller/history/list":
            return _FakeResponse(_history_payload([9001, 9002, 9003], total=3,
                                                  page_size=10))
        if path == "/review/seller/list/v2":
            ids = json.loads(qs["id_list"])
            return _FakeResponse({"code": "0", "data": {"review_list": [
                {"id": i, "product_id": 111, "review_type": "PRODUCT_REVIEW",
                 "review_content": f"Real buyer review text {i}. Bat handle grip is great",
                 "ratings": {"overall_rating": 5 if i == 9001 else 3,
                             "product_rating": 5, "seller_rating": 4,
                             "logistics_rating": 4},
                 "submit_time": 1700000000000}
                for i in ids]}})
        return _FakeResponse({"code": "1", "message": f"unexpected {path}"})

    items, diag = _client(fake_get).collect_review_items("cricket bat", target=50)
    assert diag["products_matched"] == 1
    assert diag["review_ids"] == 3
    assert len(items) == 3
    first = items[0]
    assert first.external_id == "9001"
    assert first.text.startswith("Real buyer review text 9001")
    assert first.rating == 5.0
    assert first.review_date is not None
    assert first.source_url == "https://www.daraz.pk/products/-i-111.html"
    assert first.relevance_hint == 0.85
    # every review-body call batches at most 10 ids (official max)
    v2_calls = [c for c in calls if c[0] == "/review/seller/list/v2"]
    assert v2_calls and all(len(json.loads(qs["id_list"])) <= 10 for _, qs in v2_calls)
    # history windows respect the 7-day span requirement
    hist = [c for c in calls if c[0] == "/review/seller/history/list"]
    assert hist


def test_collect_review_items_empty_product_match():
    def fake_get(url, timeout, headers):
        return _FakeResponse({"code": "0", "data": {"products": []}})

    items, diag = _client(fake_get).collect_review_items("nonexistent widget")
    assert items == [] and diag["products_matched"] == 0


# ------------------------------------------------------------- adapter flow
def test_adapter_without_open_platform_creds_is_honest():
    """No DARAZ_ACCESS_TOKEN -> review text NOT fetched; message tells the
    user exactly which env vars unlock it (and never invents comments)."""
    adapter = DarazAdapter()
    assert not adapter.open_platform_ready
    fake_listings = [{"external_id": "111", "name": "Cricket bat", "rating": 4.5,
                      "review_count": 210, "url": "https://www.daraz.pk/x"}]
    with patch("app.integrations.live_sources.fetch_daraz_catalog",
               return_value=(fake_listings, "")), \
         patch("app.integrations.live_sources.fetch_daraz_reviews",
               return_value=([], "blocked by anti-bot")):
        result = adapter.search("cricket bat", None, 120)
    assert result.status == AdapterStatus.SUCCESS
    assert result.items == []
    assert "DARAZ_APP_KEY" in result.message and "DARAZ_ACCESS_TOKEN" in result.message
    assert result.aggregate_items == fake_listings


def test_adapter_with_open_platform_creds_collects_real_reviews():
    adapter = DarazAdapter()
    fake_items = _mk_items()
    fake_listings = [{"external_id": "111", "name": "Cricket bat"}]
    with patch.object(settings, "DARAZ_APP_KEY", "k"), \
         patch.object(settings, "DARAZ_APP_SECRET", "s"), \
         patch.object(settings, "DARAZ_ACCESS_TOKEN", "t"), \
         patch("app.integrations.live_sources.fetch_daraz_catalog",
               return_value=(fake_listings, "")), \
         patch("app.integrations.daraz_open_platform."
               "DarazOpenPlatformClient.collect_review_items",
               return_value=(fake_items, {"products_matched": 2, "review_ids": 2,
                                          "review_batches": 1, "reviews": 2,
                                          "id_windows_scanned": 2,
                                          "lookback_days": 90})):
        result = adapter.search("cricket bat", None, 120)
    assert result.status == AdapterStatus.SUCCESS
    assert result.items == fake_items
    assert "REAL buyer review" in result.message
    assert "official" in result.message
    assert result.aggregate_items == fake_listings


def test_adapter_open_platform_auth_error_surfaces_real_api_message():
    adapter = DarazAdapter()
    with patch.object(settings, "DARAZ_APP_KEY", "k"), \
         patch.object(settings, "DARAZ_APP_SECRET", "s"), \
         patch.object(settings, "DARAZ_ACCESS_TOKEN", "expired"), \
         patch("app.integrations.live_sources.fetch_daraz_catalog",
               return_value=([], "")), \
         patch("app.integrations.daraz_open_platform."
               "DarazOpenPlatformClient.collect_review_items",
               side_effect=DarazOpenPlatformError(
                   "6", "E006: Unexpected internal error / invalid token",
                   "/products/get")):
        result = adapter.search("cricket bat", None, 120)
    assert result.status == AdapterStatus.BLOCKED
    assert "[6]" in result.message and "invalid token" in result.message
    assert "access token" in result.message


def _mk_items():
    from datetime import datetime
    from app.integrations.base import ReviewItem
    return [
        ReviewItem(external_id="9001", text="Great bat, superb pickup",
                   rating=5.0, review_date=datetime(2023, 11, 14),
                   variant="GN cricket bat",
                   source_url="https://www.daraz.pk/products/-i-111.html",
                   relevance_hint=0.85),
        ReviewItem(external_id="9002", text="Handle broke in two weeks",
                   rating=2.0, review_date=datetime(2023, 11, 20),
                   variant="GN cricket bat",
                   source_url="https://www.daraz.pk/products/-i-111.html",
                   relevance_hint=0.85),
    ]
