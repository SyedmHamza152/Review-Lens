"""Constrained budget optimizer — the core feature.

Method (see README §Methodology for the full write-up):
  1. Per format, build an expected funnel: unit cost -> clicks/views ->
     conversions -> revenue, blended from three evidence sources with
     shrinkage: cold-start priors, historical campaign aggregates, and ML
     model predictions (whichever are available).
  2. Convert to a utility per currency unit: u_i = revenue_rate_i ×
     audience_fit × objective_fit × category_fit × (1 − risk_i), plus a
     UCB-style exploration bonus sqrt(ln N / n_i) so under-explored formats
     still get a fair share.
  3. Solve the allocation with SLSQP (scipy): maximize Σ u_i·x_i −
     λ·Σ risk_i·(x_i/B)²  subject to Σ x_i = B and per-format bounds.
  4. Round to whole currency units with the largest-remainder method so the
     allocation sums to EXACTLY the user's budget (property-tested).
  5. Emit a human-readable, number-citing explanation per allocation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

from app.core.constants import SUPPORTED_FORMATS
from app.optimization.coldstart import PRIOR_PSEUDO_SAMPLE, FormatPrior


@dataclass
class FormatScore:
    """Everything the optimizer knows about one advertising format."""

    format_key: str
    label: str
    pricing_model: str            # cpv | cpc
    unit_cost: float              # currency per view (cpv) or click (cpc)
    view_rate: float              # impressions -> views (cpv)
    click_rate: float             # clicks per view (cpv) or per impression (cpc)
    cvr: float
    aov: float
    audience_fit: float = 1.0     # 0.5 .. 1.5
    objective_fit: float = 1.0
    category_fit: float = 1.0
    risk: float = 0.3
    sample_size: int = 0          # impressions worth of evidence behind metrics
    confidence: float = 0.35      # 0..1 overall confidence in this score
    data_source_label: str = "SYNTHETIC DEMO DATA"
    evidence: list[str] = field(default_factory=list)
    min_share: float = 0.05
    max_share: float = 0.70


@dataclass
class Allocation:
    format_key: str
    label: str
    share: float                  # fraction of budget (sums to 1.0)
    amount: float                 # currency units (sums to total budget)
    predicted: dict               # impressions/clicks/conversions/revenue/...
    confidence: float
    reason: str


@dataclass
class OptimizationResult:
    allocations: list[Allocation]
    predicted_totals: dict
    methodology: str
    algorithm: str
    meta: dict
    cold_start: bool
    confidence: float


def _funnel(budget: float, s: FormatScore) -> dict:
    """Expected performance for spending `budget` on this format."""
    if s.pricing_model == "cpv":
        views = budget / max(s.unit_cost, 1e-9)
        impressions = views / max(s.view_rate, 1e-9) if s.view_rate > 0 else 0.0
        clicks = views * s.click_rate
        video_views = views
    else:
        clicks = budget / max(s.unit_cost, 1e-9)
        impressions = clicks / max(s.click_rate, 1e-9) if s.click_rate > 0 else 0.0
        views = impressions * s.view_rate if s.view_rate > 0 else 0.0
        video_views = clicks  # a thumbnail click opens the watch page = a view
    conversions = clicks * s.cvr
    revenue = conversions * s.aov
    return {
        "impressions": impressions,
        "clicks": clicks,
        "video_views": video_views,
        "conversions": conversions,
        "revenue": revenue,
        "cpa_or_cpv": None,
    }


def _revenue_rate(s: FormatScore) -> float:
    """Expected revenue per currency unit spent."""
    f = _funnel(1.0, s)
    return f["revenue"]


def _utility(s: FormatScore) -> float:
    return (
        _revenue_rate(s)
        * s.audience_fit
        * s.objective_fit
        * s.category_fit
        * (1.0 - 0.5 * s.risk)
    )


def _exploration_bonus(scores: list[FormatScore], bonus_scale: float) -> dict[str, float]:
    """UCB1-style bonus: sqrt(ln N / n_i) rewards under-explored formats."""
    n_eff = []
    for s in scores:
        # pseudo-count for priors so cold start still differentiates by risk
        n_eff.append(max(float(s.sample_size), PRIOR_PSEUDO_SAMPLE * max(s.confidence, 0.1)))
    total = sum(n_eff) or 1.0
    log_n = math.log(total)
    ref = float(np.median([_utility(s) for s in scores]) or 1.0)
    return {
        s.format_key: bonus_scale * ref * math.sqrt(log_n / max(n, 1.0))
        for s, n in zip(scores, n_eff)
    }


def _largest_remainder(budget: float, utilities: dict[str, float], scores: list[FormatScore]) -> dict[str, float]:
    """Integer-currency allocation that sums to EXACTLY `budget`."""
    total_util = sum(utilities.values()) or 1.0
    exact = {k: budget * u / total_util for k, u in utilities.items()}
    base = {k: float(math.floor(v)) for k, v in exact.items()}
    remainder = budget - sum(base.values())
    # distribute leftover units to the largest fractional parts
    order = sorted(scores, key=lambda s: (exact[s.format_key] - base[s.format_key]), reverse=True)
    i = 0
    while remainder > 1e-9 and order:
        s = order[i % len(order)]
        base[s.format_key] += 1.0
        remainder -= 1.0
        i += 1
    return base


def optimize_budget(
    total_budget: float,
    scores: list[FormatScore],
    strategy: str = "balanced",          # balanced | performance | exploratory
    risk_aversion: float = 0.35,
    exploration_bonus_scale: float = 0.35,
    cold_start: bool = False,
) -> OptimizationResult:
    if total_budget <= 0:
        raise ValueError("total_budget must be positive")
    if not scores:
        raise ValueError("at least one format score is required")

    # strategy-dependent bounds
    bounds_cfg = {
        "balanced": (0.05, 0.65),
        "performance": (0.02, 0.80),
        "exploratory": (0.12, 0.55),
    }
    lo_share, hi_share = bounds_cfg.get(strategy, bounds_cfg["balanced"])

    for s in scores:
        s.min_share = max(s.min_share, lo_share)
        s.max_share = min(max(s.max_share, lo_share), hi_share)

    # --- feasibility: shrink the active set if the budget cannot fund minimums
    active = sorted(scores, key=_utility, reverse=True)
    while len(active) > 1 and sum(s.min_share for s in active) * total_budget > total_budget:
        active.pop()  # drop the lowest-utility format
    min_amounts = {s.format_key: s.min_share * total_budget for s in active}
    if sum(min_amounts.values()) > total_budget and active:
        # even the single best format's minimum doesn't fit — give it all
        active = active[:1]
        min_amounts = {active[0].format_key: 0.0}

    utilities = {s.format_key: _utility(s) for s in active}
    bonuses = _exploration_bonus(active, exploration_bonus_scale)
    effective_u = {k: utilities[k] + bonuses[k] for k in utilities}

    # --- SLSQP over the active set -----------------------------------------
    keys = [s.format_key for s in active]
    u_vec = np.array([effective_u[k] for k in keys])
    risk_vec = np.array([next(s.risk for s in active if s.format_key == k) for k in keys])
    B = float(total_budget)
    lower = np.array([min_amounts[k] for k in keys])
    upper = np.array([next(s.max_share for s in active if s.format_key == k) * B for k in keys])

    # if bounds got crossed (tiny budgets), relax to a single-format split
    upper = np.maximum(upper, lower)

    def objective(x: np.ndarray) -> float:
        conc = np.sum(risk_vec * (x / B) ** 2)
        return -float(np.dot(u_vec, x)) + risk_aversion * u_vec.max() * conc

    constraints = [{"type": "eq", "fun": lambda x: float(np.sum(x) - B)}]
    bounds = list(zip(lower, upper))
    x0 = lower + (B - lower.sum()) * (u_vec / (u_vec.sum() or 1.0))
    x0 = np.clip(x0, lower, np.maximum(upper, lower))

    iterations = 0
    try:
        res = minimize(objective, x0, method="SLSQP", bounds=bounds,
                       constraints=constraints, options={"maxiter": 200, "ftol": 1e-9})
        x = res.x if res.success and abs(float(np.sum(res.x)) - B) < 1.0 else x0
        iterations = int(getattr(res, "nit", 0) or 0)
    except Exception:
        x = x0

    # clip negative/NaN defensively, then renormalise
    x = np.nan_to_num(np.asarray(x, dtype=float), nan=0.0)
    x = np.clip(x, 0, None)
    if x.sum() <= 0:
        x = x0
    raw_amounts = {k: float(v) for k, v in zip(keys, x)}

    # --- exact rounding ------------------------------------------------------
    amounts = _largest_remainder(B, raw_amounts, active)
    # enforce per-format minimums after rounding (then re-fix the sum)
    for k in keys:
        amounts[k] = max(amounts[k], min_amounts[k])
    drift = B - sum(amounts.values())
    if abs(drift) > 1e-6:
        biggest = max(amounts, key=lambda k: amounts[k])
        amounts[biggest] += drift

    total_amount = sum(amounts.values())
    assert abs(total_amount - B) < 0.01, "allocation must equal budget"

    # --- build result --------------------------------------------------------
    allocations: list[Allocation] = []
    totals = {"impressions": 0.0, "clicks": 0.0, "video_views": 0.0,
              "conversions": 0.0, "revenue": 0.0, "cost": 0.0}
    for s in sorted(active, key=lambda s: amounts[s.format_key], reverse=True):
        amt = amounts[s.format_key]
        if amt <= 0:
            continue
        f = _funnel(amt, s)
        share = amt / B
        cpa = (amt / f["conversions"]) if f["conversions"] > 0 else None
        roas = (f["revenue"] / amt) if amt > 0 else None
        predicted = {
            "impressions": round(f["impressions"]),
            "clicks": round(f["clicks"]),
            "video_views": round(f["video_views"]),
            "conversions": round(f["conversions"], 1),
            "revenue": round(f["revenue"], 2),
            "cpa": round(cpa, 2) if cpa else None,
            "roas": round(roas, 2) if roas else None,
        }
        reason = _explain(s, share, amt, effective_u[s.format_key], bonuses.get(s.format_key, 0.0), B)
        allocations.append(Allocation(
            format_key=s.format_key,
            label=s.label,
            share=round(share, 4),
            amount=round(amt, 2),
            predicted=predicted,
            confidence=round(s.confidence, 2),
            reason=reason,
        ))
        for kk in ("impressions", "clicks", "video_views", "conversions", "revenue"):
            totals[kk] += f[kk]
        totals["cost"] += amt

    predicted_totals = {k: round(v, 2) for k, v in totals.items()}
    predicted_totals["cpa"] = round(totals["cost"] / totals["conversions"], 2) if totals["conversions"] > 0 else None
    predicted_totals["roas"] = round(totals["revenue"] / totals["cost"], 2) if totals["cost"] > 0 else None
    predicted_totals["ctr"] = round(100 * totals["clicks"] / totals["impressions"], 2) if totals["impressions"] > 0 else None
    predicted_totals["conversion_rate"] = round(100 * totals["conversions"] / totals["clicks"], 2) if totals["clicks"] > 0 else None

    confidences = [s.confidence for s in active if amounts[s.format_key] > 0]
    overall_conf = float(np.average(confidences, weights=[amounts[s.format_key] for s in active if amounts[s.format_key] > 0])) if confidences else 0.3

    inactive = [s for s in scores if s.format_key not in keys]
    methodology = _methodology_text(strategy, cold_start, active, inactive, risk_aversion, exploration_bonus_scale)

    return OptimizationResult(
        allocations=allocations,
        predicted_totals=predicted_totals,
        methodology=methodology,
        algorithm=f"SLSQP constrained optimization + UCB exploration ({strategy})",
        meta={
            "iterations": iterations,
            "strategy": strategy,
            "cold_start": cold_start,
            "active_formats": keys,
            "effective_utilities": {k: round(v, 4) for k, v in effective_u.items()},
            "exploration_bonuses": {k: round(v, 4) for k, v in bonuses.items()},
            "risk_aversion": risk_aversion,
        },
        cold_start=cold_start,
        confidence=round(overall_conf, 2),
    )


def _explain(s: FormatScore, share: float, amount: float, utility: float, bonus: float, budget: float) -> str:
    bits = [f"{share * 100:.0f}% share driven by"]
    rate = _revenue_rate(s)
    bits.append(
        f"expected {rate:.2f} revenue per currency unit "
        f"({'CPV' if s.pricing_model == 'cpv' else 'CPC'} {s.unit_cost:g}, CVR {s.cvr * 100:.1f}%)"
    )
    if s.evidence:
        bits.append(s.evidence[0])
    if s.sample_size > 500:
        bits.append(f"historical evidence n={s.sample_size:,} impressions")
    else:
        bits.append("limited history — priors + exploration bonus applied")
    if s.audience_fit != 1.0:
        bits.append(f"audience fit ×{s.audience_fit:.2f}")
    if s.objective_fit != 1.0:
        bits.append(f"objective fit ×{s.objective_fit:.2f}")
    if bonus > 0.01:
        bits.append(f"exploration bonus +{bonus:.2f}")
    return "; ".join(bits) + "."


def _methodology_text(strategy, cold_start, active, inactive, risk_aversion, exploration) -> str:
    lines = [
        f"Strategy: {strategy}. Objective: maximize expected revenue subject to the exact budget, "
        f"per-format share bounds and a risk-adjusted concentration penalty (λ={risk_aversion}).",
        "Utilities combine: evidence-based funnel rates (historical aggregates blended with "
        "ML predictions where available, else cold-start priors), audience/objective/category fit "
        "multipliers, (1 − risk/2), and a UCB-style exploration bonus sqrt(ln N / n_i) "
        f"(scale={exploration}) so formats with little data still receive a fair trial budget.",
    ]
    if cold_start:
        lines.append(
            "COLD START: insufficient campaign history was available, so allocation is anchored on "
            "documented priors (see README §Cold-start assumptions). Treat predicted numbers as "
            "planning estimates, not forecasts."
        )
    if inactive:
        lines.append(
            "De-activated formats: " + ", ".join(s.label for s in inactive)
            + " (budget too small to fund their minimum viable allocation, or dominated utility)."
        )
    return " ".join(lines)


def score_from_prior(prior: FormatPrior, label: str | None = None) -> FormatScore:
    return FormatScore(
        format_key=prior.format_key,
        label=label or SUPPORTED_FORMATS.get(prior.format_key, prior.format_key),
        pricing_model=prior.pricing_model,
        unit_cost=prior.unit_cost,
        view_rate=prior.view_rate,
        click_rate=prior.click_rate,
        cvr=prior.cvr,
        aov=1.0,  # replaced by caller with category AOV
        risk=prior.risk,
        confidence=0.35,
        data_source_label="SYNTHETIC DEMO DATA",
        min_share=0.05,
        max_share=0.70,
    )
