"""Train ML models on the 100k synthetic dataset (or the latest available).

Usage (Windows PowerShell):
    cd backend
    .\\.venv\\Scripts\\python ..\\scripts\\train_models.py

Linux/macOS:
    backend/.venv/bin/python scripts/train_models.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import pandas as pd  # noqa: E402

from app.ml.features import build_feature_frame  # noqa: E402
from app.ml.pipeline import train_all  # noqa: E402
from app.core.config import settings  # noqa: E402


def main() -> None:
    data_dir = Path(settings.DATA_DIR) / "datasets"
    candidates = sorted(data_dir.glob("ad_campaigns_100000_*.csv")) or sorted(
        data_dir.glob("ad_campaigns_*.csv")
    )
    if not candidates:
        print("No training dataset found. Generate one first:")
        print("  python scripts/generate_dataset.py --rows 100000")
        sys.exit(1)
    csv_path = candidates[-1]
    print(f"Training from {csv_path.name}")
    df = pd.read_csv(csv_path)
    frame = build_feature_frame(df)
    print(f"Campaign-day frame: {frame.shape}")
    registry = train_all(frame, settings.MODELS_DIR)
    print("\nBest model per target:")
    for target, info in registry["targets"].items():
        best = info["metrics"][info["best_model"]]
        print(f"  {target:12} {info['best_model']:20} R2={best['r2']:.3f} MAE={best['mae']:.4f}")
    print(f"\nArtifacts saved to {settings.MODELS_DIR} (metrics.json + *_best.joblib)")


if __name__ == "__main__":
    main()
