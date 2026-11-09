"""Ad-duration intelligence — "how many SECONDS of ad work best for me?"

Answers, per YouTube format and per candidate creative length, which duration
is expected to hold the most attention for THIS product, objective, audience
and budget — and backs it with a viewable retention curve.

Evidence model (transparent, three layers):

1. BASE EFFECTIVENESS PRIOR — documented heuristics from Google's own creative
   guidance (6s bumpers for reach, ~15s skippable sweet spot, Shorts <20s
   complete more, in-feed thumbnail click intent). These are assumptions,
   labeled MODEL PREDICTION when they drive an output alone.

2. CONTEXT ADJUSTMENTS — audience age (younger -> shorter), category
   "demo need" (products that need explanation reward longer holds), budget
   band (small budgets favor cheaper-to-produce short cuts).

3. LIVE RESEARCH SIGNAL — when YouTube Data API research rows exist for the
   analysis, real public videos are bucketed by duration and their REAL
   median engagement per bucket nudges the overlapping duration options.
   Rows used here are labeled LIVE DATA.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import SUPPORTED_FORMATS
from app.models.analysis import ProductAnalysis
from app.models.research import ResearchVideo

# --------------------------------------------------------------------------
# 1. Duration catalogue + base effectiveness per objective (documented priors)
# --------------------------------------------------------------------------
# effectiveness = expected attention-hold quality for the objective, 0..1.
OBJECTIVES = ["Brand Awareness", "Video Views", "Website Traffic", "Leads", "Sales / Conversions"]

@dataclass(frozen=True)
class DurationOption:
    key: str
    format_key: str
    label: str
    seconds: int          # representative length for charts
    seconds_label: str    # human range, e.g. "16-30s"
    base: dict[str, float]
    non_skippable: bool = False
    note: str = ""


DURATION_CATALOGUE: list[DurationOption] = [
    # ---- In-Stream (skippable unless noted) --------------------------------
    DurationOption("in_stream_6s_bumper", "in_stream", "6s bumper (non-skippable)", 6, "6s",
                   {"Brand Awareness": 0.86, "Video Views": 0.70, "Website Traffic": 0.50,
                    "Leads": 0.42, "Sales / Conversions": 0.48},
                   non_skippable=True,
                   note="Non-skippable reach wall — message must be a single hook."),
    DurationOption("in_stream_15s", "in_stream", "15s skippable in-stream", 15, "~15s",
                   {"Brand Awareness": 0.90, "Video Views": 0.88, "Website Traffic": 0.82,
                    "Leads": 0.78, "Sales / Conversions": 0.84},
                   note="Google's skippable sweet spot: hook + one proof point + CTA."),
    DurationOption("in_stream_20s", "in_stream", "20s skippable in-stream", 20, "~20s",
                   {"Brand Awareness": 0.83, "Video Views": 0.86, "Website Traffic": 0.84,
                    "Leads": 0.83, "Sales / Conversions": 0.87}),
    DurationOption("in_stream_30s", "in_stream", "30s skippable in-stream", 30, "~30s",
                   {"Brand Awareness": 0.74, "Video Views": 0.80, "Website Traffic": 0.86,
                    "Leads": 0.89, "Sales / Conversions": 0.90},
                   note="Room for demo + objection handling; watch the 5s skip cliff."),
    DurationOption("in_stream_60s_plus", "in_stream", "60s+ long-form in-stream", 75, "60s+",
                   {"Brand Awareness": 0.55, "Video Views": 0.64, "Website Traffic": 0.70,
                    "Leads": 0.78, "Sales / Conversions": 0.72},
                   note="Deep storytelling/education; best as remarketing, not cold reach."),
    # ---- Shorts ------------------------------------------------------------
    DurationOption("shorts_up_to_15s", "shorts", "Shorts up to 15s", 15, "≤15s",
                   {"Brand Awareness": 0.88, "Video Views": 0.92, "Website Traffic": 0.74,
                    "Leads": 0.58, "Sales / Conversions": 0.64},
                   note="Highest completion odds; loop-friendly hooks."),
    DurationOption("shorts_16_30s", "shorts", "Shorts 16-30s", 30, "16-30s",
                   {"Brand Awareness": 0.84, "Video Views": 0.86, "Website Traffic": 0.78,
                    "Leads": 0.64, "Sales / Conversions": 0.72},
                   note="Hook (0-3s) + payoff + CTA; the Shorts workhorse."),
    DurationOption("shorts_31_60s", "shorts", "Shorts 31-60s", 60, "31-60s",
                   {"Brand Awareness": 0.72, "Video Views": 0.74, "Website Traffic": 0.68,
                    "Leads": 0.56, "Sales / Conversions": 0.62},
                   note="Mini-stories and tutorials; swipe risk rises after 30s."),
    # ---- In-Feed -----------------------------------------------------------
    DurationOption("in_feed_15_30s", "in_feed", "In-Feed 15-30s", 30, "15-30s",
                   {"Brand Awareness": 0.62, "Video Views": 0.72, "Website Traffic": 0.90,
                    "Leads": 0.84, "Sales / Conversions": 0.82},
                   note="Viewer chose the click — front-load the value, keep CTA visible."),
    DurationOption("in_feed_31_60s", "in_feed", "In-Feed 31-60s", 60, "31-60s",
                   {"Brand Awareness": 0.58, "Video Views": 0.66, "Website Traffic": 0.86,
                    "Leads": 0.88, "Sales / Conversions": 0.86},
                   note="Considered explainers for high-intent thumbnail clickers."),
    DurationOption("in_feed_61_90s", "in_feed", "In-Feed 61-90s", 90, "61-90s",
                   {"Brand Awareness": 0.50, "Video Views": 0.56, "Website Traffic": 0.76,
                    "Leads": 0.80, "Sales / Conversions": 0.78},
                   note="Longest in-feed option; only with strong thumbnail promise."),
]

# Categories where the product needs demonstration/explanation -> longer holds win
DEMO_HEAVY_CATEGORIES = {
    "electronics": 1.10, "home_kitchen": 1.08, "education_courses": 1.08,
    "software_app": 1.08, "fitness_health": 1.05, "toys_kids": 1.04,
    "automotive": 1.06, "sports_equipment": 1.04,
}
VISUAL_IMPULSE_CATEGORIES = {
    "fashion_apparel": 1.10, "food_beverage": 1.12, "beauty_skincare": 1.08,
    "books_media": 1.05, "jewelry_accessories": 1.02,
}

# --------------------------------------------------------------------------
# 2. Retention curve models (labeled MODEL PREDICTION)
# --------------------------------------------------------------------------
def retention_curve(opt: DurationOption, hold_quality: float) -> list[dict]:
    """% of reached audience still watching at t seconds.

    Documented shape model, parameters scaled by the option's hold quality:
      * non-skippable bumpers: near-flat (viewers cannot skip)
      * skippable in-stream: 5-second skip cliff then exponential decay
      * Shorts: swipe decay, steep in the first 3 seconds
      * in-feed: self-selected viewers, gentle decay after the click
    """
    dur = max(opt.seconds, 6)
    if opt.non_skippable:
        k = 0.004
        end = 0.92 + 0.06 * hold_quality
        pts = [(0, 100.0), (dur, round(100 * end, 1))]
        return [{"t": t, "held": held} for t, held in pts]

    if opt.format_key == "in_stream":
        s5 = 0.55 + 0.25 * hold_quality           # survivors at the 5s cliff
        k = 0.02 + 0.03 * (1.0 - hold_quality)    # post-cliff decay rate
        times = sorted({1, 5, *range(10, dur + 1, 5), dur})
        pts = []
        for t in times:
            if t <= 5:
                held = 100.0 - (100.0 - 100 * s5) * (t / 5.0)
            else:
                held = 100 * s5 * pow(2.718281828, -k * (t - 5))
            pts.append((t, round(max(held, 2.0), 1)))
        return [{"t": t, "held": held} for t, held in pts]

    if opt.format_key == "shorts":
        s3 = 0.62 + 0.25 * hold_quality           # survivors after the 3s swipe window
        k = 0.015 + 0.02 * (1.0 - hold_quality)
        times = sorted({1, 3, *range(5, dur + 1, 5), dur})
        pts = []
        for t in times:
            if t <= 3:
                held = 100.0 - (100.0 - 100 * s3) * (t / 3.0)
            else:
                held = 100 * s3 * pow(2.718281828, -k * (t - 3))
            pts.append((t, round(max(held, 2.0), 1)))
        return [{"t": t, "held": held} for t, held in pts]

    # in-feed: self-selected audience — click intent helps, but drop-off is real
    end = 0.48 + 0.30 * hold_quality
    k = 0.016
    times = sorted({1, 5, *range(10, dur + 1, 10), dur})
    return [{"t": t, "held": round(max(100.0 * (end + (1 - end) * pow(2.718281828, -k * t)), 2.0), 1)}
            for t in times]


def _auc_hold(points: list[dict]) -> float:
    """Average % held across the duration (trapezoid area / span)."""
    if len(points) < 2:
        return points[0]["held"] if points else 0.0
    area = 0.0
    for a, b in zip(points, points[1:]):
        area += (a["held"] + b["held"]) / 2.0 * (b["t"] - a["t"])
    return round(area / max(points[-1]["t"], 1), 1)


# --------------------------------------------------------------------------
# 3. LIVE research buckets — real public videos grouped by length
# --------------------------------------------------------------------------
LIVE_BUCKETS = [
    ("0-15s", 0, 15), ("16-30s", 16, 30), ("31-60s", 31, 60),
    ("61-180s", 61, 180), ("180s+", 181, 10**9),
]


def live_duration_analysis(videos: list[dict]) -> dict:
    usable = [v for v in videos if (v.get("views") or 0) > 0 and (v.get("duration_seconds") or 0) > 0]
    if not usable:
        return {"label": "NO DATA", "buckets": [], "scatter": [], "videos_used": 0,
                "note": "No live YouTube research rows for this analysis yet."}

    def _median(xs: list[float]) -> float:
        s = sorted(xs)
        n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

    overall_eng = _median([v.get("engagement_rate") or 0.0 for v in usable]) or 0.0

    buckets = []
    for label, lo, hi in LIVE_BUCKETS:
        rows = [v for v in usable if lo <= v["duration_seconds"] <= hi]
        if not rows:
            buckets.append({"bucket": label, "count": 0, "median_views": 0,
                            "median_engagement": 0.0, "engagement_index": None})
            continue
        med_eng = _median([(v.get("engagement_rate") or 0.0) for v in rows])
        idx = round(med_eng / overall_eng, 2) if overall_eng > 0 else None
        buckets.append({
            "bucket": label, "count": len(rows),
            "median_views": int(_median([float(v["views"]) for v in rows])),
            "median_engagement": round(med_eng, 5),
            "engagement_index": idx,   # 1.0 = niche average
        })

    scatter = [{
        "seconds": min(v["duration_seconds"], 600),   # cap axis for readability
        "engagement_rate": round((v.get("engagement_rate") or 0.0) * 100, 3),
        "views": v["views"],
        "title": (v.get("title") or "")[:60],
    } for v in usable]

    return {
        "label": "LIVE DATA",
        "buckets": buckets,
        "scatter": scatter,
        "videos_used": len(usable),
        "note": ("Real public YouTube videos for this product, grouped by length. "
                 "Engagement index compares each bucket's median engagement to the niche average."),
    }


def _med_eng(rows: list[dict]) -> float:
    vals = sorted((v.get("engagement_rate") or 0.0) for v in rows)
    if not vals:
        return 0.0
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _live_adjustment(opt: DurationOption, buckets: list[dict]) -> tuple[float, str]:
    """Nudge overlapping duration options using REAL bucket engagement index."""
    sec = opt.seconds
    if sec <= 15:
        b = next((x for x in buckets if x["bucket"] == "0-15s"), None)
    elif sec <= 30:
        b = next((x for x in buckets if x["bucket"] == "16-30s"), None)
    elif sec <= 60:
        b = next((x for x in buckets if x["bucket"] == "31-60s"), None)
    elif sec <= 180:
        b = next((x for x in buckets if x["bucket"] == "61-180s"), None)
    else:
        b = next((x for x in buckets if x["bucket"] == "180s+"), None)
    if not b or not b.get("count") or b.get("engagement_index") is None:
        return 1.0, ""
    idx = float(b["engagement_index"])
    adj = max(0.85, min(1.15, 1.0 + 0.12 * (idx - 1.0)))
    if abs(adj - 1.0) < 0.01:
        return 1.0, ""
    direction = "above" if idx > 1 else "below"
    return adj, (f"real {b['bucket']} videos in this niche engage {abs(idx - 1) * 100:.0f}% "
                 f"{direction} average (LIVE DATA)")


# --------------------------------------------------------------------------
# 4. Main entry point
# --------------------------------------------------------------------------
def compute_duration_plan(db: Session, analysis: ProductAnalysis) -> dict:
    text = f"{analysis.product.name or ''} {analysis.product.description or ''}".lower()
    category_key = (analysis.audience or {}).get("category_key") or ""
    if not category_key:
        from app.services.knowledge import classify_category
        profile, _ = classify_category(text)
        category_key = profile.key

    age_w = (analysis.audience or {}).get("age_weights") or {}
    young_share = float(age_w.get("18-24", 0.3)) + float(age_w.get("25-34", 0.35))
    objective = analysis.objective or "Sales / Conversions"
    budget = float(analysis.product.total_budget or 0.0)
    small_budget = budget < 25_000  # documented band: short cuts are cheaper to produce

    demo_factor = DEMO_HEAVY_CATEGORIES.get(category_key, 1.0)
    impulse_factor = VISUAL_IMPULSE_CATEGORIES.get(category_key, 1.0)

    live_videos = []
    if analysis.youtube_research_status == "live":
        rows = db.execute(
            select(ResearchVideo).where(ResearchVideo.analysis_id == analysis.id)
        ).scalars().all()
        live_videos = [{
            "views": v.views, "duration_seconds": v.duration_seconds,
            "engagement_rate": v.engagement_rate, "title": v.title,
        } for v in rows]
    live = live_duration_analysis(live_videos)
    live_buckets = live["buckets"]

    recommendations = []
    best_overall: dict | None = None
    curves = []

    for fmt_key, fmt_label in SUPPORTED_FORMATS.items():
        scored = []
        for opt in DURATION_CATALOGUE:
            if opt.format_key != fmt_key:
                continue
            base = opt.base.get(objective, 0.6)
            # context adjustments (documented, additive up to ~±20%)
            if opt.non_skippable:
                score = base * (1.0 + 0.10 * (1.0 - young_share))
            else:
                score = base * (1.0 + 0.14 * (0.5 - young_share) * (1 if opt.seconds <= 30 else -1.2))
            score *= (demo_factor if opt.seconds >= 30 else (2.0 - demo_factor) if opt.seconds <= 15 else 1.0)
            if impulse_factor != 1.0 and opt.format_key == "shorts":
                score *= impulse_factor if opt.seconds <= 30 else (2.0 - impulse_factor)
            if small_budget:
                score *= 1.06 if opt.seconds <= 15 else 0.97
            adj, live_note = _live_adjustment(opt, live_buckets)
            score *= adj
            score = max(0.05, min(0.98, score))

            hq = score  # hold quality drives the curve shape
            curve = retention_curve(opt, hq)
            hold = _auc_hold(curve)
            scored.append({
                "duration_key": opt.key,
                "label": opt.label,
                "seconds": opt.seconds,
                "seconds_label": opt.seconds_label,
                "non_skippable": opt.non_skippable,
                "note": opt.note,
                "score": round(score, 3),
                "expected_hold_rate": hold,       # avg % of ad watched
                "live_adjustment": live_note,
            })

        scored.sort(key=lambda s: s["score"], reverse=True)
        best = scored[0]
        reason = (f"{best['label']} scores highest for “{objective}” in the "
                  f"{category_key.replace('_', ' ')} category — expected hold rate {best['expected_hold_rate']}% "
                  f"of the ad watched. {best['note']}").strip()
        if best.get("live_adjustment"):
            reason += f" Backed by: {best['live_adjustment']}."
        recommendations.append({
            "format_key": fmt_key,
            "format_label": fmt_label,
            "best": best,
            "alternatives": scored[1:3],
            "all": scored,
        })
        curves.append({
            "format_key": fmt_key,
            "format_label": fmt_label,
            "duration_key": best["duration_key"],
            "label": f"{fmt_label} — {best['seconds_label']}",
            "seconds": best["seconds"],
            "points": retention_curve(next(o for o in DURATION_CATALOGUE if o.key == best["duration_key"]), best["score"]),
        })
        if best_overall is None or best["score"] > best_overall["score"]:
            best_overall = {
                "format_key": fmt_key,
                "format_label": fmt_label,
                **best,
                "reason": reason,
            }

    plan_label = "LIVE DATA" if live["label"] == "LIVE DATA" else "MODEL PREDICTION"
    return {
        "analysis_id": analysis.id,
        "objective": objective,
        "data_source_label": plan_label,
        "recommendations": recommendations,
        "overall_best": best_overall,
        "retention_curves": curves,
        "live_research": live,
        "methodology": (
            "Duration scoring = documented creative priors per objective (Google creative guidance), "
            "adjusted for audience age mix, category demo-need, budget band, and — when live YouTube "
            "research rows exist — the REAL engagement of public videos in each duration bucket. "
            "Retention curves are MODEL PREDICTION shapes for planning, not measured watches."
        ),
    }
