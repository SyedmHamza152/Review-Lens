"""Optimizer service — assembles evidence and drives the optimization engine.

Evidence blending (shrinkage toward priors):
    effective_param = (n_history × param_history + k_priors × param_prior) / (n_history + k_priors)

ML predictions, when a trained registry exists, act as a third evidence
source with their own pseudo-count. Every blend records its ingredients in
`evidence` strings so the UI can show exactly why an allocation was made.
"""
from __future__ import annotations

import logging
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import SUPPORTED_FORMATS
from app.models.analysis import ProductAnalysis
from app.models.campaign import Campaign, CampaignPerformance
from app.models.recommendation import BudgetRecommendation, OptimizationRun
from app.models.research import ResearchVideo
from app.optimization import engine as opt_engine
from app.optimization.coldstart import AOV_BY_BAND, FORMAT_PRIORS
from app.services.knowledge import FORMAT_OBJECTIVE_FIT  # re-exported from knowledge

logger = logging.getLogger(__name__)

PSEUDO_COUNT_PARAMS = 200_000.0   # impressions-equivalent weight of the priors
PSEUDO_COUNT_ML = 120_000.0       # impressions-equivalent weight of ML predictions
MIN_SAMPLE_FOR_TRUST = 30_000     # below this, priors dominate


def historical_metrics_by_format(db: Session, analysis: ProductAnalysis) -> dict[str, dict]:
    """Aggregate stored campaign performance per format (demo or live).

    SYNTHETIC rows are additionally modulated by the product's category
    profile (documented, see `_modulate_synthetic`): a fashion product's
    simulated Shorts history differs from an electronics product's. LIVE rows
    are NEVER touched — they pass through unmodified.
    """
    from app.services.metrics import MetricSet, merge_metric_sets

    rows = db.execute(
        select(CampaignPerformance, Campaign)
        .join(Campaign, CampaignPerformance.campaign_id == Campaign.id)
        .order_by(CampaignPerformance.date.desc())
        .limit(200_000)
    ).all()

    by_format: dict[str, list[MetricSet]] = {}
    for perf, camp in rows:
        ms = MetricSet(
            impressions=perf.impressions,
            clicks=perf.clicks,
            cost=perf.cost_micros / 1_000_000.0,
            conversions=perf.conversions,
            conversion_value=perf.conversion_value,
            video_views=perf.video_views,
            video_impressions=perf.video_impressions or perf.impressions,
            source="live" if camp.data_source_label == "LIVE DATA" else "synthetic",
        )
        by_format.setdefault(camp.format_key, []).append(ms)
    out: dict[str, dict] = {}
    for key, sets in by_format.items():
        merged = merge_metric_sets(sets)
        if merged.source != "live":
            merged = _modulate_synthetic(merged, key, analysis)
        out[key] = {
            "metrics": merged.to_dict(),
            "sample_size": int(merged.impressions),
            "source": merged.source,
        }
    return out


def _modulate_synthetic(ms, format_key: str, analysis: ProductAnalysis):
    """Make SIMULATED history product-aware (SYNTHETIC rows only).

    The static demo fixture would otherwise give every product identical
    "history" and identical charts. Each category profile carries documented
    format affinities; we modulate the synthetic engagement rates by the
    product's relative affinity for this format so a fashion product's
    simulated Shorts history genuinely differs from an electronics one.

    Modulation: rate_adjust = 0.80 + 0.40 × (affinity / mean_affinity),
    i.e. ±20% around 1.0 — applied to CTR and CVR only (costs follow the
    market, not the product). LIVE DATA never passes through here.
    """
    from app.services.knowledge import classify_category

    text = f"{analysis.product.name} {analysis.product.description}"  # type: ignore[union-attr]
    profile, _ = classify_category(text)
    affs = profile.format_affinity or {format_key: 1.0}
    mean_aff = sum(affs.values()) / max(len(affs), 1)
    rel = affs.get(format_key, 1.0) / (mean_aff or 1.0)
    factor = 0.80 + 0.40 * rel

    # CTR ×= factor  → clicks ×= factor
    # CVR ×= factor  → conversions = clicks_new × cvr_new = conversions × factor²
    # conversion_value ×= factor² keeps the AOV unchanged
    ms.clicks *= factor
    ms.conversions *= factor * factor
    ms.conversion_value *= factor * factor
    ms.extras["synthetic_modulation"] = round(factor, 3)
    return ms


