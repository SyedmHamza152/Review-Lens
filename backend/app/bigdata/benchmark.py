"""Benchmark runner — measures (never invents) Pandas vs MapReduce vs Spark.

For each (dataset size × engine):
  1. generate the synthetic CSV (timed)
  2. run the engine pipeline (timed, peak RSS sampled)
  3. cross-check engine totals against the Pandas baseline (equivalence)
Results land in DatasetBenchmark rows + a JSON/Markdown report + PNG charts
under backend/data/benchmarks/. Runs execute in a background thread with
progress persisted in BenchmarkJob so the UI polls real state.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.models.benchmark import BenchmarkJob, DatasetBenchmark  # noqa: E402

logger = logging.getLogger(__name__)

BENCH_DIR = Path(settings.DATA_DIR) / "benchmarks"
DATASET_DIR = Path(settings.DATA_DIR) / "datasets"
ENGINE_LABELS = {"pandas": "Pandas", "mapreduce": "Python MapReduce", "spark": "PySpark (local)"}


def _peak_memory_mb():
    try:
        import resource

        # ru_maxrss of THIS process and reaped children (KB on Linux)
        self_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        child_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        return max(self_kb, child_kb) / 1024.0
    except Exception:
        return 0.0


class _MemSampler:
    """Samples the RSS of the whole process tree while one engine runs."""

    def __init__(self) -> None:
        self._stop = False
        self._peak = 0
        self._thread: threading.Thread | None = None
        self._proc = None

    def start(self) -> None:
        try:
            import psutil

            self._proc = psutil.Process()
        except Exception:
            self._proc = None
            return
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop:
            try:
                total = self._proc.memory_info().rss
                for child in self._proc.children(recursive=True):
                    try:
                        total += child.memory_info().rss
                    except Exception:
                        pass
                self._peak = max(self._peak, total)
            except Exception:
                pass
            time.sleep(0.08)

    def stop_mb(self) -> float:
        self._stop = True
        if self._thread:
            self._thread.join(timeout=2)
        return round(self._peak / (1024 * 1024), 1)


def _file_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024) if path.exists() else 0.0


def run_benchmark_job(job_id: str, rows: int, engines: list[str]) -> None:
    """Executed in background thread. Creates its own DB session."""
    db = SessionLocal()
    ok = True
    try:
        _execute(db, job_id, rows, engines)
    except Exception as e:
        ok = False
        logger.exception("Benchmark job %s failed", job_id)
        job = db.get(BenchmarkJob, job_id)
        if job:
            job.status = "error"
            job.error = str(e)[:1500]
            job.finished_at = datetime.now(timezone.utc)
            db.add(job)
            db.commit()
    finally:
        db.close()


def _execute(db, job_id: str, rows: int, engines: list[str]) -> None:
    from app.bigdata.generator import generate_dataset
    from app.bigdata import pandas_pipeline, mapreduce_pipeline

    job = db.get(BenchmarkJob, job_id)
    if not job:
        raise ValueError("benchmark job not found")

    def step(text: str, frac: float) -> None:
        job.current_step = text
        job.progress = round(frac * 100.0, 1)
        db.add(job)
        db.commit()

    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    step(f"Generating {rows:,}-row dataset", 0.05)
    t0 = time.perf_counter()
    csv_path = DATASET_DIR / f"ad_campaigns_{rows}_{stamp}.csv"
    generate_dataset(rows, csv_path)
    gen_seconds = time.perf_counter() - t0
    size_mb = _file_size_mb(csv_path)
    step(f"Dataset ready ({size_mb:.1f} MB) — running engines", 0.2)

    results: dict[str, dict] = {}
    baseline_totals: dict | None = None

    frac_per_engine = 0.75 / max(len(engines), 1)
    for i, eng in enumerate(engines):
        step(f"Running {ENGINE_LABELS.get(eng, eng)} on {rows:,} rows", 0.2 + i * frac_per_engine)
        entry: dict = {"status": "ok"}
        sampler = _MemSampler()
        try:
            sampler.start()
            t1 = time.perf_counter()
            if eng == "pandas":
                out = pandas_pipeline.run_pipeline(csv_path)
            elif eng == "mapreduce":
                out = mapreduce_pipeline.run_pipeline(csv_path)
            elif eng == "spark":
                from app.bigdata import spark_pipeline

                out = spark_pipeline.run_pipeline(csv_path)
            else:
                raise ValueError(f"unknown engine {eng}")
            elapsed = time.perf_counter() - t1
            peak = sampler.stop_mb()
            entry.update({
                "seconds": round(elapsed, 3),
                "peak_memory_mb": peak,
                "totals": out.get("totals", {}),
                "by_format": out.get("by_format", [])[:5],
            })
            if eng == "pandas":
                baseline_totals = out.get("totals", {})
        except Exception as e:
            sampler.stop_mb()
            logger.exception("Engine %s failed", eng)
            entry.update({"status": "error", "error": str(e)[:800], "seconds": None})
        results[eng] = entry

        db.add(DatasetBenchmark(
            job_id=job_id,
            engine=eng,
            rows=rows,
            dataset_size_mb=round(size_mb, 2),
            generate_seconds=round(gen_seconds, 3),
            pipeline_seconds=entry.get("seconds") or 0.0,
            peak_memory_mb=entry.get("peak_memory_mb") or 0.0,
            status=entry["status"],
            error=entry.get("error", ""),
            result_summary={"totals": entry.get("totals", {})},
        ))
        db.commit()

    # equivalence check (engines must agree with the Pandas baseline)
    equivalence = {}
    for eng, entry in results.items():
        t = entry.get("totals") or {}
        if eng != "pandas" and baseline_totals and entry["status"] == "ok":
            ok_eq = (
                t.get("impressions") == baseline_totals.get("impressions")
                and t.get("clicks") == baseline_totals.get("clicks")
                and abs(float(t.get("spend", 0)) - float(baseline_totals.get("spend", 0))) < 1.0
                and abs(float(t.get("revenue", 0)) - float(baseline_totals.get("revenue", 0))) < 1.0
            )
            equivalence[eng] = ok_eq
        elif eng == "pandas":
            equivalence[eng] = True

    for row in db.query(DatasetBenchmark).filter(DatasetBenchmark.job_id == job_id).all():
        row.equivalence_ok = bool(equivalence.get(row.engine, False))
    db.commit()

    # charts + report
    step("Building charts and report", 0.96)
    chart_paths = _make_charts(results, rows, stamp)
    report_path = _write_report(results, equivalence, rows, gen_seconds, size_mb, stamp, chart_paths)

    job.status = "done" if all(results[e]["status"] == "ok" for e in results) else "done_with_errors"
    job.progress = 100.0
    job.finished_at = datetime.now(timezone.utc)
    db.add(job)
    db.commit()


def _make_charts(results: dict, rows: int, stamp: str) -> list[str]:
    ok = {e: r for e, r in results.items() if r["status"] == "ok" and r.get("seconds")}
    if not ok:
        return []
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    engines = list(ok.keys())
    times = [ok[e]["seconds"] for e in engines]
    mems = [ok[e].get("peak_memory_mb", 0) for e in engines]

    colors = ["#34d399", "#f59e0b", "#38bdf8"]
    bars = axes[0].barh([ENGINE_LABELS.get(e, e) for e in engines], times,
                        color=colors[: len(engines)])
    axes[0].set_xlabel("seconds")
    axes[0].set_title(f"Pipeline time — {rows:,} rows (measured)")
    axes[0].bar_label(bars, fmt="%.1fs", padding=3)

    bars2 = axes[1].barh([ENGINE_LABELS.get(e, e) for e in engines], mems,
                         color=colors[: len(engines)])
    axes[1].set_xlabel("peak RSS (MB)")
    axes[1].set_title("Peak memory (process tree)")
    axes[1].bar_label(bars2, fmt="%.0f MB", padding=3)

    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    out = BENCH_DIR / f"benchmark_{rows}_{stamp}.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return [str(out)]


def _write_report(results, equivalence, rows, gen_seconds, size_mb, stamp, charts) -> Path:
    lines = [
        f"# AdPilot AI — Benchmark report ({stamp})",
        "",
        f"Dataset: {rows:,} synthetic rows, {size_mb:.1f} MB, generated in {gen_seconds:.1f}s "
        "(generator timed separately from engine pipelines).",
        "",
        "| Engine | Status | Time (s) | Peak RSS (MB) | CTR % | CPC | ROAS | Equivalence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for eng, r in results.items():
        t = r.get("totals") or {}
        lines.append(
            f"| {ENGINE_LABELS.get(eng, eng)} | {r['status']} | "
            f"{r.get('seconds') if r.get('seconds') is not None else '—'} | "
            f"{r.get('peak_memory_mb', 0)} | {t.get('ctr', '—')} | {t.get('cpc', '—')} | "
            f"{t.get('roas', '—')} | {'✓' if equivalence.get(eng) else '✗'} |"
        )
    lines += ["", "Equivalence: totals (impressions/clicks/spend/revenue) must match the "
                   "Pandas baseline exactly (±1.0 currency unit).", ""]
    for eng, r in results.items():
        if r["status"] == "error":
            lines.append(f"**{ENGINE_LABELS.get(eng, eng)} error:** {r.get('error', '')}")
    lines.append("")
    lines.append("_All numbers above were measured during this run — nothing is estimated._")

    md = BENCH_DIR / f"benchmark_{rows}_{stamp}.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (BENCH_DIR / f"benchmark_{rows}_{stamp}.json").write_text(
        json.dumps({"rows": rows, "results": results, "equivalence": equivalence,
                    "charts": charts}, indent=2),
        encoding="utf-8",
    )
    return md
