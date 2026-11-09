"""Genuine MapReduce-style pipeline in pure Python (mapper → shuffle/sort → reducer).

This is a DOCUMENTED, SINGLE-MACHINE implementation of the MapReduce
paradigm (multiprocessing pools, chunked mappers, key-grouped reducers).
It is NOT a distributed Hadoop cluster — no HDFS/YARN. The distinction is
stated here and in the UI because honesty about infrastructure matters.

Flow (two MapReduce jobs, mirroring classic Hadoop chains):
  JOB 1 — deduplication: mappers hash each raw row (blake2b-64); the reducer
          unions the hash sets. If any cross-chunk duplicates exist, a second
          mapper pass re-aggregates only distinct rows (fork shares the hash
          set copy-on-write). This matches the pandas `drop_duplicates`
          cleaning stage so both engines agree exactly.
  JOB 2 — aggregation: mappers emit (ad_format → [impressions, clicks, spend,
          conversions, revenue, views]) with per-chunk combiners; the reducer
          groups by key and sums; a final stage derives CTR/CPC/CPA/CVR/ROAS.
"""
from __future__ import annotations

import csv
import hashlib
import logging
import multiprocessing as mp
from collections import defaultdict
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

COLUMNS = ["impressions", "clicks", "spend", "conversions", "revenue", "video_views"]

# Must mirror app.bigdata.generator.HEADER (index lookup uses these names).
HEADER = [
    "date", "campaign_id", "campaign_name", "platform", "ad_format",
    "impressions", "clicks", "spend", "conversions", "revenue", "video_views",
    "age_group", "gender", "city", "device", "marketing_objective",
]


def _chunk_plan(path: Path, n_chunks: int) -> list[tuple[int, int]]:
    """Precompute (start_byte, n_lines) chunks via a fast binary scan.

    Line-count based chunking avoids csv.tell() pitfalls entirely: each mapper
    knows exactly how many complete rows to read from its start offset.
    """
    total_lines = 0
    with path.open("rb") as f:
        for _ in f:
            total_lines += 1
    data_lines = max(total_lines - 1, 0)  # minus header
    chunk_lines = max(data_lines // max(n_chunks, 1), 1)
    chunks: list[tuple[int, int]] = []
    with path.open("rb") as f:
        f.readline()  # header
        offset = f.tell()
        remaining = data_lines
        while remaining > 0:
            n = min(chunk_lines, remaining)
            chunks.append((offset, n))
            for _ in range(n):
                if not f.readline():
                    break
            offset = f.tell()
            remaining -= n
    return chunks


def _parse_float(x: str) -> float:
    try:
        return float(x)
    except ValueError:
        return 0.0


def _row_hash(line: str) -> int:
    return int.from_bytes(hashlib.blake2b(line.encode("utf-8"), digest_size=8).digest(), "big")


_GLOBAL_DISTINCT: set[int] | None = None


def _init_workers(distinct: set[int] | None) -> None:  # pragma: no cover - pool init
    global _GLOBAL_DISTINCT
    _GLOBAL_DISTINCT = distinct


def _map_chunk(args: tuple[str, int, int, int, dict | None]) -> dict[str, list[float]]:
    """Mapper: parse exactly `n_lines` complete data rows from `start`.

    Dedup pass 2 semantics (mirrors pandas drop_duplicates = keep first):
      * rows whose hash is globally duplicated are aggregated only by their
        OWNER chunk (the earliest chunk containing that hash),
      * and within the owner chunk only the first occurrence survives.
    """
    path, start, n_lines, chunk_idx, dup_owner = args
    out: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(COLUMNS))
    idx_fmt = HEADER.index("ad_format")
    idx = {name: HEADER.index(name) for name in ["ad_format"] + COLUMNS}
    seen_local: set[int] = set()
    with open(path, "r", encoding="utf-8", newline="") as f:
        f.seek(start)
        # NOTE: planner offsets always sit exactly at a line boundary (computed
        # with readline() in binary mode), so no partial-line skip is needed —
        # skipping here would silently drop one row per chunk.
        processed = 0
        for line in f:
            if processed >= n_lines:
                break
            processed += 1
            if dup_owner is not None:
                h = _row_hash(line)
                owner = dup_owner.get(h)
                if owner is None:
                    pass  # not a duplicated hash — keep
                elif owner != chunk_idx:
                    continue  # owned by an earlier chunk
                elif h in seen_local:
                    continue  # later duplicate inside the owner chunk
                else:
                    seen_local.add(h)
            row = line.rstrip("\r\n").split(",")
            try:
                key = row[idx_fmt]
                vec = out[key]
                vec[0] += float(row[idx["impressions"]])
                vec[1] += float(row[idx["clicks"]])
                vec[2] += _parse_float(row[idx["spend"]])
                vec[3] += _parse_float(row[idx["conversions"]])
                vec[4] += _parse_float(row[idx["revenue"]])
                vec[5] += float(row[idx["video_views"]])
            except (ValueError, IndexError):
                pass  # dirty row — skipped by the cleaning stage contract
    return dict(out)


