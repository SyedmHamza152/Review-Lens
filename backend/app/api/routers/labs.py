"""ML Lab, Big Data Lab, and Reports endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.ml import pipeline as ml_pipeline
from app.ml.registry import invalidate_cache, load_predictor, models_dir
from app.models.analysis import ProductAnalysis
from app.models.benchmark import BenchmarkJob, DatasetBenchmark
from app.models.ml import ModelRegistryEntry
from app.models.report import GeneratedReport
from app.schemas.common import BenchmarkRequest, GenerateDatasetRequest, PredictRequest, ReportRequest
from app.services.job_runner import submit

router = APIRouter(tags=["ml", "bigdata", "reports"])


# ------------------------------------------------------------------ ML Lab
@router.get("/ml/models")
def ml_models(db: Session = Depends(get_db)):
    registry = ml_pipeline.load_registry(models_dir()) or {}
    targets = registry.get("targets", {})
    entries = db.execute(select(ModelRegistryEntry)).scalars().all()
    return {
        "trained_on": registry.get("trained_on", "synthetic"),
        "rows_train": registry.get("rows_train"),
        "rows_test": registry.get("rows_test"),
        "available": bool(targets),
        "targets": [
            {"target": t, "best_model": info.get("best_model"),
             "metrics": info.get("metrics", {}), "train_seconds": info.get("train_seconds")}
            for t, info in targets.items()
        ],
        "registry_rows": [{"target": e.target, "model": e.model_name, "is_best": e.is_best,
                           "mae": e.mae, "rmse": e.rmse, "r2": e.r2,
                           "trained_on": e.trained_on} for e in entries],
        "note": ("Models are trained on SYNTHETIC data unless retrained with authorized "
                 "live campaign data (label shown per model)."),
    }


@router.post("/ml/predict")
def ml_predict(payload: PredictRequest):
    predictor = load_predictor()
    if not predictor:
        raise HTTPException(404, "No trained models — run POST /api/v1/ml/train or scripts/train_models.py first")
    preds = predictor(format_key=payload.format_key, objective=payload.objective,
                      category_key=payload.category_key)
    return {"inputs": payload.model_dump(), "predictions": preds,
            "data_source_label": "MODEL PREDICTION"}


@router.post("/ml/train", status_code=202)
def ml_train(db: Session = Depends(get_db)):
    """Retrain on the 100k synthetic dataset (or live campaign dump when present)."""
    datasets = sorted(Path(settings.DATA_DIR).glob("datasets/ad_campaigns_100000_*.csv"))
    if not datasets:
        raise HTTPException(409, "No 100k training dataset found — generate one in the Big Data Lab first")

    # training runs in the background pool; UI polls GET /api/v1/ml/models
    def run():
        import pandas as pd

        from app.ml.features import build_feature_frame

        df = pd.read_csv(datasets[-1])
        frame = build_feature_frame(df)
        ml_pipeline.train_all(frame, models_dir())
        _sync_registry()
        invalidate_cache()

    submit(run, name="ml-train")
    return {"status": "queued", "note": "Poll GET /api/v1/ml/models until 'available' is true"}


def _sync_registry() -> None:
    """Mirror metrics.json into model_registry rows (best-effort)."""
    registry = ml_pipeline.load_registry(models_dir()) or {}
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        db.query(ModelRegistryEntry).delete()
        for target, info in registry.get("targets", {}).items():
            for model_name, metrics in (info.get("metrics") or {}).items():
                if "error" in metrics:
                    continue
                db.add(ModelRegistryEntry(
                    target=target, model_name=model_name,
                    is_best=model_name == info.get("best_model"),
                    mae=metrics.get("mae", 0.0), rmse=metrics.get("rmse", 0.0), r2=metrics.get("r2", 0.0),
                    train_rows=registry.get("rows_train", 0), test_rows=registry.get("rows_test", 0),
                    trained_on=registry.get("trained_on", "synthetic"),
                ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ------------------------------------------------------------------ Big Data Lab
@router.get("/bigdata/datasets")
def bigdata_datasets():
    datasets = []
    for p in sorted(Path(settings.DATA_DIR).glob("datasets/*.csv")):
        datasets.append({"file": p.name, "size_mb": round(p.stat().st_size / 1048576, 2)})
    return {"datasets": datasets[-20:]}


@router.post("/bigdata/generate", status_code=202)
def bigdata_generate(payload: GenerateDatasetRequest, db: Session = Depends(get_db)):
    job_id = uuid.uuid4().hex
    job = BenchmarkJob(id=job_id, status="running", rows=payload.rows,
                       engines=["generator"], current_step="Generating dataset",
                       started_at=datetime.now(timezone.utc))
    db.add(job)
    db.commit()

    from app.bigdata.generator import generate_dataset

    def run():
        from app.core.db import SessionLocal

        s = SessionLocal()
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = Path(settings.DATA_DIR) / "datasets" / f"ad_campaigns_{payload.rows}_{stamp}.csv"
            generate_dataset(payload.rows, out, seed=payload.seed)
            j = s.get(BenchmarkJob, job_id)
            j.status = "done"
            j.progress = 100.0
            j.current_step = f"Saved {out.name}"
            j.finished_at = datetime.now(timezone.utc)
            s.add(j)
            s.commit()
        except Exception as e:
            j = s.get(BenchmarkJob, job_id)
            j.status = "error"
            j.error = str(e)[:1000]
            s.add(j)
            s.commit()
        finally:
            s.close()

    submit(run, name=f"generate-{payload.rows}")
    return {"job_id": job_id, "status": "running"}


@router.post("/bigdata/benchmark", status_code=202)
def bigdata_benchmark(payload: BenchmarkRequest, db: Session = Depends(get_db)):
    job_id = uuid.uuid4().hex
    job = BenchmarkJob(id=job_id, status="queued", rows=payload.rows, engines=payload.engines,
                       current_step="Queued", started_at=datetime.now(timezone.utc))
    db.add(job)
    db.commit()
    submit(lambda: _run_benchmark(job_id, payload.rows, payload.engines), name=f"benchmark-{payload.rows}")
    return {"job_id": job_id, "status": "queued"}


def _run_benchmark(job_id: str, rows: int, engines: list[str]) -> None:
    from app.bigdata.benchmark import run_benchmark_job

    run_benchmark_job(job_id, rows, engines)
    _sync_registry_after_benchmark()


def _sync_registry_after_benchmark() -> None:
    pass  # reserved for post-benchmark hooks


@router.get("/bigdata/jobs/{job_id}")
def bigdata_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(BenchmarkJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {"job_id": job.id, "status": job.status, "rows": job.rows, "engines": job.engines,
            "current_step": job.current_step, "progress": job.progress, "error": job.error}


@router.get("/bigdata/benchmarks")
def bigdata_benchmarks(db: Session = Depends(get_db)):
    rows = db.execute(
        select(DatasetBenchmark).order_by(DatasetBenchmark.id.desc()).limit(100)
    ).scalars().all()
    return {"benchmarks": [{
        "id": r.id, "engine": r.engine, "rows": r.rows, "dataset_size_mb": r.dataset_size_mb,
        "generate_seconds": r.generate_seconds, "pipeline_seconds": r.pipeline_seconds,
        "peak_memory_mb": r.peak_memory_mb, "status": r.status, "error": r.error,
        "equivalence_ok": r.equivalence_ok, "created_at": str(r.created_at),
    } for r in rows]}


@router.get("/bigdata/benchmark/report")
def bigdata_report():
    files = sorted(Path(settings.DATA_DIR).glob("benchmarks/benchmark_*.md"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise HTTPException(404, "No benchmark report yet — run a benchmark first")
    return {"file": files[0].name, "content": files[0].read_text(encoding="utf-8")}


@router.get("/bigdata/charts/{name}")
def bigdata_chart(name: str):
    if "/" in name or ".." in name:
        raise HTTPException(422, "invalid name")
    path = Path(settings.DATA_DIR) / "benchmarks" / name
    if not path.exists():
        raise HTTPException(404, "chart not found")
    return FileResponse(path, media_type="image/png")


# ------------------------------------------------------------------ Reports
@router.get("/reports")
def list_reports(db: Session = Depends(get_db)):
    reports = db.execute(select(GeneratedReport).order_by(GeneratedReport.id.desc()).limit(50)).scalars().all()
    return {"reports": [{"id": r.id, "analysis_id": r.analysis_id, "format": r.format,
                         "size_bytes": r.size_bytes, "created_at": str(r.created_at),
                         "download": f"/api/v1/reports/{r.id}/download"} for r in reports]}


@router.post("/reports", status_code=201)
def create_report(payload: ReportRequest, db: Session = Depends(get_db)):
    a = db.get(ProductAnalysis, payload.analysis_id)
    if not a:
        raise HTTPException(404, "analysis not found")
    from app.reports.generator import generate_report

    path, fmt = generate_report(db, a, payload.format, settings.DATA_DIR)
    rep = GeneratedReport(analysis_id=a.id, format=fmt, path=str(path),
                          size_bytes=path.stat().st_size)
    db.add(rep)
    db.commit()
    db.refresh(rep)
    return {"id": rep.id, "format": fmt, "size_bytes": rep.size_bytes,
            "download": f"/api/v1/reports/{rep.id}/download"}


@router.get("/reports/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    rep = db.get(GeneratedReport, report_id)
    if not rep or not Path(rep.path).exists():
        raise HTTPException(404, "report not found")
    media = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "csv": "text/csv"}[rep.format]
    return FileResponse(rep.path, media_type=media, filename=Path(rep.path).name)