def _blend(prior: float, historical: float | None, ml_value: float | None,
           n_hist: float, clamp: tuple[float, float] | None = None) -> float:
    """Weighted blend of prior / history / ML with shrinkage."""
    num = PSEUDO_COUNT_PARAMS * prior
    den = PSEUDO_COUNT_PARAMS
    if historical is not None and n_hist > 0:
        num += n_hist * historical
        den += n_hist
    if ml_value is not None and ml_value > 0:
        num += PSEUDO_COUNT_ML * ml_value
        den += PSEUDO_COUNT_ML
    val = num / den
    if clamp:
        val = min(max(val, clamp[0]), clamp[1])
    return val


def build_format_scores(
    analysis: ProductAnalysis,
    history: dict[str, dict],
    ml_predictor=None,
    research_videos: list[dict] | None = None,
) -> list[opt_engine.FormatScore]:
    from app.services.knowledge import classify_category

    text = f"{analysis.product.name} {analysis.product.description}"  # type: ignore[union-attr]
    profile, _conf = classify_category(text)
    aov = float((analysis.audience or {}).get("aov_estimate") or AOV_BY_BAND["medium"])

    age_w = (analysis.audience or {}).get("age_weights") or {}
    young_share = float(age_w.get("18-24", 0.3)) + float(age_w.get("25-34", 0.35))

    objective = analysis.objective or "Sales / Conversions"
    scores: list[opt_engine.FormatScore] = []

    for key, label in SUPPORTED_FORMATS.items():
        prior = FORMAT_PRIORS[key]
        hist = history.get(key)
        hist_m = hist["metrics"] if hist else None
        n_hist = float(hist["sample_size"]) if hist else 0.0

        ml_funnel = None
        if ml_predictor is not None:
            try:
                ml_funnel = ml_predictor(
                    format_key=key, objective=objective, category_key=profile.key,
                )
            except Exception as e:  # model problems must never break analysis
                logger.warning("ML predictor failed: %s", e)

        unit_cost = _blend(
            prior.unit_cost,
            (hist_m.get("cpv") if prior.pricing_model == "cpv" else hist_m.get("cpc")) if hist_m else None,
            ml_funnel.get("unit_cost") if ml_funnel else None,
            n_hist,
            clamp=(0.15, 60.0),
        )
        if prior.pricing_model == "cpv":
            view_rate = _blend(prior.view_rate, None, ml_funnel.get("view_rate") if ml_funnel else None, n_hist, clamp=(0.08, 0.55))
        else:
            view_rate = 0.0

        if prior.pricing_model == "cpv":
            click_rate_prior = prior.click_rate
            click_rate_hist = _ctr_of_views(hist_m) if hist_m else None
        else:
            click_rate_prior = prior.click_rate
            click_rate_hist = (hist_m.get("ctr") / 100.0) if hist_m and hist_m.get("ctr") else None
        click_rate = _blend(click_rate_prior, click_rate_hist, ml_funnel.get("click_rate") if ml_funnel else None, n_hist, clamp=(0.002, 0.5))

        cvr = _blend(prior.cvr, (hist_m.get("conversion_rate") / 100.0) if hist_m and hist_m.get("conversion_rate") else None,
                     ml_funnel.get("cvr") if ml_funnel else None, n_hist, clamp=(0.001, 0.25))

        # effective AOV from real conversion value when available
        aov_eff = aov
        if hist_m and hist_m.get("conversions") and hist_m["conversions"] > 0 and hist_m.get("conversion_value", 0) > 0:
            aov_eff = hist_m["conversion_value"] / hist_m["conversions"]
        elif prior.aov_factor != 1.0:
            aov_eff = aov * prior.aov_factor

        # audience fit: centered at 1.0 so NO format is structurally favored —
        # young audiences favor Shorts, older/skewed audiences favor in-stream,
        # in-feed stays near-neutral (deliberate thumbnail intent).
        if key == "shorts":
            audience_fit = 0.75 + 0.55 * young_share        # 0.75 .. 1.30
        elif key == "in_stream":
            audience_fit = 1.20 - 0.30 * young_share        # 0.90 .. 1.20
        else:
            audience_fit = 1.05 - 0.10 * young_share        # 0.95 .. 1.05
        objective_fit = FORMAT_OBJECTIVE_FIT[key].get(objective, 1.0)
        category_fit = profile.format_affinity.get(key, 1.0)
        research_fit, research_note = research_fit_for(key, research_videos)

        risk = prior.risk * (1.0 - min(n_hist / 200_000.0, 0.5) * 0.6)
        if ml_funnel:
            risk *= 0.85

        if hist and n_hist >= MIN_SAMPLE_FOR_TRUST:
            confidence = 0.72 if hist["source"] == "live" else 0.55
        elif ml_funnel:
            confidence = 0.52
        else:
            confidence = 0.35

        evidence = []
        if hist and n_hist > 0:
            src = "live" if hist["source"] == "live" else "synthetic demo"
            evidence.append(
                f"historical {src} campaigns: CTR {hist_m['ctr']:.2f}%, "
                f"{'CPV' if prior.pricing_model == 'cpv' else 'CPC'} {unit_cost:.2f}, CVR {cvr * 100:.2f}%"
            )
        if ml_funnel:
            evidence.append("ML model prediction blended in")
        if research_note:
            evidence.append(research_note)
        if not evidence:
            evidence.append("cold-start priors (documented assumptions)")

        scores.append(opt_engine.FormatScore(
            format_key=key,
            label=label,
            pricing_model=prior.pricing_model,
            unit_cost=round(unit_cost, 4),
            view_rate=round(view_rate, 4),
            click_rate=round(click_rate, 5),
            cvr=round(cvr, 5),
            aov=round(aov_eff, 2),
            objective=objective,
            audience_fit=round(audience_fit, 3),
            objective_fit=round(objective_fit, 3),
            category_fit=round(category_fit, 3),
            research_fit=round(research_fit, 3),
            risk=round(risk, 3),
            sample_size=int(n_hist),
            confidence=confidence,
            data_source_label="LIVE DATA" if (hist and hist["source"] == "live") else "SYNTHETIC DEMO DATA",
            evidence=evidence,
        ))
    return scores


