"""Model registry — loads trained artifacts and exposes a prediction API.

`load_predictor()` returns a callable: predictor(format_key=..., objective=...,
category_key=...) -> {target: {value, model}} using the best model per target.
Returns None when no registry exists (optimizer then falls back to priors).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Lock

import joblib

from app.core.config import settings
from app.ml.features import inference_features

logger = logging.getLogger(__name__)

_lock = Lock()
_cache: dict = {}


def models_dir() -> Path:
    return Path(settings.MODELS_DIR)


def load_predictor():
    """Return the prediction callable or None (no trained registry).

    A `None` result is cached for only 15 seconds so models trained after the
    server started are picked up without a restart.
    """
    d = models_dir()
    with _lock:
        cached = _cache.get("predictor", "__missing__")
        if cached != "__missing__":
            if cached is not None or (time.time() - _cache.get("cached_at", 0)) < 15:
                return cached
        from app.ml.pipeline import load_registry

        registry = load_registry(d)
        if not registry or not registry.get("targets"):
            _cache["predictor"] = None
            _cache["cached_at"] = time.time()
            return None
        models = {}
        for target, info in registry["targets"].items():
            path = d / f"{target}_best.joblib"
            if path.exists():
                try:
                    models[target] = (joblib.load(path), info.get("best_model", ""))
                except Exception as e:
                    logger.warning("Failed to load model for %s: %s", target, e)
        if not models:
            _cache["predictor"] = None
            _cache["cached_at"] = time.time()
            return None

        def predictor(format_key: str, objective: str, category_key: str) -> dict:
            X = inference_features(format_key, objective, category_key)
            out = {}
            for target, (model, name) in models.items():
                try:
                    value = float(model.predict(X)[0])
                    out[target] = {"value": max(value, 0.0), "model": name,
                                   "features": X.iloc[0].to_dict()}
                except Exception as e:  # pragma: no cover
                    logger.warning("Prediction failed for %s: %s", target, e)
            return out

        _cache["predictor"] = predictor
        _cache["cached_at"] = time.time()
        return predictor


def invalidate_cache() -> None:
    with _lock:
        _cache.pop("predictor", None)
        _cache.pop("cached_at", None)


def funnel_from_predictions(preds: dict) -> dict:
    """Convert raw target predictions into optimizer funnel parameters.

    Mapping (with documented clamps):
      ctr (clicks/impression)     -> click_rate for CPC-priced formats
      cpc                          -> unit_cost for CPC formats
      cvr (conversions/click)      -> cvr
      cpa + cvr                    -> implied cpc
      roas                         -> sanity signal (not directly used)
    """
    def get(t: str) -> float | None:
        v = preds.get(t)
        return float(v["value"]) if v and v.get("value") is not None else None

    ctr, cpc, cvr, cpa, cpv = get("ctr"), get("cpc"), get("cvr"), get("cpa"), None
    unit_cost = None
    if cpc and cpc > 0:
        unit_cost = cpc
    elif cpa and cvr and cvr > 0:
        unit_cost = cpa * cvr

    out: dict = {"cvr": cvr, "unit_cost": unit_cost}
    if ctr is not None and ctr > 0:
        # store as click_rate per impression for CPC pricing; per-view conversion
        # happens in the optimizer via cpv click_rate heuristic (documented).
        out["click_rate"] = min(ctr, 0.5)
        out["view_rate"] = None
    return {k: v for k, v in out.items() if v is not None}
