"""FastAPI application: all REST endpoints (mounted under /api)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import check_db, get_db
from app.integrations.registry import ADAPTERS, platform_listing
from app.models import Review, SearchJob
from app.schemas import (
    HealthResponse, PaginatedReviews, PlatformStatusOut, ReportResponse,
    ReviewOut, SearchRequest, JobStatusResponse,
)
from app.services import aggregation, exporter
from app.services.orchestrator import create_job, start_job_background

log = logging.getLogger("api")
router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- health/meta
@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    return HealthResponse(
        status="ok" if check_db() else "db-error",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        nlp_pipeline=settings.NLP_PIPELINE_VERSION,
        database="postgresql" if not settings.is_sqlite else "sqlite (sandbox; postgres-ready)",
        task_queue=settings.TASK_QUEUE,
        sample_data_allowed=settings.ALLOW_SAMPLE_DATA,
        time=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/platforms")
def platforms():
    return {"platforms": platform_listing()}


# ---------------------------------------------------------------- search/jobs
@router.post("/search")
def search(req: SearchRequest, db: Session = Depends(get_db)):
    job = create_job(db, req.product_name, req.description, req.platforms, req.include_sample)
    start_job_background(job.id)
    return {"job_id": job.id, "status": job.status}


def _job_response(db: Session, job: SearchJob) -> dict:
    from app.models import JobPlatformStatus
    statuses = db.query(JobPlatformStatus).filter_by(job_id=job.id).all()
    collected = sum(s.items_collected for s in statuses)
    return {
        "job_id": job.id,
        "product_name": job.product_name,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "data_mode": job.data_mode,
        "error": job.error,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "platforms": [
            {
                "platform": s.platform_key,
                "platform_name": s.platform_name,
                "status": s.status,
                "message": s.message,
                "items_collected": s.items_collected,
                "is_sample": s.is_sample,
                "requires_credentials": json.loads(s.requires_credentials or "[]"),
                "collected_at": s.collected_at,
            } for s in statuses
        ],
        "totals": {"collected": collected},
    }


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(SearchJob).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_response(db, job)


@router.get("/jobs/{job_id}/report", response_model=ReportResponse)
def job_report(job_id: str, db: Session = Depends(get_db)):
    from app.models import ReportCache
    job = db.query(SearchJob).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    cache = db.query(ReportCache).get(job_id)
    if cache and job.status == "completed":
        return JSONResponse(content=json.loads(cache.report_json))
    report = aggregation.analyze(db, job_id)
    return JSONResponse(content=json.loads(json.dumps(report, default=str)))


@router.get("/jobs/{job_id}/reviews", response_model=PaginatedReviews)
def job_reviews(
    job_id: str,
    platform: str | None = None,
    sentiment: str | None = None,
    language: str | None = None,
    scope: str | None = None,
    variant: str | None = None,
    q: str | None = None,
    min_rating: float | None = Query(default=None, ge=0, le=5),
    max_rating: float | None = Query(default=None, ge=0, le=5),
    date_from: str | None = None,
    date_to: str | None = None,
    include_spam: bool = False,
    include_flagged: bool = True,
    sort: str = "date",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Review).filter_by(job_id=job_id)
    if not include_spam:
        query = query.filter(Review.is_spam == False)  # noqa: E712
    if platform:
        query = query.filter(Review.platform == platform)
    if sentiment:
        query = query.filter(Review.sentiment == sentiment)
    if language:
        query = query.filter(Review.language == language)
    if scope:
        query = query.filter(Review.complaint_scope == scope)
    if variant:
        query = query.filter(Review.variant == variant)
    if min_rating is not None:
        query = query.filter(Review.rating >= min_rating)
    if max_rating is not None:
        query = query.filter((Review.rating <= max_rating) | (Review.rating == None))  # noqa: E711
    if date_from:
        query = query.filter(Review.review_date >= date_from)
    if date_to:
        query = query.filter(Review.review_date <= date_to)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(or_(func.lower(Review.text_original).like(like),
                                 func.lower(Review.text_normalized).like(like)))
    if not include_flagged:
        query = query.filter(Review.relevance >= settings.RELEVANCE_THRESHOLD)

    total = query.count()
    order = {
        "date": desc(Review.review_date),
        "sentiment": desc(Review.sentiment_score),
        "rating": desc(Review.rating),
        "relevance": desc(Review.relevance),
    }.get(sort, desc(Review.review_date))
    rows = query.order_by(order, desc(Review.id)).offset((page - 1) * page_size).limit(page_size).all()

    from app.models import JobPlatformStatus
    pmap = {s.platform_key: s.platform_name
            for s in db.query(JobPlatformStatus).filter_by(job_id=job_id).all()}
    items = [
        ReviewOut(
            id=r.id, platform=r.platform, platform_name=pmap.get(r.platform, r.platform),
            text_original=r.text_original, translation=r.translation,
            language=r.language, language_confidence=r.language_confidence,
            language_uncertain=r.language_uncertain,
            sentiment=r.sentiment, sentiment_score=r.sentiment_score,
            sentiment_confidence=r.sentiment_confidence,
            sentiment_uncertain=r.sentiment_uncertain,
            sarcasm_suspect=r.sarcasm_suspect,
            complaint_scope=r.complaint_scope,
            aspects=json.loads(r.aspects_json or "[]"),
            drivers=(lambda d: d if isinstance(d, list) else [])(json.loads(r.drivers_json or "[]")),
            rating=r.rating, review_date=r.review_date, variant=r.variant,
            source_url=r.source_url, is_spam=r.is_spam, relevance=r.relevance,
            data_source=r.data_source,
        ) for r in rows
    ]
    return PaginatedReviews(total=total, page=page, page_size=page_size, items=items)


# ---------------------------------------------------------------- export
@router.get("/jobs/{job_id}/export.csv")
def export_csv(job_id: str, db: Session = Depends(get_db)):
    job = db.query(SearchJob).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    filename, content = exporter.export_csv(db, job_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/jobs/{job_id}/export.pdf")
def export_pdf(job_id: str, db: Session = Depends(get_db)):
    job = db.query(SearchJob).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    from app.models import ReportCache
    cache = db.query(ReportCache).get(job_id)
    if cache:
        report = json.loads(cache.report_json)
    else:
        report = aggregation.analyze(db, job_id)
    filename, content = exporter.export_pdf(db, job_id, report)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
