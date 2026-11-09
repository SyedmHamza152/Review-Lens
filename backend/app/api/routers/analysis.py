"""Products, analyses (7-step pipeline), recommendation, dashboard, analytics."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.analysis import AnalysisJob, ProductAnalysis
from app.models.campaign import Campaign, CampaignPerformance
from app.models.product import Product
from app.models.recommendation import BudgetRecommendation
from app.models.research import ResearchVideo
from app.schemas.common import ProductCreate, ReoptimizeRequest, paginate
from app.services import analysis_engine
from app.services.job_runner import submit
from app.services.metrics import MetricSet, merge_metric_sets
from app.services.optimizer_service import run_optimization

router = APIRouter(tags=["products", "analyses", "dashboard"])


# ------------------------------------------------------------------ products
@router.post("/products", status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    if payload.total_budget <= 0:
        raise HTTPException(422, "Total budget must be greater than zero")
    user = analysis_engine.ensure_demo_user(db) if hasattr(analysis_engine, "ensure_demo_user") else None
    product = Product(
        name=payload.name.strip(), description=payload.description.strip(),
        total_budget=payload.total_budget, currency=payload.currency, market=payload.market,
        user_id=user.id if user else None,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"id": product.id, "name": product.name, "total_budget": product.total_budget,
            "currency": product.currency, "market": product.market,
            "description": product.description}


@router.get("/products")
def list_products(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db)):
    products = db.execute(select(Product).order_by(Product.id.desc())).scalars().all()
    items = [{"id": p.id, "name": p.name, "total_budget": p.total_budget,
              "currency": p.currency, "market": p.market,
              "description": p.description, "created_at": str(p.created_at)} for p in products]
    return paginate(items, page, size)


# ------------------------------------------------------------------ analyses
@router.post("/analyses", status_code=202)
def create_analysis(payload: dict, db: Session = Depends(get_db)):
    product_id = payload.get("product_id")
    if not product_id:
        raise HTTPException(422, "product_id is required")
    product = db.get(Product, int(product_id))
    if not product:
        raise HTTPException(404, f"product {product_id} not found")
    if product.total_budget <= 0:
        raise HTTPException(422, "Product has no budget — update the product first")
    job = analysis_engine.create_job(db, product)
    submit(lambda: analysis_engine.run_analysis(job.id), name=f"analysis-{job.id}")
    return {"job_id": job.id, "status": job.status, "poll": f"/api/v1/analyses/jobs/{job.id}"}


@router.get("/analyses/jobs/{job_id}")
def analysis_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {
        "job_id": job.id, "status": job.status, "current_step": job.current_step,
        "steps": job.steps or [], "progress": job.progress, "error": job.error,
        "analysis_id": job.analysis_id,
    }


@router.get("/analyses/latest")
def latest_analysis(db: Session = Depends(get_db)):
    a = analysis_engine.latest_analysis(db)
    if not a:
        # 200 with an empty payload: "no analysis yet" is an expected state,
        # not an error — keeps the browser console clean on first load.
        return {"empty": True, "message": "No analysis yet — submit a product first."}
    return _analysis_payload(db, a)


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    a = db.get(ProductAnalysis, analysis_id)
    if not a:
        raise HTTPException(404, "analysis not found")
    return _analysis_payload(db, a)


def _analysis_payload(db: Session, a: ProductAnalysis) -> dict:
    videos = db.execute(
        select(ResearchVideo).where(ResearchVideo.analysis_id == a.id).order_by(ResearchVideo.views.desc())
    ).scalars().all()
    return {
        "id": a.id,
        "product": {"id": a.product.id, "name": a.product.name, "description": a.product.description,
                    "total_budget": a.product.total_budget, "currency": a.product.currency,
                    "market": a.product.market},
        "category": a.category,
        "product_type": a.product_type,
        "features": a.features,
        "value_proposition": a.value_proposition,
        "problems_solved": a.problems_solved,
        "audience": a.audience,
        "objective": a.objective,
        "objective_rationale": a.objective_rationale,
        "competitor_summary": a.competitor_summary,
        "suitable_formats": a.suitable_formats,
        "videos": [{"video_id": v.video_id, "title": v.title, "channel_title": v.channel_title,
                    "channel_id": v.channel_id, "views": v.views, "likes": v.likes,
                    "comments": v.comments, "duration_seconds": v.duration_seconds,
                    "engagement_rate": v.engagement_rate, "published_at": v.published_at,
                    "thumbnail_url": v.thumbnail_url,
                    "data_source_label": v.data_source_label} for v in videos],
        "inference_method": a.inference_method,
        "data_source_label": a.data_source_label,
        "youtube_research_status": a.youtube_research_status,
        "ads_history_status": a.ads_history_status,
        "confidence": a.confidence,
        "created_at": str(a.created_at),
    }


@router.get("/analyses/{analysis_id}/recommendation")
def get_recommendation(analysis_id: int, db: Session = Depends(get_db)):
    rec = analysis_engine.latest_recommendation(db, analysis_id)
    if not rec:
        raise HTTPException(404, "no recommendation for this analysis yet")
    return _rec_payload(rec)


@router.post("/analyses/{analysis_id}/recommendation/reoptimize")
def reoptimize(analysis_id: int, payload: ReoptimizeRequest, db: Session = Depends(get_db)):
    a = db.get(ProductAnalysis, analysis_id)
    if not a:
        raise HTTPException(404, "analysis not found")
    rec = run_optimization(db, a, float(a.product.total_budget), strategy=payload.strategy)
    return _rec_payload(rec)


def _rec_payload(rec: BudgetRecommendation) -> dict:
    return {
        "id": rec.id,
        "analysis_id": rec.analysis_id,
        "total_budget": rec.total_budget,
        "currency": rec.currency,
        "objective": rec.objective,
        "allocations": rec.allocations,
        "predicted_totals": rec.predicted_totals,
        "methodology": rec.methodology,
        "algorithm": rec.algorithm,
        "optimizer_meta": rec.optimizer_meta,
        "cold_start": rec.cold_start,
        "confidence": rec.confidence,
        "data_source_label": rec.data_source_label,
        "created_at": str(rec.created_at),
    }


# ------------------------------------------------------------------ dashboard & analytics
@router.get("/dashboard")
def dashboard(analysis_id: int | None = None, db: Session = Depends(get_db)):
    a = db.get(ProductAnalysis, analysis_id) if analysis_id else analysis_engine.latest_analysis(db)
    if not a:
        return {"empty": True,
                "message": "No analysis yet. Submit a product to populate the dashboard."}
    rec = analysis_engine.latest_recommendation(db, a.id)
    return {
        "analysis_id": a.id,
        "product": {"name": a.product.name, "budget": a.product.total_budget,
                    "currency": a.product.currency},
        "objective": a.objective,
        "category": a.category,
        "confidence": a.confidence,
        "data_source_label": a.data_source_label,
        "allocation": [
            {"format_key": al["format_key"], "label": al["label"], "share": al["share"],
             "amount": al["amount"], "confidence": al.get("confidence")}
            for al in (rec.allocations if rec else [])
        ],
        "predicted": rec.predicted_totals if rec else {},
        "recommendation_id": rec.id if rec else None,
        "cold_start": rec.cold_start if rec else True,
        "ads_history_status": a.ads_history_status,
        "youtube_research_status": a.youtube_research_status,
    }


@router.get("/campaigns/analytics")
def campaigns_analytics(days: int = Query(90, ge=7, le=365), format_key: str | None = None,
                        db: Session = Depends(get_db)):
    """Historical performance series + per-campaign table (labeled by source)."""
    from datetime import date, timedelta

    cutoff = date.today() - timedelta(days=days)
    rows = db.execute(
        select(CampaignPerformance, Campaign)
        .join(Campaign, CampaignPerformance.campaign_id == Campaign.id)
        .where(CampaignPerformance.date >= cutoff)
    ).all()
    if format_key:
        rows = [(p, c) for p, c in rows if c.format_key == format_key]

    daily: dict[str, MetricSet] = {}
    per_campaign: dict[int, dict] = {}
    by_format: dict[str, MetricSet] = {}
    for p, c in rows:
        ms = MetricSet(impressions=p.impressions, clicks=p.clicks, cost=p.cost_micros / 1e6,
                       conversions=p.conversions, conversion_value=p.conversion_value,
                       video_views=p.video_views, video_impressions=p.video_impressions)
        key = p.date.isoformat()
        daily[key] = merge_metric_sets([daily[key], ms]) if key in daily else ms
        bucket = per_campaign.setdefault(c.id, {
            "campaign_id": c.id, "name": c.name, "format_key": c.format_key,
            "status": c.status, "metrics": MetricSet(), "data_source_label": c.data_source_label})
        bucket["metrics"] = merge_metric_sets([bucket["metrics"], ms])
        by_format[c.format_key] = merge_metric_sets([by_format[c.format_key], ms]) if c.format_key in by_format else ms

    label = "LIVE DATA" if rows and rows[0][1].data_source_label == "LIVE DATA" else (
        "SYNTHETIC DEMO DATA" if rows else "NO DATA")
    campaigns_out = []
    for bucket in per_campaign.values():
        m: MetricSet = bucket["metrics"]
        d = m.to_dict()
        campaigns_out.append({k: v for k, v in bucket.items() if k != "metrics"} | {"metrics": d})
    return {
        "days": days,
        "data_source_label": label,
        "totals": merge_metric_sets(list(daily.values())).to_dict() if daily else {},
        "series": [{"date": k, **v.to_dict()} for k, v in sorted(daily.items())],
        "by_format": [{"format_key": k, **v.to_dict()} for k, v in by_format.items()],
        "campaigns": sorted(campaigns_out, key=lambda c: c["metrics"]["cost"], reverse=True)[:30],
    }


@router.get("/audience/{analysis_id}")
def audience(analysis_id: int, db: Session = Depends(get_db)):
    a = db.get(ProductAnalysis, analysis_id)
    if not a:
        raise HTTPException(404, "analysis not found")
    return {
        "analysis_id": a.id,
        "audience": a.audience,
        "inference_method": a.inference_method,
        "disclaimer": "Inferred hypotheses — not verified demographic data.",
    }


@router.get("/competitors/{analysis_id}")
def competitors(analysis_id: int, db: Session = Depends(get_db)):
    a = db.get(ProductAnalysis, analysis_id)
    if not a:
        raise HTTPException(404, "analysis not found")
    videos = db.execute(
        select(ResearchVideo).where(ResearchVideo.analysis_id == a.id).order_by(ResearchVideo.views.desc())
    ).scalars().all()
    return {
        "analysis_id": a.id,
        "status": a.youtube_research_status,
        "summary": a.competitor_summary,
        "videos": [{"video_id": v.video_id, "title": v.title, "channel_title": v.channel_title,
                    "views": v.views, "likes": v.likes, "comments": v.comments,
                    "engagement_rate": v.engagement_rate, "duration_seconds": v.duration_seconds,
                    "published_at": v.published_at, "thumbnail_url": v.thumbnail_url,
                    "url": f"https://www.youtube.com/watch?v={v.video_id}",
                    "data_source_label": v.data_source_label} for v in videos],
        "disclaimer": ("Public organic YouTube statistics. They do NOT reveal ad spend, "
                       "paid conversions or competitor ROAS."),
    }
