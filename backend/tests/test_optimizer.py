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
        assert "per currency unit" in a.reason


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


def test_no_structural_in_stream_bias():
    """Regression: the optimizer must NOT always favor in-stream.

    Across objectives × audience profiles × category leans, every format
    must win somewhere — and no single format may win everywhere.
    """
    from app.services.knowledge import FORMAT_OBJECTIVE_FIT

    winners = set()
    for objective in FORMAT_OBJECTIVE_FIT["in_stream"]:
        for young_share, cat_fit in ((0.65, 1.0), (0.15, 1.0),
                                     (0.65, {"in_stream": 1.22, "shorts": 1.10, "in_feed": 0.85})):
            scores = _scores()
            for s in scores:
                s.objective = objective
                s.objective_fit = FORMAT_OBJECTIVE_FIT[s.format_key].get(objective, 1.0)
                if s.format_key == "shorts":
                    s.audience_fit = 0.75 + 0.55 * young_share
                elif s.format_key == "in_stream":
                    s.audience_fit = 1.20 - 0.30 * young_share
                else:
                    s.audience_fit = 1.05 - 0.10 * young_share
                s.category_fit = cat_fit.get(s.format_key, 1.0) if isinstance(cat_fit, dict) else cat_fit
            res = optimize_budget(100_000, scores)
            winners.add(res.allocations[0].format_key)
    assert winners == {"in_stream", "shorts", "in_feed"}, (
        f"structural bias detected — winners: {winners}"
    )


def test_fit_factors_surfaced():
    res = optimize_budget(100_000, _scores())
    for a in res.allocations:
        ff = a.fit_factors
        assert set(ff) == {"audience", "objective", "category", "research"}
        assert all(0.3 < v < 2.0 for v in ff.values())


def test_research_fit_changes_allocation():
    """A Shorts-heavy LIVE niche signal must move budget toward Shorts."""
    base = _scores()
    res0 = optimize_budget(100_000, base)
    shorts_share = {a.format_key: a.share for a in res0.allocations}

    research = _scores()
    for s in research:
        s.research_fit = {"in_stream": 0.88, "shorts": 1.22, "in_feed": 0.94}[s.format_key]
    res1 = optimize_budget(100_000, research)
    shorts_new = {a.format_key: a.share for a in res1.allocations}
    assert shorts_new["shorts"] > shorts_share["shorts"]
