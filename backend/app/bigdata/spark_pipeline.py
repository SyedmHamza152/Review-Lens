"""Apache Spark (PySpark, local mode) pipeline.

Same contract as the Pandas pipeline: ingest → clean → transform → aggregate.
Runs fully locally (local[*]); requires Java 17+. If Java or PySpark is
missing, a typed error is raised and the benchmark records it honestly.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SparkUnavailable(Exception):
    pass


def _spark_session():
    try:
        from pyspark.sql import SparkSession
    except ImportError as e:
        raise SparkUnavailable("pyspark is not installed (pip install pyspark)") from e
    import shutil

    if not shutil.which("java"):
        raise SparkUnavailable("Java runtime not found — install Java 17+ to run Spark")
    spark = (
        SparkSession.builder.master("local[*]")
        .appName("AdPilot-BigData")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def run_pipeline(csv_path: str | Path) -> dict:
    from pyspark.sql import functions as F

    spark = _spark_session()
    try:
        df = (
            spark.read.csv(str(csv_path), header=True, inferSchema=True)
        )
        n_raw = df.count()

        # ---------- cleaning ----------
        df = df.dropna(subset=["campaign_id", "ad_format", "impressions", "clicks", "spend"]).dropDuplicates()
        num = ["impressions", "clicks", "spend", "conversions", "revenue", "video_views"]
        for c in num:
            df = df.withColumn(c, F.when(F.col(c) < 0, 0).otherwise(F.col(c)))
        df = df.filter(F.col("impressions") > 0).cache()

        # ---------- transformation ----------
        df = (
            df.withColumn("ctr", F.when(F.col("impressions") > 0, F.col("clicks") / F.col("impressions")).otherwise(0.0))
              .withColumn("cpc", F.when(F.col("clicks") > 0, F.col("spend") / F.col("clicks")).otherwise(0.0))
              .withColumn("cvr", F.when(F.col("clicks") > 0, F.col("conversions") / F.col("clicks")).otherwise(0.0))
              .withColumn("roas", F.when(F.col("spend") > 0, F.col("revenue") / F.col("spend")).otherwise(0.0))
        )

        # ---------- aggregations ----------
        totals_row = df.agg(
            F.count("*").alias("rows"),
            F.sum("impressions").alias("impressions"),
            F.sum("clicks").alias("clicks"),
            F.round(F.sum("spend"), 2).alias("spend"),
            F.round(F.sum("conversions"), 2).alias("conversions"),
            F.round(F.sum("revenue"), 2).alias("revenue"),
            F.sum("video_views").alias("video_views"),
        ).collect()[0]

        t = totals_row.asDict()
        t_imp, t_clk = int(t["impressions"] or 0), int(t["clicks"] or 0)
        t_spend, t_conv = float(t["spend"] or 0), float(t["conversions"] or 0)
        totals = {
            "rows": int(t["rows"] or 0),
            "rows_raw": int(n_raw),
            "impressions": t_imp,
            "clicks": t_clk,
            "spend": t_spend,
            "conversions": t_conv,
            "revenue": float(t["revenue"] or 0),
            "video_views": int(t["video_views"] or 0),
            "ctr": round(100 * t_clk / t_imp, 4) if t_imp else None,
            "cpc": round(t_spend / t_clk, 4) if t_clk else None,
            "cpa": round(t_spend / t_conv, 4) if t_conv else None,
            "cvr": round(100 * t_conv / t_clk, 4) if t_clk else None,
            "roas": round(float(t["revenue"] or 0) / t_spend, 4) if t_spend else None,
        }

        by_format = (
            df.groupBy("ad_format").agg(
                F.sum("impressions").alias("impressions"),
                F.sum("clicks").alias("clicks"),
                F.round(F.sum("spend"), 2).alias("spend"),
                F.round(F.sum("conversions"), 2).alias("conversions"),
                F.round(F.sum("revenue"), 2).alias("revenue"),
                F.sum("video_views").alias("video_views"),
            )
            .withColumn("roas", F.round(F.col("revenue") / F.col("spend"), 4))
            .withColumn("ctr", F.round(100 * F.col("clicks") / F.col("impressions"), 4))
            .orderBy(F.desc("roas"))
        ).collect()

        return {
            "totals": totals,
            "by_format": [r.asDict() for r in by_format],
            "engine": "spark-local",
        }
    finally:
        spark.stop()
