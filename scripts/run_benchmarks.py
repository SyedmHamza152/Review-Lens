"""Run Big Data benchmarks from the CLI and print the measured report.

Usage:
    python scripts/run_benchmarks.py --rows 10000 100000 1000000 --engines pandas mapreduce spark
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.bigdata.benchmark import run_benchmark_job  # noqa: E402
from app.core.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, nargs="+", default=[10_000, 100_000])
    parser.add_argument("--engines", nargs="+", default=["pandas", "mapreduce", "spark"])
    args = parser.parse_args()

    from app.core.db import SessionLocal, init_db

    init_db()
    for rows in args.rows:
        db = SessionLocal()
        job_id = uuid.uuid4().hex
        job = type("J", (), {})  # benchmark writes its own rows
        print(f"\n=== Benchmarking {rows:,} rows x {args.engines} ===")
        run_benchmark_job(job_id, rows, args.engines)
        # print fresh results
        from app.models.benchmark import DatasetBenchmark
        from sqlalchemy import select

        for r in db.execute(
            select(DatasetBenchmark).where(DatasetBenchmark.job_id == job_id)
        ).scalars():
            status = r.status if r.status == "ok" else f"{r.status}: {r.error[:80]}"
            print(
                f"  {r.engine:10} {r.pipeline_seconds:>8.2f}s  mem {r.peak_memory_mb:>7.0f}MB  "
                f"equivalence={'ok' if r.equivalence_ok else 'MISMATCH'}  {status}"
            )
        db.close()
    print(f"\nReports + charts: {Path(settings.DATA_DIR) / 'benchmarks'}")


if __name__ == "__main__":
    main()
