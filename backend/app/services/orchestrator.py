"""Search job orchestrator.

Runs platform adapters concurrently (isolated - one failure never blocks the
rest), feeds results through the analysis pipeline, then aggregates the
report. Uses in-process background threads for the sandbox MVP; the
TASK_QUEUE=celery option documents the production deployment path.
"""
from __future__ import annotations

import json
import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.registry import ADAPTERS
from app.integrations.sample_corpus import build_sample_result
from app.models import JobPlatformStatus, ProductMatch, ReportCache, SearchJob
from app.nlp.relevance import product_tokens
from app.services import aggregation
from app.services.pipeline import process_adapter_result

log = logging.getLogger("orchestrator")


def create_job(db: Session, product_name: str, description: str | None,
               platforms: list[str] | None, include_sample: bool = False) -> SearchJob:
    from uuid import uuid4
    job_id = str(uuid4())
    keys = list(ADAPTERS.keys()) if not platforms or platforms == ["all"] else \
        [p for p in platforms if p in ADAPTERS]
    job = SearchJob(
        id=job_id,
        product_name=product_name.strip(),
        description=(description or "").strip() or None,
        platforms_requested=json.dumps(keys),
        include_sample=include_sample,
        status="queued", stage="queued", progress=0,
        data_mode="sample" if include_sample else "live",
    )
    db.add(job)
    for key in keys:
        adapter = ADAPTERS[key]
        db.add(JobPlatformStatus(
            job_id=job_id, platform_key=key, platform_name=adapter.name,
            status="pending", message="",
            requires_credentials=json.dumps(adapter.required_env),
        ))
    db.add(ProductMatch(
        job_id=job_id, canonical_name=product_name.strip(),
        brand=None,
        tokens_json=json.dumps(sorted(product_tokens(product_name, description))),
    ))
    db.commit()
    return job


def _update_platform(db: Session, job_id: str, key: str, **fields) -> None:
    row = db.query(JobPlatformStatus).filter_by(job_id=job_id, platform_key=key).first()
    if row:
        for k, v in fields.items():
            setattr(row, k, v)
        row.collected_at = datetime.now(timezone.utc)
        db.commit()


def _set_job(db: Session, job_id: str, **fields) -> None:
    job = db.query(SearchJob).get(job_id)
    if job:
        for k, v in fields.items():
            setattr(job, k, v)
        db.commit()


def run_job(job_id: str) -> None:
    """Background entry point: execute the whole search + analysis."""
    from app.core.db import SessionLocal
    db = SessionLocal()
    try:
        _run(db, job_id)
    except Exception as exc:  # never leave job stuck
        log.exception("job failed: %s", job_id)
        _set_job(db, job_id, status="failed", error=str(exc)[:800],
                 stage="failed", progress=100,
                 completed_at=datetime.now(timezone.utc))
    finally:
        db.close()


def _run(db: Session, job_id: str) -> None:
    job = db.query(SearchJob).get(job_id)
    if not job:
        return
    keys = json.loads(job.platforms_requested)
    # Sample corpus is test/eval-only; the live app never mixes it in.
    include_sample = bool(job.include_sample) and settings.ALLOW_SAMPLE_DATA
    ptokens = product_tokens(job.product_name, job.description)

    _set_job(db, job_id, status="running", stage="searching platforms", progress=5)

    # ---- phase 1: collect from adapters (isolated, parallel) ----
    # NOTE: worker threads perform ONLY adapter HTTP calls; all DB access
    # happens on this main thread (SQLAlchemy Sessions are not thread-safe).
    results: dict[str, tuple] = {}  # key -> (result, used_sample)
    for key in keys:
        _update_platform(db, job_id, key, status="searching", message="Querying platform...")

    def collect(key: str):
        adapter = ADAPTERS[key]
        return adapter.search_with_retry(job.product_name, job.description,
                                         settings.MAX_REVIEWS_PER_PLATFORM)

    with ThreadPoolExecutor(max_workers=settings.BACKGROUND_WORKERS) as pool:
        futures = {pool.submit(collect, key): key for key in keys}
        done = 0
        for fut in as_completed(futures):
            key = futures[fut]
            done += 1
            try:
                res = fut.result()
            except Exception:
                log.exception("adapter %s crashed", key)
                res = None
            used_sample = False
            if res is None:
                if include_sample:
                    res = build_sample_result(key, job.product_name, job.description,
                                              settings.MAX_REVIEWS_PER_PLATFORM)
                    used_sample = True
            elif res.status.value in ("needs_credentials", "blocked", "unsupported", "error", "no_results"):
                if include_sample:
                    res = build_sample_result(key, job.product_name, job.description,
                                              settings.MAX_REVIEWS_PER_PLATFORM)
                    used_sample = True
            results[key] = (res, used_sample)
            _set_job(db, job_id, stage=f"collecting ({done}/{len(keys)} platforms)",
                     progress=5 + int(55 * done / max(1, len(keys))))

    # ---- phase 2: analyze + persist ----
    _set_job(db, job_id, stage="analyzing sentiment", progress=65)
    any_live = False
    any_sample = False
    processed = 0
    for key in keys:
        res, used_sample = results.get(key, (None, False))
        if res is None:
            _update_platform(db, job_id, key, status="error", message="Adapter crashed.",
                             items_collected=0)
            continue
        stats = process_adapter_result(db, job_id, res, ptokens)
        processed += stats["stored"]
        message = res.message or ("Collected and analyzed %d item(s)." % stats["stored"])
        if used_sample:
            message = (message + " | Live access unavailable, so the clearly-labelled "
                       "SAMPLE corpus was used for demonstration.").strip(" |")
            any_sample = True
        elif res.status.value == "success":
            any_live = True
        status = res.status
        final_status = "success_sample" if (used_sample and res.items) else status.value
        _update_platform(
            db, job_id, key,
            status=final_status,
            message=message[:800],
            items_collected=len(res.items),
            is_sample=used_sample,
        )
        _set_job(db, job_id, stage=f"analyzing {key}", progress=65 + int(25 * (keys.index(key) + 1) / len(keys)))

    # ---- phase 3: aggregate report ----
    _set_job(db, job_id, stage="aggregating report", progress=93)
    report = aggregation.analyze(db, job_id)
    cache = db.query(ReportCache).get(job_id)
    from json import dumps
    report_json = dumps(report, default=str, ensure_ascii=False)
    if cache:
        cache.report_json = report_json
        cache.built_at = datetime.now(timezone.utc)
    else:
        db.add(ReportCache(job_id=job_id, report_json=report_json))
    data_mode = "live" if any_live and not any_sample else ("mixed" if any_live else ("sample" if any_sample else "none"))
    _set_job(db, job_id, status="completed", stage="completed", progress=100,
             data_mode=data_mode, completed_at=datetime.now(timezone.utc))
    log.info("job %s completed: %d processed", job_id, processed)


def start_job_background(job_id: str) -> None:
    """Run the job in a daemon thread (sandbox 'inline' queue).

    Production: set TASK_QUEUE=celery and dispatch to Celery workers with
    Redis as broker instead of this thread launcher.
    """
    if settings.TASK_QUEUE == "celery":  # pragma: no cover
        try:
            from celery_app import run_job_task  # type: ignore
            run_job_task.delay(job_id)
            return
        except Exception:
            log.exception("celery dispatch failed; falling back to inline thread")
    t = threading.Thread(target=run_job, args=(job_id,), daemon=True,
                         name=f"job-{job_id[:8]}")
    t.start()
