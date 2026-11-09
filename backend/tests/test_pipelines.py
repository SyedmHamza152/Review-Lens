"""Pipeline equivalence tests — engines must agree on the same CSV."""
from app.bigdata.generator import generate_dataset
from app.bigdata.mapreduce_pipeline import run_pipeline as mr_run
from app.bigdata.pandas_pipeline import run_pipeline as pd_run


def _make(tmp_path, rows=4000):
    csv_path = tmp_path / "data.csv"
    generate_dataset(rows, csv_path, seed=11)
    return csv_path


def test_mapreduce_matches_pandas(tmp_path):
    csv_path = _make(tmp_path)
    base = pd_run(csv_path)["totals"]
    mr = mr_run(csv_path)["totals"]
    for key in ("impressions", "clicks", "spend", "conversions", "revenue", "video_views"):
        assert abs(float(base[key]) - float(mr[key])) < 1.0, f"{key} mismatch: {base[key]} vs {mr[key]}"


def test_mapreduce_by_format_matches_pandas(tmp_path):
    csv_path = _make(tmp_path)
    base = {r["ad_format"]: r for r in pd_run(csv_path)["by_format"]}
    mr = {r["ad_format"]: r for r in mr_run(csv_path)["by_format"]}
    assert set(base.keys()) == set(mr.keys())
    for fmt, brow in base.items():
        assert abs(brow["impressions"] - mr[fmt]["impressions"]) < 1.0


def test_derived_metrics_sane(tmp_path):
    csv_path = _make(tmp_path)
    totals = pd_run(csv_path)["totals"]
    assert 0 < totals["ctr"] < 10
    assert totals["roas"] > 0
    assert totals["cpc"] > 0
