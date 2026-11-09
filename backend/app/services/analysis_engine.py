"""Analysis pipeline — the 7-step AI workflow behind the progress page.

  1. Understanding product          (rule engine + optional Ollama)
  2. Identifying target audience    (inference, labeled as hypothesis)
  3. Selecting marketing objective  (decision matrix, explained)
  4. Researching YouTube market     (LIVE via YouTube Data API v3)
  5. Fetching advertising history   (Google Ads if connected, else demo data)
  6. Analyzing campaign performance (metrics engine + ML predictions)
  7. Running optimization           (SLSQP + UCB -> budget recommendation)

Every step writes progress to the AnalysisJob row so the UI polls REAL state —
fake progress is never shown.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import constants
from app.integrations import google_ads_client, llm_client, youtube_client
from app.models.analysis import AnalysisJob, ProductAnalysis
from app.models.ml import MLPrediction
from app.models.product import Product
from app.models.recommendation import BudgetRecommendation
from app.models.research import AudienceInsight, ResearchVideo
from app.services import rule_engine
from app.services.knowledge import classify_category

logger = logging.getLogger(__name__)

STEPS = [
    ("understand", "Understanding product"),
    ("audience", "Identifying target audience"),
    ("research", "Researching YouTube market"),
    ("ads_history", "Fetching advertising history"),
    ("performance", "Analyzing campaign performance"),
    ("optimize", "Running optimization"),
    ("recommend", "Generating recommendations"),
]


def _set_step(job: AnalysisJob, db: Session, idx: int, status: str = "running", detail: str = "") -> None:
    steps = list(job.steps or [])
    while len(steps) < len(STEPS):
        steps.append({"key": STEPS[len(steps)][0], "label": STEPS[len(steps)][1], "status": "pending", "detail": ""})
    steps[idx] = {"key": STEPS[idx][0], "label": STEPS[idx][1], "status": status, "detail": detail[:500]}
    job.steps = steps
    job.current_step = idx + 1
    job.progress = round((idx) / len(STEPS) * 100.0, 1)
    job.status = "running"
    db.add(job)
    db.commit()


def create_job(db: Session, product: Product) -> AnalysisJob:
    job = AnalysisJob(
        id=uuid.uuid4().hex,
        product_id=product.id,
        status="queued",
        steps=[{"key": k, "label": lbl, "status": "pending", "detail": ""} for k, lbl in STEPS],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_analysis(job_id: str) -> None:
    """Executed in the background pool. Creates its own DB session."""
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        _run(db, job_id)
    except Exception as e:
        logger.exception("Analysis job %s failed", job_id)
        job = db.get(AnalysisJob, job_id)
        if job:
            from app.models.user import utcnow as _utcnow

            job.status = "error"
            job.error = str(e)[:1000]
            job.finished_at = _utcnow()
            db.add(job)
            db.commit()
    finally:
        db.close()


def _run(db: Session, job_id: str) -> None:
    from app.models.user import utcnow
    from app.services.optimizer_service import run_optimization

    job = db.get(AnalysisJob, job_id)
    if not job:
        raise ValueError(f"job {job_id} not found")
    product = db.get(Product, job.product_id)
    if not product:
        raise ValueError(f"product {job.product_id} not found")

    job.status = "running"
    job.started_at = utcnow()
    db.commit()

    # ---- STEP 1: understand -------------------------------------------------
    _set_step(job, db, 0)
    llm = llm_client.generate_json(
        f"Product: {product.name}. Description: {product.description}. "
        'Return JSON with keys: product_type (string), features (list of up to 6 short strings), '
        'value_proposition (one sentence).'
    )
    understanding = rule_engine.understand_product(product.name, product.description, llm_result=llm)
    profile, profile_conf = classify_category(f"{product.name} {product.description}")
    _set_step(job, db, 0, status="done",
              detail=f"Category: {understanding['category']} ({understanding['inference_method']})")

    # ---- STEP 2: audience (+ objective selection) -----------------------------
    _set_step(job, db, 1)
    market = product.market or settings_market()
    audience = rule_engine.infer_audience(profile, market=market)
    audience["aov_estimate"] = understanding["aov_estimate"]
    audience["objective_bias"] = profile.objective_bias
    objective, rationale = rule_engine.select_objective(profile, product.total_budget)
    _set_step(job, db, 1, status="done", detail=f"Objective selected: {objective}")

    # ---- STEP 3: YouTube research -------------------------------------------
    _set_step(job, db, 2)
    research_status = "skipped"
    research_payload: dict = {}
    videos: list[dict] = []
    if youtube_client.is_configured():
        try:
            research_payload = youtube_client.research_product(product.name, product.description)
            videos = research_payload.get("videos", [])
            research_status = "live"
            _set_step(job, db, 2, status="done", detail=f"{len(videos)} public videos analyzed (LIVE DATA)")
        except Exception as e:
            logger.warning("YouTube research failed: %s", e)
            research_status = f"error: {str(e)[:150]}"
            _set_step(job, db, 2, status="done", detail=f"YouTube research unavailable: {str(e)[:120]}")
    else:
        _set_step(job, db, 2, status="done", detail="YOUTUBE_API_KEY not configured — research skipped")

    # ---- STEP 4: advertising history ----------------------------------------
    _set_step(job, db, 3)
    ads_status = "demo"
    if google_ads_client.is_configured():
        try:
            from app.services.google_ads_service import sync_campaigns

            n = sync_campaigns(db)
            ads_status = "live"
            _set_step(job, db, 3, status="done", detail=f"Synced {n} daily rows from Google Ads (LIVE DATA)")
        except Exception as e:
            ads_status = f"error: {str(e)[:150]}"
            logger.warning("Google Ads sync failed: %s", e)
            _set_step(job, db, 3, status="done", detail=f"Google Ads unavailable ({str(e)[:100]}) — using estimated campaign history")
    else:
        _set_step(job, db, 3, status="done",
                  detail="Google Ads not connected — estimated campaign history used (source labeled per section)")

    # ---- STEP 5: performance + persist analysis ------------------------------
    _set_step(job, db, 4)
    analysis = ProductAnalysis(
        product_id=product.id,
        category=understanding["category"],
        product_type=understanding["product_type"],
        features=understanding["features"],
        value_proposition=understanding["value_proposition"],
        problems_solved=understanding["problems_solved"],
        audience=audience,
        objective=objective,
        objective_rationale=rationale,
        competitor_summary=research_payload.get("summary", {}),
        suitable_formats=rule_engine.suitable_formats(profile),
        inference_method=understanding["inference_method"],
        data_source_label="LIVE DATA" if ads_status == "live" else "SYNTHETIC DEMO DATA",
        youtube_research_status=research_status,
        ads_history_status=ads_status,
        confidence=round(min(0.9, profile_conf + (0.15 if research_status == "live" else 0.0) + (0.15 if ads_status == "live" else 0.0)), 2),
    )
    db.add(analysis)
    db.flush()

    for v in videos[:120]:
        db.add(ResearchVideo(analysis_id=analysis.id, **{k: v[k] for k in (
            "video_id", "title", "channel_id", "channel_title", "published_at",
            "thumbnail_url", "views", "likes", "comments", "duration_seconds",
            "channel_subscribers", "engagement_rate", "data_source_label") if k in v}))
    for seg in audience.get("segments", []):
        db.add(AudienceInsight(
            analysis_id=analysis.id,
            segment_key=str(seg.get("key", seg.get("label", "segment")))[:80],
            payload=seg,
            inference_method=audience.get("inference_method", "rule_based"),
        ))
    db.commit()

    # ML predictions (best-effort)
    _persist_ml_predictions(db, analysis)

    # ---- STEP 5 done: persist analysis ---------------------------------------
    _set_step(job, db, 4, status="done",
              detail=f"Analysis stored — {len(videos)} research rows, formats ranked")

    # ---- STEP 6: optimization -------------------------------------------------
    _set_step(job, db, 5)
    rec = run_optimization(db, analysis, float(product.total_budget))
    _set_step(job, db, 5, status="done", detail=f"{len(rec.allocations)} allocations, confidence {rec.confidence:.0%}")

    # ---- STEP 7: recommendation ready -----------------------------------------
    _set_step(job, db, 6, status="done", detail=f"Recommendation #{rec.id} ready (sums to exactly {product.total_budget:,.0f} {product.currency})")

    job.analysis_id = analysis.id
    job.status = "done"
    job.progress = 100.0
    job.finished_at = utcnow()
    db.add(job)
    db.commit()


def _persist_ml_predictions(db: Session, analysis: ProductAnalysis) -> None:
    from app.ml.registry import load_predictor

    try:
        predictor = load_predictor()
        if not predictor:
            return
        text = f"{analysis.product.name} {analysis.product.description}"  # type: ignore[union-attr]
        profile, _ = classify_category(text)
        for key in constants.FORMAT_KEYS:
            preds = predictor(format_key=key, objective=analysis.objective, category_key=profile.key)
            for target, value in (preds or {}).items():
                db.add(MLPrediction(
                    analysis_id=analysis.id,
                    format_key=key,
                    target=target,
                    model_name=str(value.get("model", "")),
                    predicted_value=float(value.get("value", 0.0)),
                    features=value.get("features", {}),
                ))
        db.commit()
    except Exception as e:
        logger.warning("ML prediction persistence skipped: %s", e)


def settings_market() -> str:
    from app.core.config import settings as cfg

    return cfg.DEFAULT_MARKET


def latest_analysis(db: Session) -> ProductAnalysis | None:
    return db.execute(
        select(ProductAnalysis).order_by(ProductAnalysis.id.desc()).limit(1)
    ).scalar_one_or_none()


def latest_recommendation(db: Session, analysis_id: int) -> BudgetRecommendation | None:
    return db.execute(
        select(BudgetRecommendation)
        .where(BudgetRecommendation.analysis_id == analysis_id)
        .order_by(BudgetRecommendation.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def date_range(days: int = 90) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()
