"""Generate a synthetic YouTube ads dataset CSV.

Usage:
    python scripts/generate_dataset.py --rows 100000 --out backend/data/datasets/my.csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.bigdata.generator import generate_dataset  # noqa: E402
from app.core.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    out = Path(args.out) if args.out else (
        Path(settings.DATA_DIR) / "datasets" / f"ad_campaigns_{args.rows}_cli.csv"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    path = generate_dataset(args.rows, out, seed=args.seed)
    print(f"Wrote {args.rows:,} rows -> {path} ({path.stat().st_size / 1048576:.1f} MB)")


if __name__ == "__main__":
    main()
