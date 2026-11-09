"""Pandas pipeline — ingestion → cleaning → transformation → aggregation.

Two ingestion modes (auto-selected by file size, both full pandas):
  * in-memory: a single read_csv with explicit dtypes (fast, ~3 GB RAM at 10M rows);
  * chunked: iterates read_csv(chunksize=...) with incremental groupby aggregation
    and a two-pass keep-first deduplication — the standard pandas pattern for
    larger-than-memory files. Mode is recorded in the result for honesty.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DTYPES = {
    "campaign_id": "category",
    "campaign_name": "category",
    "platform": "category",
    "ad_format": "category",
    "age_group": "category",
    "gender": "category",
    "city": "category",
    "device": "category",
    "marketing_objective": "category",
    "impressions": "int64",
    "clicks": "int64",
    "video_views": "int64",
    "spend": "float64",
    "conversions": "float64",
    "revenue": "float64",
}

CHUNK_ROWS = 500_000
CHUNKED_MODE_FILE_MB = 300  # above this, use the chunked engine


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["campaign_id", "ad_format", "impressions", "clicks", "spend"])
    df = df.drop_duplicates()
    num = ["impressions", "clicks", "spend", "conversions", "revenue", "video_views"]
    df[num] = df[num].clip(lower=0)
    return df[df["impressions"] > 0].copy()


def _add_row_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df["ctr"] = np.where(df["impressions"] > 0, df["clicks"] / df["impressions"], 0.0)
    df["cpc"] = np.where(df["clicks"] > 0, df["spend"] / df["clicks"], 0.0)
    df["cvr"] = np.where(df["clicks"] > 0, df["conversions"] / df["clicks"], 0.0)
    df["roas"] = np.where(df["spend"] > 0, df["revenue"] / df["spend"], 0.0)
    return df


def _finalize(totals: dict, by_format: pd.DataFrame, by_campaign: pd.DataFrame,
              by_city: pd.Series, by_age: pd.Series, by_device: pd.Series,
              trend: pd.DataFrame, mode: str, dedup_removed: int) -> dict:
    totals["ctr"] = round(100 * totals["clicks"] / totals["impressions"], 4) if totals["impressions"] else None
    totals["cpc"] = round(totals["spend"] / totals["clicks"], 4) if totals["clicks"] else None
    totals["cpa"] = round(totals["spend"] / totals["conversions"], 4) if totals["conversions"] else None
    totals["cvr"] = round(100 * totals["conversions"] / totals["clicks"], 4) if totals["clicks"] else None
    totals["roas"] = round(totals["revenue"] / totals["spend"], 4) if totals["spend"] else None

    bf = by_format.copy()
    bf["roas"] = (bf["revenue"] / bf["spend"]).round(4)
    bf["cpa"] = np.where(bf["conversions"] > 0, bf["spend"] / bf["conversions"].replace(0, np.nan), 0).round(2)
    bf["ctr"] = (100 * bf["clicks"] / bf["impressions"]).round(4)
    bf = bf.sort_values("roas", ascending=False)
    if bf.index.name != "ad_format":
        bf = bf.set_index("ad_format") if "ad_format" in bf.columns else bf
    rec_share = (bf["roas"] / bf["roas"].sum()).round(4)
    bf_records = bf.reset_index().to_dict(orient="records")

    return {
        "totals": totals,
        "by_format": bf_records,
        "top_campaigns": by_campaign.to_dict(orient="records"),
        "by_city": [{"city": k, "revenue": round(float(v), 2)} for k, v in by_city.items()],
        "by_age": [{"age_group": k, "conversions": round(float(v), 2)} for k, v in by_age.items()],
        "by_device": [{"device": k, "spend": round(float(v), 2)} for k, v in by_device.items()],
        "trend": [{"month": str(k), "spend": round(float(v["spend"]), 2), "revenue": round(float(v["revenue"]), 2)}
                  for k, v in trend.iterrows()],
        "budget_recommendation": [
            {"format": str(r["ad_format"]), "roas": float(r["roas"]), "suggested_share": float(rec_share.iloc[i])}
            for i, r in enumerate(bf_records)
        ],
        "ingestion_mode": mode,
        "dedup_rows_removed": dedup_removed,
    }


def run_pipeline(csv_path: str | Path, chunked: bool | None = None) -> dict:
    csv_path = Path(csv_path)
    size_mb = csv_path.stat().st_size / 1048576
    use_chunked = chunked if chunked is not None else size_mb > CHUNKED_MODE_FILE_MB
    if not use_chunked:
        return _run_in_memory(csv_path)
    return _run_chunked(csv_path)


def _run_in_memory(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path, dtype=DTYPES, parse_dates=["date"])
    n_raw = len(df)
    df = _clean(df)
    df = _add_row_metrics(df)
    df["month"] = df["date"].dt.to_period("M")

    totals = {
        "rows": int(len(df)),
        "rows_raw": int(n_raw),
        "impressions": int(df["impressions"].sum()),
        "clicks": int(df["clicks"].sum()),
        "spend": round(float(df["spend"].sum()), 2),
        "conversions": round(float(df["conversions"].sum()), 2),
        "revenue": round(float(df["revenue"].sum()), 2),
        "video_views": int(df["video_views"].sum()),
    }
    by_format = df.groupby("ad_format", observed=True).agg(
        impressions=("impressions", "sum"), clicks=("clicks", "sum"),
        spend=("spend", "sum"), conversions=("conversions", "sum"),
        revenue=("revenue", "sum"), video_views=("video_views", "sum"),
    )
    by_campaign = df.groupby(["campaign_id", "campaign_name"], observed=True).agg(
        spend=("spend", "sum"), conversions=("conversions", "sum"), revenue=("revenue", "sum"),
    ).reset_index().sort_values("revenue", ascending=False).head(20)
    by_city = df.groupby("city", observed=True)["revenue"].sum().sort_values(ascending=False).head(10)
    by_age = df.groupby("age_group", observed=True)["conversions"].sum()
    by_device = df.groupby("device", observed=True)["spend"].sum()
    trend = df.groupby("month", observed=True).agg(spend=("spend", "sum"), revenue=("revenue", "sum"))

    # rows dropped by the cleaning stage (na + duplicates + non-positive impressions)
    dedup_removed = n_raw - int(len(df))
    return _finalize(totals, by_format, by_campaign, by_city, by_age, by_device, trend,
                     "in-memory", max(dedup_removed, 0))


def _run_chunked(csv_path: Path) -> dict:
    """Incremental pandas: read_csv(chunksize) + per-chunk groupby accumulation.

    Deduplication uses pandas' own row hashing (pd.util.hash_pandas_object):
    pass 1 collects hashes + aggregates; if duplicates exist, a second pass
    re-aggregates with keep-first semantics (matching the in-memory mode).
    """
    reader = pd.read_csv(csv_path, dtype=DTYPES, parse_dates=["date"], chunksize=CHUNK_ROWS)

    hash_parts: list[np.ndarray] = []

    def agg_chunk(df: pd.DataFrame) -> dict:
        return {
            "totals": {
                "rows": int(len(df)),
                "impressions": int(df["impressions"].sum()),
                "clicks": int(df["clicks"].sum()),
                "spend": float(df["spend"].sum()),
                "conversions": float(df["conversions"].sum()),
                "revenue": float(df["revenue"].sum()),
                "video_views": int(df["video_views"].sum()),
            },
            "by_format": df.groupby("ad_format", observed=True).agg(
                impressions=("impressions", "sum"), clicks=("clicks", "sum"),
                spend=("spend", "sum"), conversions=("conversions", "sum"),
                revenue=("revenue", "sum"), video_views=("video_views", "sum")),
            "by_campaign": df.groupby(["campaign_id", "campaign_name"], observed=True).agg(
                spend=("spend", "sum"), conversions=("conversions", "sum"), revenue=("revenue", "sum")),
            "by_city": df.groupby("city", observed=True)["revenue"].sum(),
            "by_age": df.groupby("age_group", observed=True)["conversions"].sum(),
            "by_device": df.groupby("device", observed=True)["spend"].sum(),
            "by_month": df.groupby(df["date"].dt.to_period("M"), observed=True).agg(
                spend=("spend", "sum"), revenue=("revenue", "sum")),
        }

    def combine(acc: dict, part: dict) -> None:
        for k in ("totals",):
            for kk, v in part[k].items():
                acc[k][kk] = acc[k].get(kk, 0) + v
        for k in ("by_format", "by_campaign", "by_month"):
            acc[k] = pd.concat([acc[k], part[k]]).groupby(level=list(range(part[k].index.nlevels))).sum()
        for k in ("by_city", "by_age", "by_device"):
            acc[k] = acc[k].add(part[k], fill_value=0)

    def empty_acc() -> dict:
        return {
            "totals": {"rows": 0, "impressions": 0, "clicks": 0, "spend": 0.0,
                       "conversions": 0.0, "revenue": 0.0, "video_views": 0},
            "by_format": pd.DataFrame(), "by_campaign": pd.DataFrame(),
            "by_city": pd.Series(dtype="float64"), "by_age": pd.Series(dtype="float64"),
            "by_device": pd.Series(dtype="float64"), "by_month": pd.DataFrame(),
        }

    acc = empty_acc()
    n_raw = 0
    for chunk in reader:
        n_raw += len(chunk)
        c = _clean(chunk)
        hash_parts.append(pd.util.hash_pandas_object(c, index=False).to_numpy(dtype=np.uint64))
        combine(acc, agg_chunk(c))

    all_hashes = np.concatenate(hash_parts)
    uniq, counts = np.unique(all_hashes, return_counts=True)
    dup_hashes = uniq[counts > 1]
    dedup_removed = int(len(all_hashes) - len(uniq))

    if dedup_removed > 0:
        # pass 2 with keep-first semantics over the (tiny) duplicated-hash set
        acc = empty_acc()
        seen_dup: set[int] = set()
        reader2 = pd.read_csv(csv_path, dtype=DTYPES, parse_dates=["date"], chunksize=CHUNK_ROWS)
        for chunk in reader2:
            c = _clean(chunk)
            if len(c):
                h = pd.util.hash_pandas_object(c, index=False).to_numpy(dtype=np.uint64)
                is_dup = np.isin(h, dup_hashes)
                keep = ~is_dup
                if is_dup.any():
                    for i in np.nonzero(is_dup)[0]:
                        hi = int(h[i])
                        if hi in seen_dup:
                            keep[i] = False
                        else:
                            seen_dup.add(hi)
                c = c.iloc[np.nonzero(keep)[0]]
                if len(c):
                    combine(acc, agg_chunk(c))

    totals = dict(acc["totals"])
    totals["spend"] = round(totals["spend"], 2)
    totals["conversions"] = round(totals["conversions"], 2)
    totals["revenue"] = round(totals["revenue"], 2)
    totals["rows_raw"] = int(n_raw)

    by_campaign = acc["by_campaign"].reset_index().sort_values("revenue", ascending=False).head(20)
    by_city = acc["by_city"].sort_values(ascending=False).head(10)
    return _finalize(totals, acc["by_format"], by_campaign, by_city,
                     acc["by_age"], acc["by_device"], acc["by_month"], "chunked", dedup_removed)
