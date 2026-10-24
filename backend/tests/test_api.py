"""End-to-end API tests: health -> platforms -> search -> job -> report -> reviews -> export."""
import time
import uuid


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_platforms_listing(client):
    r = client.get("/api/platforms")
    assert r.status_code == 200
    platforms = r.json()["platforms"]
    keys = {p["key"] for p in platforms}
    # YouTube-only product decision: no other platform is exposed.
    assert keys == {"youtube"}
    yt = next(p for p in platforms if p["key"] == "youtube")
    assert yt["live_capability"] == "live"
    assert yt["status"] == "success"


def _search(client, name="Samsung Galaxy S25 Ultra", desc="512GB, Titanium Gray"):
    r = client.post("/api/search", json={
        "product_name": name, "description": desc, "include_sample": True,
    })
    assert r.status_code == 200
    return r.json()["job_id"]


def _wait_completed(client, job_id, timeout_s=60):
    for _ in range(timeout_s * 5):
        r = client.get(f"/api/jobs/{job_id}")
        if r.json()["status"] in ("completed", "failed"):
            return r.json()
        time.sleep(0.2)
    raise AssertionError("job did not finish in time")


def test_full_search_flow(client):
    job_id = _search(client)
    job = _wait_completed(client, job_id)
    assert job["status"] == "completed"
    assert job["progress"] == 100
    # YouTube-only product decision: every job uses exactly one platform.
    assert len(job["platforms"]) == 1
    assert job["platforms"][0]["platform"] == "youtube"
    # sample fallback marked transparently
    assert any(p["status"] in ("success", "success_sample") for p in job["platforms"])

    rep = client.get(f"/api/jobs/{job_id}/report").json()
    assert rep["totals"]["analyzed"] > 0
    # No 50-comment minimum: every analyzed comment counts toward the verdict.
    assert all(c["analysis_processed"] for c in rep["comparison"])
    assert abs(sum(d["pct"] for d in rep["distribution"]) - 100) < 1.5
    assert rep["languages"], "language breakdown missing"
    assert rep["verdict"]["label"] in {
        "Generally Positive", "Mostly Positive with Some Concerns", "Mixed Feedback",
        "Mostly Negative with Some Positives", "Generally Negative", "Insufficient Data",
    }
    assert rep["summary"].strip()


def test_review_filters(client):
    job_id = _search(client, "Wireless Earbuds Pro", "ANC, 30h battery")
    _wait_completed(client, job_id)
    base = client.get(f"/api/jobs/{job_id}/reviews?page_size=5").json()
    assert base["total"] > 0
    for lang in ("english", "roman_urdu", "urdu"):
        r = client.get(f"/api/jobs/{job_id}/reviews?language={lang}&page_size=5")
        assert r.status_code == 200
    r = client.get(f"/api/jobs/{job_id}/reviews?sentiment=negative&page_size=5")
    for item in r.json()["items"]:
        assert item["sentiment"] == "negative"


def test_spam_excluded_by_default(client):
    job_id = _search(client, "Running Sneakers", "EU 42")
    _wait_completed(client, job_id)
    r = client.get(f"/api/jobs/{job_id}/reviews?page_size=100").json()
    assert all(not item["is_spam"] for item in r["items"])


def test_exports(client):
    job_id = _search(client, "Air Fryer 5L", "digital display")
    _wait_completed(client, job_id)
    csv = client.get(f"/api/jobs/{job_id}/export.csv")
    assert csv.status_code == 200 and "text/csv" in csv.headers["content-type"]
    pdf = client.get(f"/api/jobs/{job_id}/export.pdf")
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"


def test_job_not_found(client):
    fake = str(uuid.uuid4())
    assert client.get(f"/api/jobs/{fake}").status_code == 404
    assert client.get(f"/api/jobs/{fake}/report").status_code == 404


def test_insufficient_data_verdict(client):
    # no sample data, no credentials -> zero usable reviews
    r = client.post("/api/search", json={
        "product_name": "Zebra Xyz100 Gadget", "include_sample": False})
    job_id = r.json()["job_id"]
    job = _wait_completed(client, job_id)
    assert job["status"] == "completed"
    rep = client.get(f"/api/jobs/{job_id}/report").json()
    assert rep["verdict"]["label"] == "Insufficient Data"
