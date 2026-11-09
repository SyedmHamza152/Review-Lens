"""Optimizer property tests — allocations must ALWAYS sum exactly to budget."""
import pytest

from app.optimization.coldstart import AOV_BY_BAND, FORMAT_PRIORS
from app.optimization.engine import FormatScore, optimize_budget, score_from_prior


def _scores(**overrides) -> list[FormatScore]:
    scores = []
    for key in ("in_stream", "shorts", "in_feed"):
        s = score_from_prior(FORMAT_PRIORS[key])
        s.aov = AOV_BY_BAND["medium"]
        s.sample_size = 250_000
        s.confidence = 0.6
        for attr, val in overrides.items():
            setattr(s, attr, val)
        scores.append(s)
    return scores


@pytest.mark.parametrize("budget", [5000, 50_000, 123_457, 999_999, 150_000.75])
def test_allocation_sums_exactly(budget):
    result = optimize_budget(budget, _scores())
    total = sum(a.amount for a in result.allocations)
    assert abs(total - budget) < 0.01, f"{total} != {budget}"
    assert all(a.amount >= 0 for a in result.allocations)
    share_total = sum(a.share for a in result.allocations)
    assert abs(share_total - 1.0) < 0.001


@pytest.mark.parametrize("budget", [8000, 25_000, 75_000, 500_000])
def test_no_negative_and_reasonable_shares(budget):
    result = optimize_budget(budget, _scores())
    for a in result.allocations:
        assert a.amount >= 0
        assert 0 < a.share <= 0.85
        assert a.predicted["conversions"] >= 0
        assert a.predicted["revenue"] >= 0


def test_bounds_respected():
    scores = _scores()
    result = optimize_budget(100_000, scores, strategy="balanced")
    for a in result.allocations:
        assert a.share <= 0.66  # max_share cap (0.65 + rounding slack)


def test_performance_strategy_concentrates():
    balanced = optimize_budget(100_000, _scores(), strategy="balanced")
    perf = optimize_budget(100_000, _scores(), strategy="performance")
    top_b = max(a.share for a in balanced.allocations)
    top_p = max(a.share for a in perf.allocations)
    assert top_p >= top_b


def test_cold_start_flag_and_methodology():
    scores = _scores()
    for s in scores:
        s.sample_size = 0
        s.confidence = 0.3
    result = optimize_budget(50_000, scores, cold_start=True)
    assert result.cold_start is True
    assert "COLD START" in result.methodology


def test_explanations_present():
    result = optimize_budget(50_000, _scores())
    for a in result.allocations:
        assert len(a.reason) > 60
        assert "revenue per currency unit" in a.reason


def test_tiny_budget_single_format():
    # budget too small to fund 3 minimums -> top format takes all
    result = optimize_budget(900, _scores())
    assert sum(a.amount for a in result.allocations) == 900
    assert len(result.allocations) >= 1


def test_zero_budget_rejected():
    with pytest.raises(ValueError):
        optimize_budget(0, _scores())


def test_predicted_totals_consistency():
    result = optimize_budget(80_000, _scores())
    pt = result.predicted_totals
    total_conv = sum(a.predicted["conversions"] for a in result.allocations)
    assert abs(pt["conversions"] - total_conv) < 0.5
    assert pt["roas"] is not None and pt["roas"] > 0
    assert pt["impressions"] > 0
