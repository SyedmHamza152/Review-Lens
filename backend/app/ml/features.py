"""Feature engineering for the performance prediction models.

Features are built from campaign rows so that training data and inference
time inputs share exactly the same schema (no leakage, no drift).
"""
from __future__ import annotations


import pandas as pd

CATEGORICAL_FEATURES = ["ad_format", "marketing_objective", "category"]
NUMERIC_FEATURES = ["budget_share", "audience_age_index", "device_mobile_share", "month", "day_of_week"]
FEATURE_NAMES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

TARGETS = ["ctr", "cpc", "cvr", "cpa", "roas", "conversions", "revenue", "video_views"]

AGE_INDEX = {"18-24": 1.0, "25-34": 2.0, "35-44": 3.0, "45-54": 4.0, "55+": 5.0}


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """num/den with zeros-and-negatives-safe semantics (0 when den<=0)."""
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    den = den.where(den > 0)  # 0 or negative denominators -> NaN -> 0
    return (num / den).fillna(0.0).clip(lower=0.0)


def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized metric computation with zero-safe denominators."""
    df = df.copy()
    df["ctr"] = _safe_ratio(df["clicks"], df["impressions"])
    df["cpc"] = _safe_ratio(df["spend"], df["clicks"])
    df["cvr"] = _safe_ratio(df["conversions"], df["clicks"])
    df["cpa"] = _safe_ratio(df["spend"], df["conversions"])
    df["roas"] = _safe_ratio(df["revenue"], df["spend"])
    df["month"] = pd.to_datetime(df["date"]).dt.month.astype(float)
    return df


def build_feature_frame(df: pd.DataFrame, default_category: str = "general") -> pd.DataFrame:
    """One row per campaign-day with engineered features + targets.

    Campaign-day granularity gives thousands of training rows from the
    synthetic corpus while keeping every feature computable at inference
    time from planner inputs only (no target leakage).
    """
    df = add_derived_metrics(df)
    df["is_mobile"] = (df["device"].astype(str) == "mobile").astype(float)
    df["age_index"] = df["age_group"].astype(str).map(AGE_INDEX).fillna(2.0)
    df["dow"] = pd.to_datetime(df["date"]).dt.day_of_week.astype(float)

    grouped = df.groupby(["campaign_id", "date"], observed=True).agg(
        ad_format=("ad_format", "first"),
        marketing_objective=("marketing_objective", "first"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        spend=("spend", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
        video_views=("video_views", "sum"),
        month=("month", "first"),
        day_of_week=("dow", "first"),
        audience_age_index=("age_index", "mean"),
        device_mobile_share=("is_mobile", "mean"),
    ).reset_index()

    # campaign-day metrics (targets)
    grouped["ctr"] = _safe_ratio(grouped["clicks"], grouped["impressions"])
    grouped["cpc"] = _safe_ratio(grouped["spend"], grouped["clicks"])
    grouped["cvr"] = _safe_ratio(grouped["conversions"], grouped["clicks"])
    grouped["cpa"] = _safe_ratio(grouped["spend"], grouped["conversions"])
    grouped["roas"] = _safe_ratio(grouped["revenue"], grouped["spend"])

    grouped["category"] = default_category
    day_total = grouped.groupby("date", observed=True)["spend"].transform("sum")
    grouped["budget_share"] = grouped["spend"] / day_total.clip(lower=1.0)

    return grouped


def inference_features(format_key: str, objective: str, category_key: str) -> pd.DataFrame:
    """Single-row frame matching training features (median numeric defaults)."""
    return pd.DataFrame([{
        "ad_format": format_key,
        "marketing_objective": objective,
        "category": category_key,
        "budget_share": 0.33,
        "audience_age_index": 2.0,
        "device_mobile_share": 0.72,
        "month": 6.0,
        "day_of_week": 2.0,
    }])[FEATURE_NAMES]
