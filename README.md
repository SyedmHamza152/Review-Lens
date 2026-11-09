# AdPilot AI — AI-Powered Google & YouTube Advertising Budget Optimizer

Enter a **product name** and a **budget**. AdPilot AI infers the product category and
audience, researches the live YouTube market, predicts performance with machine
learning, and distributes your **exact** budget across the three YouTube advertising
formats — with a written, evidence-citing reason for every allocation.

> **Scope (by design):** only YouTube advertising inventory is supported —
> **In-Stream**, **Shorts** and **In-Feed Video** ads via the Google Ads API, plus
> public content research via the YouTube Data API v3. Search, Display, and every
> non-Google platform are intentionally absent from the code, the UI and the data.
> Default market: **Pakistan (PKR)**, configurable.

This is the second project in the series — the first is
[Review Lens](https://github.com/SyedmHamza152/Review-Lens) — and follows the same
engineering conventions (FastAPI + Next.js 16 monorepo, honest data labeling,
single-page dashboard shell).

---

## 1. Architecture

```
Browser ──> Caddy gateway (:81, preview URL)
              ├─ /                     -> Next.js 16 server (:3000)   [single-page app]
              ├─ /api/py-health        -> Next.js route — spawns/watches the backend
              └─ /api/*?XTransformPort=8321 -> Python FastAPI (:8321)

FastAPI (backend/app)
  ├─ api/          REST API (/api/v1/...) + OpenAPI docs at /api/docs
  ├─ services/     7-step analysis pipeline, optimizer service, metrics, demo seeder
  ├─ optimization/ SLSQP constrained optimizer + UCB exploration + cold-start priors
  ├─ ml/           feature engineering, model training (LR/RF/GBM/XGB), registry
  ├─ bigdata/      synthetic generator (10k–10M), Pandas / MapReduce / PySpark, benchmarks
  ├─ integrations/ YouTube Data API v3, Google Ads GAQL, Google OAuth2, Ollama LLM
  └─ reports/      PDF (ReportLab), Excel (OpenPyXL), CSV exporters
```

- **Frontend** (`src/`) is a single page (`src/app/page.tsx`) with a hash-based state
  machine: landing → analyze → progress → dashboard (sidebar views: Allocation,
  Campaign Analytics, Audience, Competitors, Big Data Lab, ML Lab, Reports, Settings).
- **Backend** is spawned automatically: `src/app/api/py-health/route.ts`
  (health-check → spawn → wait, idempotent) and `mini-services/adpilot-backend` at
  sandbox boot. Standalone: `cd backend && python -m uvicorn app.main:app --port 8321`.
- **Database**: SQLite (zero-config, `backend/data/adpilot.db`). For PostgreSQL set
  `SQLALCHEMY_DATABASE_URL=postgresql+psycopg://adpilot:adpilot@localhost:5432/adpilot`
  and run `alembic upgrade head` (initial migration included in `backend/alembic/versions`).
- **Background jobs** run in an in-process thread pool (`TASK_QUEUE=inline`). For
  production set `TASK_QUEUE=celery` (Celery + Redis ship in `docker-compose.yml`).

### The 7-step analysis pipeline

1. **Understanding product** — rule engine (keyword classifier over 15 category
   profiles) optionally enriched by a local Ollama LLM; falls back cleanly to rules.
2. **Identifying target audience** — age-band weights, gender skew, interests,
   priority cities, named segments. Output is labeled *inference/hypothesis*, never
   verified demographics.
3. **Marketing objective** — decision matrix over purchase intent × price band ×
   budget size → Awareness / Video Views / Traffic / Leads / Sales, with rationale.
4. **Researching YouTube market** — *live* YouTube Data API v3 search (up to 30 public
   videos per run — one flat 100-quota-unit search call) + video stats +
   channel stats (quota-tracked, cached, backoff). Clearly organic metrics only.
5. **Fetching advertising history** — *live* Google Ads GAQL sync (VIDEO channel
   only) when connected; otherwise the labeled **synthetic demo history** (12
   campaigns × 180 days) is used and never mixed with live data. The synthetic
   rows are **product-aware**: engagement rates are modulated by the product
   category's documented format affinities (±20%, `optimizer_service._modulate_synthetic`),
   so a fashion product's simulated Shorts history genuinely differs from an
   electronics one — while every row keeps its `ESTIMATED DATA` label in the UI.
6. **Analyzing campaign performance** — metrics engine (CTR/CPC/CPA/CVR/ROAS/CPV/
   view-rate, zero-safe) + ML predictions from the trained registry.
7. **Running optimization** — SLSQP constrained allocation + UCB exploration bonus +
   largest-remainder rounding so allocations sum to *exactly* the budget.

### How the optimizer avoids a default winner (no structural in-stream bias)

The utility per format is **objective-aligned** (engine `_value_rate`):

| Objective | Utility unit | Typical winner |
|---|---|---|
| Video Views / Brand Awareness | video views per PKR | **Shorts** (cheapest engaged views) |
| Website Traffic | clicks per PKR | **In-Feed** (deliberate thumbnail clicks) |
| Leads / Sales | revenue per PKR | In-Feed / In-Stream by category demo-need |

On top of the evidence-based funnel rates, four *centered* fit multipliers
(mean ≈ 1.0, no hidden push) shape the allocation:

- **audience fit** — young audiences push Shorts up / In-Stream down; older audiences the reverse;
- **objective fit** — a *different* format leads for each objective (`knowledge.FORMAT_OBJECTIVE_FIT`);
- **category fit** — per-category affinities (fashion/food → Shorts; education/software → In-Feed; sports/home/automotive → In-Stream);
- **research fit** — *LIVE* signal from the product's real YouTube niche: Shorts-share of top public videos and short-vs-long engagement advantage (`optimizer_service.research_fit_for`).

A regression test (`test_no_structural_in_stream_bias`) fails the suite if any
format ever wins everywhere. Per-format share bounds (balanced: 8–55%) keep
every plan diversified.

### Ad duration intelligence — "how many seconds should my ad be?"

`app/services/duration_engine.py` + `GET /api/v1/analyses/{id}/durations`
recommend the best creative length **per format and objective** (6s bumper,
15s/20s/30s/60s+ in-stream, ≤15s/16–30s/31–60s Shorts, 15–30s/31–60s/61–90s
in-feed). Scoring layers:

1. documented creative priors per objective (Google creative guidance);
2. context adjustments — audience age mix, category demo-need, budget band;
3. **LIVE evidence** — real public videos of this product bucketed by length;
   buckets with above-average engagement nudge overlapping durations
   (`engagement_index`, labeled `LIVE DATA`).

The UI shows per-format best/alternative durations, expected hold-rate bars,
predicted audience-retention curves (`MODEL PREDICTION` shapes), and the real
bucket statistics + a duration-vs-engagement scatter of the live research rows.

---

## 2. Data honesty (labels you will see everywhere)

| Label | Meaning |
|---|---|
| `LIVE DATA` | Fetched from a real API (YouTube Data API, Google Ads) during this session |
| `ESTIMATED DATA` (shown in UI; stored as `SYNTHETIC DEMO DATA`) | Generated by `app/bigdata/generator.py` or the demo seeder — realistic but explicitly synthetic. The frontend displays it as **ESTIMATED DATA** |
| `MODEL PREDICTION` | Output of the ML models / optimization funnel — planning estimates, not measurements |
| `INFERENCE` / `USER INPUT` | Rule-engine hypotheses / what the user typed |

Hard rules enforced in code and UI:
- Live data is **never** silently substituted by synthetic data (status fields
  `youtube_research_status` / `ads_history_status` are stored per analysis).
- Public YouTube statistics describe **organic engagement** — never ad spend,
  conversions or competitor ROAS.
- Benchmarks are **measured at run time** and cross-checked for cross-engine
  equivalence (totals must match the Pandas baseline exactly; the MapReduce pipeline
  implements a genuine dedup MapReduce job to make that possible).
- ML models trained on synthetic data are labeled `trained on synthetic`.

---

## 3. Technology stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router, single-page shell), TypeScript, Tailwind CSS 4, shadcn/ui, Recharts, TanStack Query, Lucide |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| ML | scikit-learn (LinearRegression, RandomForest, GradientBoosting), XGBoost, joblib |
| Optimization | SciPy (SLSQP), UCB1-style exploration, largest-remainder rounding |
| Big Data | Pandas, pure-Python MapReduce (multiprocessing, 2-stage), PySpark 4 local[*] |
| Integrations | google-api-python-client (YouTube v3), google-ads (GAQL), google-auth OAuth2, Ollama (optional) |
| Reports | ReportLab (PDF), OpenPyXL (Excel), CSV |
| Database | SQLite dev default · PostgreSQL via docker-compose |

---

## 4. Installation (Windows PowerShell)

```powershell
# 1. Clone and enter the project
git clone <your-repo-url> adpilot-ai
cd adpilot-ai

# 2. Backend virtual environment (Python 3.10+; 3.12 recommended)
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Environment — copy the template and fill in your keys
Copy-Item ..\.env.example .env
notepad .env        # add YOUTUBE_API_KEY, GOOGLE_CLIENT_ID/SECRET, etc.

# 4. Start the backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8321
#    → docs: http://127.0.0.1:8321/api/docs

# 5. Frontend (new PowerShell window, project root)
cd ..
npm install
npm run dev          # http://localhost:3000
```

On first boot the backend creates the SQLite database, applies demo seeds
(`ESTIMATED DATA` in the UI) and is fully usable **without any API credentials**.

### Linux / macOS

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8321 &
cd .. && npm install && npm run dev
```

### Docker (PostgreSQL + Redis + backend + frontend)

```powershell
Copy-Item .env.example .env      # fill in credentials first
docker compose up -d postgres redis
docker compose up -d backend     # frontend: docker compose up frontend (or npm run dev)
```

---

## 5. Environment configuration (`backend/.env`)

See `.env.example` for the full annotated list:

| Variable | Purpose |
|---|---|
| `YOUTUBE_API_KEY` | YouTube Data API v3 (public research) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth 2.0 client |
| `GOOGLE_REFRESH_TOKEN` | Optional: paste a refresh token instead of completing OAuth |
| `GOOGLE_ADS_CUSTOMER_ID` / `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Google Ads account for reporting |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads API developer token (Basic access) |
| `OAUTH_REDIRECT_URI` | Defaults to `http://localhost:8321/api/v1/oauth/google/callback` |
| `SQLALCHEMY_DATABASE_URL` | SQLite default; PostgreSQL DSN for production |
| `SECRET_KEY` | Derives the Fernet key that encrypts OAuth tokens at rest |
| `DEFAULT_CURRENCY` / `DEFAULT_MARKET` | `PKR` / `PK` |
| `TASK_QUEUE` | `inline` (default) or `celery` |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Optional local LLM (llama3.1); unreachable ⇒ rule engine |

**Never commit `.env`.** It is gitignored; `.env.example` contains placeholders only.

---

## 6. Google Cloud / API setup

### YouTube Data API v3 (needed for live competitor research)
1. [Google Cloud Console](https://console.cloud.google.com) → create/select a project.
2. **APIs & Services → Library →** enable **YouTube Data API v3**.
3. **Credentials → Create credentials → API key.** Put it in `backend/.env` as `YOUTUBE_API_KEY`.
4. Default quota is 10,000 units/day (search = 100 units/call). AdPilot tracks usage
   per process and surfaces it in Settings.

### Google OAuth 2.0 (needed for Google Ads reporting)
1. **APIs & Services → Library →** enable **Google Ads API**.
2. **OAuth consent screen** → External → add yourself as test user (Testing mode).
3. **Credentials → Create credentials → OAuth client ID → Web application.**
4. Add redirect URI: `http://localhost:8321/api/v1/oauth/google/callback`
   (or your preview URL + the same path; set it as `OAUTH_REDIRECT_URI`).
5. Put client id/secret in `backend/.env`.
6. In the app: **Settings → Connect Google account** → consent → token exchange
   happens server-side; the refresh token is stored **encrypted** (Fernet).
   Alternatively paste a refresh token into `GOOGLE_REFRESH_TOKEN`.

### Google Ads API access (current requirements, verified 2026)
- A **developer token** is still required by Google for any Google Ads API access —
  request **Basic access** at https://ads.google.com/aw/apicenter (Basic is enough
  for reporting; it no longer requires the old managerial pre-approval flow, but it
  must be *approved*).
- The authenticated user (or a manager account above it, set
  `GOOGLE_ADS_LOGIN_CUSTOMER_ID`) must have access to `GOOGLE_ADS_CUSTOMER_ID`.
- Reporting queries filter `campaign.advertising_channel_type = 'VIDEO'` only —
  Search/Display/Performance Max rows are excluded by the GAQL itself.
- Until every requirement is present, Settings shows the exact missing items and the
  app keeps using labeled demo data. **`POST /api/v1/oauth/google/test-connection`**
  performs a real minimal query and reports honest success/failure.

### Optional: Ollama LLM
```powershell
ollama pull llama3.1
ollama serve     # AdPilot detects it automatically; otherwise the rule engine is used
```

---

## 7. Running the Big Data benchmarks

In the app: **Big Data Lab** → choose size (10k / 100k / 1M / 10M) and engines →
*Generate & benchmark*. Charts + a markdown report land in `backend/data/benchmarks/`.

From the CLI:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python ..\scripts\run_benchmarks.py --rows 10000 100000 1000000 --engines pandas mapreduce spark
```

Notes:
- **PySpark needs Java 17+** (`java -version`). The sandbox has Java 21; the Docker
  image installs Java 17.
- The **Python MapReduce** pipeline is a genuine two-job MapReduce implementation
  (hash-dedup job + aggregation job, multiprocessing mappers with combiners, key
  reducers) — but it is a *single-machine* implementation, **not** a Hadoop cluster.
  This distinction is stated in code, UI and reports.
- Results (seconds, peak RSS of the process tree, cross-engine equivalence) are
  **measured** and persisted; nothing is pre-filled. Engines that fail (e.g. Spark
  without Java) are recorded with their error.

---

## 8. Training the ML models

```powershell
# one-time: generate the 100k training corpus (Big Data Lab or CLI)
python ..\scripts\generate_dataset.py --rows 100000

# train all candidates on 8 targets and save artifacts to models/
python ..\scripts\train_models.py
```

- Targets: `ctr, cpc, cvr, cpa, roas, conversions, revenue, video_views`.
- Candidates per target: LinearRegression, RandomForest, GradientBoosting, XGBoost —
  compared with MAE / RMSE / R² on a chronological 80/20 split (no temporal leakage).
- Artifacts: `models/<target>_best.joblib` + `models/metrics.json`; mirrored into the
  `model_registry` table. Retrain any time new campaign data lands
  (`POST /api/v1/ml/train` or the ML Lab button).
- A missing registry never blocks the optimizer — documented cold-start priors are
  used instead and the analysis is labeled accordingly.

---

## 9. Testing

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest tests\ -q
```

55 tests cover: metric formulas incl. zero-denominators and micros conversion;
optimizer properties (allocations sum **exactly** to budget for 5000 → 999,999
incl. decimals; bounds; no negatives; tiny-budget single-format fallback; cold-start
methodology); generator schema/whitelist/determinism; Pandas↔MapReduce equivalence;
ML train/predict plumbing; report exports (PDF/XLSX/CSV byte sanity); OAuth URL/state
security and token encryption; and API integration tests (product → job →
recommendation sum; big-data generate + benchmark; settings validation; OpenAPI).

---

## 10. API summary (OpenAPI at `/api/docs`)

| Endpoint | Description |
|---|---|
| `GET /api/v1/health` | Service, DB, YouTube/Google/OAuth/LLM status |
| `GET /api/v1/auth/me` · `GET/PUT /api/v1/settings` | Demo user, currency/market |
| `POST /api/v1/products` | Create product `{name, total_budget, description?}` |
| `POST /api/v1/analyses` · `GET /api/v1/analyses/jobs/{id}` | Start 7-step pipeline · poll real progress |
| `GET /api/v1/analyses/{id}` · `/recommendation` | Full analysis · allocation + reasons |
| `POST /api/v1/analyses/{id}/recommendation/reoptimize` | Re-run with balanced/performance/exploratory |
| `GET /api/v1/dashboard` · `/campaigns/analytics` · `/audience/{id}` · `/competitors/{id}` | Aggregates for the views |
| `GET /api/v1/oauth/google/start` → `/callback` · `/status` · `/test-connection` | OAuth flow + honest status |
| `GET /api/v1/google-ads/status` · `POST /sync` · `/campaigns` | Google Ads reporting |
| `GET /api/v1/youtube/research?product=` | Live public research (organic metrics) |
| `GET /api/v1/ml/models` · `POST /ml/predict` · `POST /ml/train` | ML lab |
| `POST /api/v1/bigdata/generate` · `POST /bigdata/benchmark` · `GET /benchmarks` | Big Data lab |
| `POST /api/v1/reports` · `GET /reports/{id}/download` | PDF / XLSX / CSV exports |
| `POST /api/v1/demo/seed` | Re-seed labeled synthetic demo campaigns |

Structured errors: `{"error": {"code", "message", "details"}}`; pagination:
`{items, total, page, size}`.

---

## 11. Project structure

```
adpilot-ai/
├─ src/                      # Next.js 16 frontend (single-page app shell)
│  ├─ app/page.tsx           # hash-based view router (landing + 9 app views)
│  ├─ app/api/py-health/     # idempotent backend spawner
│  ├─ components/adpilot/    # landing, analyze, progress, dashboard, allocation,
│  │                         # campaigns, audience, competitors, bigdata, ml,
│  │                         # reports, settings + shared bits/shell
│  └─ lib/pyapi.ts           # typed API client (XTransformPort gateway aware)
├─ backend/
│  ├─ app/{api,services,models,schemas,ml,optimization,integrations,bigdata,reports,core}
│  ├─ alembic/               # migrations (initial schema included)
│  ├─ tests/                 # 55 pytest cases
│  ├─ requirements.txt · Dockerfile
├─ models/                   # trained ML artifacts (metrics.json + *.joblib)
├─ scripts/                  # train_models.py · run_benchmarks.py · generate_dataset.py
├─ docs/                     # methodology notes
├─ mini-services/adpilot-backend/  # sandbox auto-start entry for the backend
├─ data/                     # runtime datasets & benchmark reports (gitignored)
├─ .env.example · docker-compose.yml · README.md
```

*The frontend lives at the repository root (monorepo style) because the target
platform runs `next dev` from the root; separation of concerns is preserved
(`src/` = frontend, `backend/` = API).*

---

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `Backend online` never turns green | Check `backend/uvicorn.log`; run uvicorn manually to see the error |
| Competitor view empty / "research skipped" | `YOUTUBE_API_KEY` missing or quota exhausted — Settings shows quota used |
| Google Ads shows "Missing: ..." | Fill the exact env vars listed in Settings; developer token must be *approved* |
| Spark engine error in benchmark | Install Java 17+ (`java -version`), or rerun without the spark engine |
| `python: can't open file` on Windows | You are not inside `backend/` — run commands from there |
| OAuth `redirect_uri_mismatch` | The redirect URI registered in Google Cloud must equal `OAUTH_REDIRECT_URI` byte-for-byte |
| Port 8321 busy | Change `BACKEND_PORT` in `backend/.env` and `BACKEND_PORT` in `src/lib/pyapi.ts` |

---

## 13. Known limitations (stated, not hidden)

- Single-user demo mode: one provisioned user; Google OAuth identity flow exists for
  account connection, not for multi-tenant login.
- The Google Ads client is fully implemented (GAQL, subtype→format mapping, sync,
  test-connection) but **could not be verified against a live account** in the
  development sandbox — it requires an approved developer token and account access
  (see §6). It reports honest errors until then.
- ML models ship trained on the **synthetic** corpus; retrain on real authorized
  campaign data via `POST /api/v1/ml/train` before trusting the numbers.
- Benchmarks ran on a 2-core/4 GB sandbox: 10k/100k/1M measured for all three
  engines; run 10M locally with the CLI command in §7 if your machine has RAM headroom.