def research_fit_for(format_key: str, videos: list[dict] | None) -> tuple[float, str]:
    """Live-niche multiplier from REAL YouTube research rows (or neutral 1.0).

    Signals used (organic public data, LIVE DATA label):
      * shorts_share  — share of top public videos that are Shorts-length (<=65s)
      * short-form engagement advantage — median engagement of short videos vs long
    Normalized across formats so the mean multiplier stays 1.0 (no hidden push).
    """
    if not videos:
        return 1.0, ""
    usable = [v for v in videos if (v.get("views") or 0) > 0 and v.get("duration_seconds", 0) > 0]
    if len(usable) < 5:
        return 1.0, ""  # too few live rows to justify a signal

    n = len(usable)
    shorts_rows = [v for v in usable if v["duration_seconds"] <= 65]
    long_rows = [v for v in usable if v["duration_seconds"] > 65]
    shorts_share = len(shorts_rows) / n

    def _med_eng(rows: list[dict]) -> float | None:
        vals = sorted((v.get("engagement_rate") or 0.0) for v in rows)
        if not vals or max(vals) <= 0:
            return None
        m = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
        return m

    eng_short = _med_eng(shorts_rows)
    eng_long = _med_eng(long_rows)
    # advantage in [-1, 1]: +1 short-form engagement dominates, -1 long-form dominates
    advantage = 0.0
    if eng_short is not None and eng_long:
        advantage = max(-1.0, min(1.0, (eng_short - eng_long) / max(eng_long, 1e-9)))
    elif eng_short is not None and not long_rows:
        # niche is entirely short-form — moderate positive signal for Shorts
        advantage = 0.5

    raw = {
        "shorts": 0.92 + 0.40 * shorts_share + 0.18 * advantage,
        "in_stream": 1.06 - 0.30 * shorts_share - 0.12 * advantage,
        "in_feed": 1.02 - 0.10 * shorts_share,
    }
    mean = sum(raw.values()) / 3.0
    fit = raw[format_key] / mean

    bits = [f"live niche signal: {shorts_share * 100:.0f}% of {n} top public videos are Shorts-length"]
    if advantage != 0.0:
        direction = "above" if advantage > 0 else "below"
        bits.append(f"short-form engagement {abs(advantage) * 100:.0f}% {direction} long-form")
    note = ", ".join(bits) + " (LIVE DATA)"
    return fit, note