def _map_hashes(args: tuple[str, int, int]) -> tuple[np.ndarray, dict[str, list[float]]]:
    """Dedup-job mapper: emit row hashes + combiner aggregates for the chunk."""
    path, start, n_lines = args
    hashes = np.empty(n_lines, dtype=np.uint64)
    out: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(COLUMNS))
    idx_fmt = HEADER.index("ad_format")
    idx = {name: HEADER.index(name) for name in ["ad_format"] + COLUMNS}
    with open(path, "r", encoding="utf-8", newline="") as f:
        f.seek(start)
        i = 0
        for line in f:
            if i >= n_lines:
                break
            hashes[i] = _row_hash(line)
            i += 1
            row = line.rstrip("\r\n").split(",")
            try:
                key = row[idx_fmt]
                vec = out[key]
                vec[0] += float(row[idx["impressions"]])
                vec[1] += float(row[idx["clicks"]])
                vec[2] += _parse_float(row[idx["spend"]])
                vec[3] += _parse_float(row[idx["conversions"]])
                vec[4] += _parse_float(row[idx["revenue"]])
                vec[5] += float(row[idx["video_views"]])
            except (ValueError, IndexError):
                pass
    return hashes, dict(out)


def _reduce(mapped: list[dict[str, list[float]]]) -> dict[str, list[float]]:
    """Reducer: sum vectors per key (shuffle/sort emulated by grouping)."""
    total: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(COLUMNS))
    for part in mapped:
        for key, vec in part.items():
            acc = total[key]
            for i, v in enumerate(vec):
                acc[i] += v
    return dict(total)


def _derive_metrics(reduced: dict[str, list[float]]) -> list[dict]:
    rows = []
    for key, vec in sorted(reduced.items()):
        impressions, clicks, spend, conversions, revenue, views = vec
        rows.append({
            "ad_format": key,
            "impressions": int(impressions),
            "clicks": int(clicks),
            "spend": round(spend, 2),
            "conversions": round(conversions, 2),
            "revenue": round(revenue, 2),
            "video_views": int(views),
            "ctr": round(100 * clicks / impressions, 4) if impressions else None,
            "cpc": round(spend / clicks, 4) if clicks else None,
            "cpa": round(spend / conversions, 4) if conversions else None,
            "cvr": round(100 * conversions / clicks, 4) if clicks else None,
            "roas": round(revenue / spend, 4) if spend else None,
        })
    return rows


def run_pipeline(csv_path: str | Path, workers: int | None = None) -> dict:
    """MapReduce execution with multiprocessing pools (local, in-process)."""
    path = Path(csv_path)
    workers = workers or max(mp.cpu_count() - 1, 1)
    n_chunks = workers * 4
    plan = _chunk_plan(path, n_chunks)
    tasks = [(str(path), start, n) for start, n in plan]

    def run_mappers(fn, items, *, init_args=None):
        if workers > 1 and len(items) > 1:
            ctx = mp.get_context("fork")
            with ctx.Pool(processes=workers, initializer=_init_workers,
                          initargs=init_args or (None,)) as pool:
                return pool.map(fn, items)
        return [fn(t) for t in items]

    # ---- JOB 1: dedup job (hashes + raw aggregates) ------------------------
    hash_tasks = [(t[0], t[1], t[2]) for t in tasks]
    results = run_mappers(_map_hashes, hash_tasks)
    chunk_hashes = [r[0] for r in results]
    all_hashes = np.concatenate(chunk_hashes)
    uniq, counts = np.unique(all_hashes, return_counts=True)
    dup_mask = counts > 1
    duplicates = int(counts[dup_mask].sum() - dup_mask.sum()) if dup_mask.any() else 0

    if duplicates > 0:
        # owner map: duplicated hash -> earliest chunk index containing it
        dup_hashes = uniq[dup_mask]
        dup_owner: dict[int, int] = {}
        for h in dup_hashes:
            for ci, arr in enumerate(chunk_hashes):
                if h in arr:  # arr is sorted as written; membership via search
                    dup_owner[int(h)] = ci
                    break
        agg_tasks = [(t[0], t[1], t[2], ci, dup_owner) for ci, t in enumerate(tasks)]
        mapped = run_mappers(_map_chunk, agg_tasks,
                             init_args=(set(int(x) for x in dup_hashes),))
        dedup_rows = duplicates
    else:
        agg_tasks = [(t[0], t[1], t[2], 0, None) for t in tasks]
        mapped = run_mappers(_map_chunk, agg_tasks)
        dedup_rows = 0

    reduced = _reduce(mapped)
    rows = _derive_metrics(reduced)

    t_imp = sum(r["impressions"] for r in rows)
    t_clk = sum(r["clicks"] for r in rows)
    t_spend = round(sum(r["spend"] for r in rows), 2)
    t_conv = round(sum(r["conversions"] for r in rows), 2)
    t_rev = round(sum(r["revenue"] for r in rows), 2)
    t_views = sum(r["video_views"] for r in rows)

    totals = {
        "rows": None,  # MapReduce counts combiner-level; row count not streamed
        "dedup_rows_removed": dedup_rows,
        "impressions": t_imp,
        "clicks": t_clk,
        "spend": t_spend,
        "conversions": t_conv,
        "revenue": t_rev,
        "video_views": t_views,
        "ctr": round(100 * t_clk / t_imp, 4) if t_imp else None,
        "cpc": round(t_spend / t_clk, 4) if t_clk else None,
        "cpa": round(t_spend / t_conv, 4) if t_conv else None,
        "cvr": round(100 * t_conv / t_clk, 4) if t_clk else None,
        "roas": round(t_rev / t_spend, 4) if t_spend else None,
    }
    return {"totals": totals, "by_format": rows,
            "implementation": "python-multiprocessing-mapreduce (not Hadoop)"}
