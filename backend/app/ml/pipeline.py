"""ML training pipeline.

Targets: ctr, cpc, cvr, cpa, roas, conversions, revenue, video_views.
Candidates: LinearRegression, RandomForest, GradientBoosting, XGBoost.
Split: chronological by campaign start (train = earliest 80%) to avoid
temporal leakage. Models are evaluated with MAE / RMSE / R² and the best
model per target is registered.

Honesty: models are trained on SYNTHETIC data unless explicitly retrained on
authorized live campaign data — the registry records `trained_on`.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from app.ml.features import CATEGORICAL_FEATURES, FEATURE_NAMES, NUMERIC_FEATURES

logger = logging.getLogger(__name__)

REGISTRY_FILE = "metrics.json"


def _candidates():
    models = {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=120, min_samples_leaf=4, n_jobs=-1, random_state=42),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=200, learning_rate=0.06, max_depth=3, random_state=42),
    }
    try:
        from xgboost import XGBRegressor

        models["xgboost"] = XGBRegressor(
            n_estimators=350, learning_rate=0.06, max_depth=6, subsample=0.9,
            colsample_bytree=0.9, random_state=42, n_jobs=2, tree_method="hist",
        )
    except ImportError:
        logger.warning("xgboost not installed — training without it")
    return models


def _preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("num", "passthrough", NUMERIC_FEATURES),
        ]
    )


def train_all(df_campaign: pd.DataFrame, models_dir: str | Path) -> dict:
    """Train one candidate set per target; return the registry dict."""
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    sort_col = "date" if "date" in df_campaign.columns else "month"
    df = df_campaign.sort_values(sort_col).reset_index(drop=True)
    split = int(len(df) * 0.8)
    train_df, test_df = df.iloc[:split], df.iloc[split:]
    if len(train_df) < 30 or len(test_df) < 10:
        raise ValueError(f"Not enough rows to train/test ({len(train_df)}/{len(test_df)})")

    registry: dict = {"targets": {}, "trained_on": "synthetic", "rows_train": int(len(train_df)),
                      "rows_test": int(len(test_df)), "feature_names": FEATURE_NAMES}
    candidates = _candidates()

    for target in ["ctr", "cpc", "cvr", "cpa", "roas", "conversions", "revenue", "video_views"]:
        t0 = time.time()
        y_train = train_df[target].astype(float)
        y_test = test_df[target].astype(float)
        X_train, X_test = train_df[FEATURE_NAMES], test_df[FEATURE_NAMES]

        results = {}
        best_name, best_model, best_r2 = None, None, -1e9
        for name, est in candidates.items():
            try:
                pipe = Pipeline([("prep", _preprocessor()), ("model", est)])
                pipe.fit(X_train, y_train)
                pred = np.clip(pipe.predict(X_test), a_min=0, a_max=None)
                mae = float(mean_absolute_error(y_test, pred))
                rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
                r2 = float(r2_score(y_test, pred)) if len(y_test) > 1 else 0.0
                results[name] = {"mae": mae, "rmse": rmse, "r2": r2}
                if r2 > best_r2:
                    best_name, best_model, best_r2 = name, pipe, r2
            except Exception as e:
                logger.warning("Model %s failed for %s: %s", name, target, e)
                results[name] = {"error": str(e)[:200]}

        if best_model is None:
            logger.error("No model trained for target %s", target)
            continue
        joblib.dump(best_model, models_dir / f"{target}_best.joblib")
        registry["targets"][target] = {
            "best_model": best_name,
            "metrics": results,
            "train_seconds": round(time.time() - t0, 2),
        }
        logger.info("Trained %s -> %s (R² %.3f, %.1fs)", target, best_name, best_r2, time.time() - t0)

    registry["meta"] = {
        "n_candidates": len(candidates),
        "split": "chronological 80/20 by month",
        "features": FEATURE_NAMES,
    }
    (models_dir / REGISTRY_FILE).write_text(json.dumps(registry, indent=2))
    return registry


def load_registry(models_dir: str | Path) -> dict | None:
    path = Path(models_dir) / REGISTRY_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None
