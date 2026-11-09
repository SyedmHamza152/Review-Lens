"""Unit tests for the metrics engine (spec §8 formulas, zero-safe)."""
from app.services.metrics import MetricSet, micros_to_units, safe_div, units_to_micros


def test_micros_conversion():
    assert micros_to_units(1_500_000) == 1.5
    assert units_to_micros(2.25) == 2_250_000
    assert micros_to_units(units_to_micros(3.14159)) == 3.14159


def test_safe_div_zero_denominator():
    assert safe_div(10, 0) is None
    assert safe_div(0, 0) is None
    assert safe_div(10, 2) == 5.0


def _ms(**kw) -> MetricSet:
    return MetricSet(**kw)


def test_ctr():
    assert _ms(impressions=1000, clicks=25).ctr == 2.5
    assert _ms(impressions=0, clicks=25).ctr is None


def test_cpc_cpa():
    assert _ms(cost=100, clicks=20).cpc == 5.0
    assert _ms(cost=100, clicks=0).cpc is None
    assert _ms(cost=200, conversions=4).cpa == 50.0
    assert _ms(cost=200, conversions=0).cpa is None


def test_conversion_rate():
    assert _ms(clicks=400, conversions=8).conversion_rate == 2.0
    assert _ms(clicks=0, conversions=8).conversion_rate is None


def test_roas_and_cpv():
    assert _ms(conversion_value=600, cost=200).roas == 3.0
    assert _ms(conversion_value=600, cost=0).roas is None
    assert _ms(video_views=1000, cost=150).cpv == 0.15
    assert _ms(video_views=0, cost=150).cpv is None


def test_video_view_rate():
    assert _ms(video_impressions=2000, video_views=600).video_view_rate == 30.0
    assert _ms(video_impressions=0, video_views=10).video_view_rate is None


def test_to_dict_rounding():
    d = _ms(impressions=3, clicks=1, cost=1).to_dict()
    assert d["ctr"] == 33.3333
    assert d["source"] == "unknown"


def test_merge():
    a = _ms(impressions=100, clicks=5, cost=10, video_impressions=100)
    b = _ms(impressions=300, clicks=15, cost=30, video_impressions=300)
    m = MetricSet.__new__(MetricSet)
    from app.services.metrics import merge_metric_sets

    merged = merge_metric_sets([a, b])
    assert merged.impressions == 400 and merged.clicks == 20 and merged.cost == 40
    assert merged.ctr == 5.0
