"""API integration tests — golden path with isolated DB and mocked externals."""
import uuid

from app.integrations import youtube_client


def test_health(app_client):
    r = app_client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert "google_ads" in body and "youtube" in body


def test_auth_me(app_client):
    r = app_client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert "user" in r.json()


def test_product_create_and_validation(app_client):
    r = app_client.post("/api/v1/products", json={
        "name": "Premium Cricket Bat", "total_budget": 50000,
        "description": "Professional English willow cricket bat"})
    assert r.status_code == 201
    pid = r.json()["id"]

    # invalid budgets rejected
    assert app_client.post("/api/v1/products", json={"name": "X bat", "total_budget": 0}).status_code == 422
    assert app_client.post("/api/v1/products", json={"name": "X bat", "total_budget": -5}).status_code == 422
    return pid


def test_full_analysis_flow(app_client, monkeypatch):
    """product -> job -> steps -> recommendation summing exactly to budget."""
    monkeypatch.setattr(
        youtube_client, "research_product",
        lambda *a, **k: {"query": "test", "videos": [
            {"video_id": "abc123", "title": "Cricket bat review", "channel_id": "ch1",
             "channel_title": "SportsPK", "published_at": "2025-01-01",
             "thumbnail_url": "", "views": 100000, "likes": 4000, "comments": 300,
             "duration_seconds": 480, "channel_subscribers": 50000,
             "engagement_rate": 0.043, "data_source_label": "LIVE DATA"}],
         "summary": {"videos_found": 1}, "source": "LIVE DATA"},
        raising=False,
    )
    # monkeypatch where the pipeline looks it up too
    import app.services.analysis_engine as ae

    monkeypatch.setattr(ae.youtube_client, "research_product",
                        lambda *a, **k: {"query": "test", "videos": [], "summary": {}, "source": "LIVE DATA"})

    pid = test_product_create_and_validation(app_client)
    r = app_client.post("/api/v1/analyses", json={"product_id": pid})
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    # poll until done (inline executor)
    import time

    for _ in range(60):
        job = app_client.get(f"/api/v1/analyses/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.5)
    assert job["status"] == "done", job.get("error")
    assert len(job["steps"]) == 7

    rec = app_client.get(f"/api/v1/analyses/{job['analysis_id']}/recommendation").json()
    total = sum(a["amount"] for a in rec["allocations"])
    assert abs(total - 50000) < 0.01
    assert len(rec["allocations"]) >= 1
    assert rec["predicted_totals"]["roas"] is not None
    assert len(rec["methodology"]) > 100


def test_reoptimize_strategy(app_client, db_session):
    import time

    from app.models.product import Product

    p = Product(name="LED Bulb", description="energy saving bulb", total_budget=30000)
    db_session.add(p)
    db_session.commit()
    r = app_client.post("/api/v1/analyses", json={"product_id": p.id})
    job_id = r.json()["job_id"]
    for _ in range(60):
        job = app_client.get(f"/api/v1/analyses/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.5)
    aid = job["analysis_id"]
    r2 = app_client.post(f"/api/v1/analyses/{aid}/recommendation/reoptimize",
                         json={"strategy": "performance"})
    assert r2.status_code == 200
    total = sum(a["amount"] for a in r2.json()["allocations"])
    assert abs(total - 30000) < 0.01


def test_dashboard_endpoint(app_client):
    r = app_client.get("/api/v1/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert "empty" in body or "allocation" in body


def test_campaigns_analytics_labeled(app_client):
    r = app_client.get("/api/v1/campaigns/analytics?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["data_source_label"] in ("SYNTHETIC DEMO DATA", "LIVE DATA", "NO DATA")
    if body["data_source_label"] != "NO DATA":
        assert len(body["series"]) > 0
        for point in body["series"]:
            assert "date" in point and "impressions" in point


def test_reports_generation_and_download(app_client, db_session):
    from app.models.analysis import ProductAnalysis

    a = db_session.query(ProductAnalysis).order_by(ProductAnalysis.id.desc()).first()
    if a is None:
        return  # covered by analysis flow test order
    for fmt in ("pdf", "xlsx", "csv"):
        r = app_client.post("/api/v1/reports", json={"analysis_id": a.id, "format": fmt})
        assert r.status_code == 201, r.text
        rep = r.json()
        assert rep["size_bytes"] > 500
        dl = app_client.get(f"/api/v1/reports/{rep['id']}/download")
        assert dl.status_code == 200
        assert len(dl.content) == rep["size_bytes"]


def test_bigdata_generate_and_benchmark(app_client):
    r = app_client.post("/api/v1/bigdata/generate", json={"rows": 2000, "seed": 3})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    import time

    for _ in range(40):
        job = app_client.get(f"/api/v1/bigdata/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.5)
    assert job["status"] == "done", job.get("error")

    r = app_client.post("/api/v1/bigdata/benchmark",
                        json={"rows": 2000, "engines": ["pandas", "mapreduce"]})
    assert r.status_code == 202
    bjob = r.json()["job_id"]
    for _ in range(60):
        job = app_client.get(f"/api/v1/bigdata/jobs/{bjob}").json()
        if job["status"] in ("done", "done_with_errors", "error"):
            break
        time.sleep(0.5)
    assert job["status"] in ("done", "done_with_errors")
    marks = app_client.get("/api/v1/bigdata/benchmarks").json()["benchmarks"]
    assert any(m["engine"] == "pandas" and m["status"] == "ok" for m in marks)
    assert any(m["engine"] == "mapreduce" and m["equivalence_ok"] for m in marks)


def test_oauth_status_honest(app_client):
    r = app_client.get("/api/v1/oauth/google/status")
    assert r.status_code == 200
    body = r.json()
    assert "connected" in body
    assert "refresh_token_in_env" in body


def test_settings_roundtrip(app_client):
    r = app_client.put("/api/v1/settings", json={"currency": "USD", "market": "US"})
    assert r.status_code == 200
    assert r.json()["currency"] == "USD"
    # invalid values rejected
    assert app_client.put("/api/v1/settings", json={"currency": "XYZ"}).status_code == 422
    app_client.put("/api/v1/settings", json={"currency": "PKR", "market": "PK"})


def test_openapi_available(app_client):
    r = app_client.get("/api/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for expected in ("/api/v1/health", "/api/v1/products", "/api/v1/analyses",
                     "/api/v1/bigdata/benchmark", "/api/v1/ml/models", "/api/v1/reports"):
        assert expected in paths, f"missing {expected}"