def _ctr_of_views(hist_m: dict) -> float | None:
    """clicks / video views for CPV-priced formats."""
    if not hist_m or not hist_m.get("video_views"):
        return None
    return hist_m["clicks"] / hist_m["video_views"]


def run_optimization(
    db: Session,
    analysis: ProductAnalysis,
    total_budget: float,
    strategy: str = "balanced",
    ml_predictor=None,
) -> BudgetRecommendation:
    if ml_predictor is None:
        # wire the trained-model registry (converted to funnel params) if present
        from app.ml.registry import funnel_from_predictions, load_predictor

        raw_predictor = load_predictor()
        if raw_predictor is not None:
            def ml_predictor(format_key: str, objective: str, category_key: str) -> dict:
                raw = raw_predictor(format_key=format_key, objective=objective, category_key=category_key)
                return funnel_from_predictions(raw)

    history = historical_metrics_by_format(db, analysis)
    cold_start = not history or all(h["sample_size"] < MIN_SAMPLE_FOR_TRUST for h in history.values())
    research_rows = [
        {
            "views": v.views,
            "duration_seconds": v.duration_seconds,
            "engagement_rate": v.engagement_rate,
            "title": v.title,
        }
        for v in db.execute(
            select(ResearchVideo).where(ResearchVideo.analysis_id == analysis.id)
        ).scalars().all()
    ] if analysis.youtube_research_status == "live" else []
    scores = build_format_scores(analysis, history, ml_predictor, research_videos=research_rows)

    result = opt_engine.optimize_budget(
        total_budget=total_budget,
        scores=scores,
        strategy=strategy,
        cold_start=cold_start,
    )

    # honest source label: LIVE only when the evidence itself is live
    live_sources = [h["source"] for h in history.values() if h["sample_size"] > 0]
    source_label = (
        "LIVE DATA" if (live_sources and all(s == "live" for s in live_sources))
        else "SYNTHETIC DEMO DATA" if live_sources
        else "MODEL PREDICTION"
    )

    rec = BudgetRecommendation(
        analysis_id=analysis.id,
        total_budget=total_budget,
        currency=analysis.product.currency,  # type: ignore[union-attr]
        objective=analysis.objective,
        allocations=[
            {
                "format_key": a.format_key,
                "label": a.label,
                "share": a.share,
                "amount": a.amount,
                "predicted": a.predicted,
                "confidence": a.confidence,
                "reason": a.reason,
                "fit_factors": a.fit_factors,
            }
            for a in result.allocations
        ],
        predicted_totals=result.predicted_totals,
        methodology=result.methodology,
        algorithm=result.algorithm,
        optimizer_meta=result.meta,
        cold_start=cold_start,
        confidence=result.confidence,
        data_source_label=source_label,
    )
    db.add(rec)
    db.add(OptimizationRun(
        analysis_id=analysis.id,
        algorithm=result.algorithm,
        iterations=result.meta.get("iterations", 0),
        objective_value=float(result.predicted_totals.get("revenue", 0.0)),
        notes={
            "cold_start": cold_start,
            "strategy": strategy,
            "history_formats": {k: v["sample_size"] for k, v in history.items()},
        },
    ))
    db.commit()
    db.refresh(rec)
    return rec
