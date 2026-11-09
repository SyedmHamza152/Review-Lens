# AdPilot AI — Methodology

This document explains how AdPilot produces its numbers, what every number means,
and where the documented assumptions live.

## 1. Budget optimization

### Evidence blending
For each format (in_stream, shorts, in_feed) the optimizer needs four funnel
parameters: unit cost (CPV or CPC), click-through rate, conversion rate (CVR) and
average order value (AOV). Three evidence sources are blended with shrinkage:

```
effective_param = (n_hist × param_history + k_priors × param_prior) / (n_hist + k_priors)
```

- `param_history` — aggregated metrics from stored campaign rows (live or demo).
- `param_prior` — cold-start priors in `app/optimization/coldstart.py`
  (documented PKR assumptions).
- Weights: priors carry `k = 200,000` impressions-equivalent; history carries its
  real impression count; ML predictions (when a registry exists) carry 120,000.

### Utility and exploration
Utility per currency unit:

```
u_i = revenue_rate_i × audience_fit × objective_fit × category_fit × (1 − risk_i/2)
      + exploration_bonus_i
```

- `revenue_rate_i` = expected revenue per unit spend through the format funnel
  (CPV formats: views = budget/CPV, clicks = views × click_rate; CPC formats:
  clicks = budget/CPC, impressions = clicks/CTR).
- `exploration_bonus_i = c × median(u) × sqrt(ln N / n_i)` (UCB1-style), so
  formats with thin evidence keep a fair trial budget. `n_i` never falls below a
  pseudo-count attributed to the priors themselves.
- Fits: audience fit from the inferred age profile (young audiences favor Shorts),
  objective fit from `FORMAT_OBJECTIVE_FIT`, category fit from the category profile.

### Constrained solve
SciPy **SLSQP** maximizes `Σ u_i·x_i − λ·Σ risk_i·(x_i/B)²` subject to
`Σ x_i = B` and per-format share bounds (strategy-dependent: balanced 5–65%,
performance 2–80%, exploratory 12–55%). Risk aversion λ = 0.35.

### Exact-sum rounding
Raw allocations are rounded to whole currency units with the **largest-remainder**
method and per-format minimums re-applied; the residual is applied to the largest
allocation. Property tests assert `Σ amounts == budget` for budgets from 900 to
999,999 including decimals, with no negative amounts.

### Deactivation
If the budget cannot fund every format's minimum viable allocation, the
lowest-utility formats are deactivated (stated in the methodology text).

## 2. Machine learning

- Grain: campaign × day rows from the synthetic corpus (40 campaigns × 180 days ≈
  7,200 rows at 100k generator scale).
- Features: `ad_format`, `marketing_objective`, `category` (one-hot) +
  `budget_share`, `audience_age_index`, `device_mobile_share`, `month`,
  `day_of_week` (numeric).
- Split: chronological 80/20 (train on earlier dates) — no temporal leakage.
- Candidates per target: LinearRegression, RandomForest, GradientBoosting, XGBoost;
  the best per target is selected by R²; **all** candidates' MAE/RMSE/R² are stored
  and shown in the ML Lab.
- Honest scope: models are trained on the synthetic corpus unless retrained on
  authorized live data; the registry records `trained_on` and the UI shows it.
- Predictions feed the optimizer as a third evidence source (clamped), never as
  the sole input.

## 3. Big Data pipelines

All three engines implement the same contract on the same CSV:
ingest → clean (dropna, dedup, clip negatives, impressions>0) → transform
(row-level CTR/CPC/CVR/ROAS) → aggregate (by format/campaign/city/age/device/month)
→ budget-recommendation view (efficiency-ranked shares).

- **Pandas** — explicit category dtypes; the equivalence baseline.
- **MapReduce** — two genuine MapReduce jobs: (1) row-hash deduplication
  (blake2b-64, owner-chunk "keep first" semantics matching pandas
  `drop_duplicates`), (2) aggregation with per-chunk combiners and key reducers,
  using multiprocessing pools over byte-aligned input chunks. Single-machine by
  design — **not** a distributed Hadoop cluster (no HDFS/YARN).
- **PySpark** — Spark local[*], same cleaning + aggregation via DataFrame API.

**Equivalence gate:** after each benchmark, impressions/clicks/spend/revenue totals
of MapReduce and Spark must match the Pandas baseline (±1.0 currency unit). The
check runs automatically and is displayed per engine.

## 4. Cold-start assumptions (where they live)

| Assumption | Location |
|---|---|
| Format economics (CPV/CPC, view/click rates, CVR, risk) | `backend/app/optimization/coldstart.py` |
| Category AOV bands | `coldstart.AOV_BY_BAND` |
| Category profiles, audiences, objective rules | `backend/app/services/knowledge.py` |
| Objective decision matrix | `knowledge.OBJECTIVE_DECISION_RULES` |
| Format × objective fit | `knowledge.FORMAT_OBJECTIVE_FIT` |

All of these are heuristic priors for the default Pakistan/PKR market. They are
blended with real evidence when available and always surfaced in the UI
methodology text.

## 5. Metric definitions (spec §8)

CTR = clicks/impressions ×100 · CPC = cost/clicks · CPA = cost/conversions ·
Conversion rate = conversions/clicks ×100 · ROAS = conversion value/cost ·
CPV = cost/video views · View rate = video views/eligible impressions ×100.
Google Ads cost arrives in micros and is converted at the ingestion boundary;
zero denominators yield `None` (never ∞ or fake zeros).
