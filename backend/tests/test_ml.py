"""ML pipeline tests — training on a small frame, prediction plumbing."""
import pandas as pd

from app.bigdata.generator import generate_dataset
from app.ml.features import FEATURE_NAMES, build_feature_frame, inference_features
from app.ml.pipeline import train_all


def _frame(tmp_path):
    csv_path = tmp_path / "ml.csv"
    generate_dataset(6000, csv_path, seed=5)
    df = pd.read_csv(csv_path)
    return build_feature_frame(df)


def test_feature_frame_shape_and_columns(tmp_path):
    frame = _frame(tmp_path)
    assert len(frame) > 500
    for col in FEATURE_NAMES + ["ctr", "cpc", "cvr", "cpa", "roas", "revenue"]:
        assert col in frame.columns


def test_train_and_registry(tmp_path):
    frame = _frame(tmp_path)
    registry = train_all(frame, tmp_path / "models")
    assert set(registry["targets"].keys()) >= {"ctr", "cpc", "cvr", "roas"}
    for target, info in registry["targets"].items():
        best = info["best_model"]
        assert best in info["metrics"]
        r2 = info["metrics"][best]["r2"]
        assert -1.0 <= r2 <= 1.0
    assert (tmp_path / "models" / "metrics.json").exists()
    assert (tmp_path / "models" / "ctr_best.joblib").exists()


def test_inference_features_schema():
    X = inference_features("shorts", "Leads", "education_courses")
    assert list(X.columns) == FEATURE_NAMES
    assert len(X) == 1


def test_registry_predictor_after_training(tmp_path, monkeypatch):
    import app.ml.registry as reg

    frame = _frame(tmp_path)
    train_all(frame, tmp_path / "models")
    monkeypatch.setattr(reg, "models_dir", lambda: tmp_path / "models")
    reg.invalidate_cache()
    predictor = reg.load_predictor()
    assert predictor is not None
    preds = predictor(format_key="in_stream", objective="Leads", category_key="education_courses")
    assert "ctr" in preds and "cpc" in preds
    assert preds["ctr"]["value"] >= 0
    reg.invalidate_cache()
