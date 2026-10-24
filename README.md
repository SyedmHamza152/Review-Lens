# ReviewLens — AI-Powered Product Review Intelligence Platform

Cross-platform product review intelligence: search a product, collect available reviews
and public discussions from e-commerce marketplaces and social platforms, analyze
sentiment in **English, Urdu script, Roman Urdu and mixed-language comments**, compare
feedback across platforms, and get an evidence-based verdict with full traceability.

Stack: **Next.js 16 + TypeScript + Tailwind + shadcn/ui + Recharts** (frontend) ·
**Python FastAPI + SQLAlchemy + scikit-learn + ReportLab** (backend).

---

## 1. Architecture

```
Browser ──> Caddy gateway (:81, preview URL)
              ├─ /                     -> Next.js server (:3000)   [single-page app]
              ├─ /api/py-health        -> Next.js route (Node runtime) — spawns/watches backend
              ├─ /api/chat             -> Next.js route (z-ai-web-dev-sdk LLM assistant)
              └─ /api/*?XTransformPort=8317 -> Python FastAPI (:8317)
```

- The **frontend is a single page** (`src/app/page.tsx`) with a state machine:
  home → search progress → dashboard (Overview / Platform comparison / Review
  explorer / AI assistant / Methodology). Reports survive refresh via URL hash
  (`#/job/<id>`).
- The **Python backend** (`backend/app`) is spawned as a managed child of the
  Next.js server process by `/api/py-health` (health-check → spawn → wait,
  idempotent). Logs: `backend/uvicorn.log`.
- **Jobs** run in background threads (in-process `TASK_QUEUE=inline`). For
  production set `TASK_QUEUE=celery` (Celery + Redis) — the dispatch point is
  `backend/app/services/orchestrator.py::start_job_background`.

### Backend modules

| Module | Responsibility |
|---|---|
| `app/api/routes.py` | REST API under `/api` |
| `app/services/orchestrator.py` | job lifecycle, parallel adapter collection (adapter failures are isolated) |
| `app/services/pipeline.py` | language → relevance → spam → dedup → sentiment → aspects → persist |
| `app/services/aggregation.py` | verdict scoring, platform comparison, aspects, languages, trends |
| `app/services/exporter.py` | CSV + PDF report |
| `app/nlp/` | language detection, Roman-Urdu normalization, sentiment engine, ABSA, gloss translation |
| `app/integrations/` | 12 platform adapters + sample corpus |

### Database (SQLAlchemy 2.0)

Tables: `search_jobs`, `job_platform_status`, `product_matches`, `reviews`,
`report_cache`. Original text, normalized analysis text and translation are
stored separately; `(job_id, platform, external_id)` + normalized-text hash
prevent double counting. Sandbox uses SQLite; set
`SQLALCHEMY_DATABASE_URL=postgresql+psycopg://...` for PostgreSQL and run
`alembic upgrade head` (initial migration included in `backend/alembic/versions`).

---

## 2. NLP pipeline (multilingual)

1. **Language detection** — Urdu-script ratio + marker tokens; product nouns
   (camera, battery, …) are treated as loanwords so Roman Urdu comments with
   English nouns classify correctly. Confidence + `uncertain` flag.
2. **Normalization** (analysis copy only; originals untouched) — spelling
   variants folded (`bohat/bahut/bohot → bohat`, `nahi/nai/nhe → nahi`, …),
   repeated-letter collapse, English slang mapping (`gud→good`, `gr8→great`).
3. **Sentiment** — merged EN + Roman Urdu + Urdu-script lexicons, phrase
   matching (bigram/trigram), negation window (±3 tokens, handles
   `"achi nahi"`, `"not good"`, `"kharab nahi"`), intensifiers/diminishers,
   adversative clause splitting (`but / lekin / magar / لیکن`) → **Mixed**
   detection; sarcasm heuristics; confidence + uncertainty flags.
4. **ABSA** — 11 aspects (quality, price/value, durability, performance, design,
   battery, delivery, packaging, customer support, seller reliability,
   authenticity) with product-vs-seller/marketplace complaint separation.
5. **Translation** — optional approximate English gloss (only when token
   coverage is sufficient); originals always preserved.

### Evaluation (honest numbers)

`backend/tests/evaluate_sentiment.py` evaluates on 120 hand-labeled realistic
Pakistani e-commerce/social comments (`backend/tests/data/eval_dataset.tsv`):

| Language class | Accuracy | Macro F1 |
|---|---|---|
| English | 0.87 | 0.83 |
| Roman Urdu | 1.00 | 1.00 |
| Urdu script | 1.00 | 1.00 |
| Mixed-language | 0.88 | 0.87 |
| Language detection | 0.76 | — |

Run it: `cd backend && python3 -m tests.evaluate_sentiment`
These are rule-engine numbers on a small curated set — re-evaluate on larger,
independent datasets before claiming production accuracy. A transformer
second-opinion engine (XLM-R) can be enabled via `TRANSFORMER_SENTIMENT_ENABLED=1`
when model downloads are available.

---

## 3. Data access reality (no fabricated data)

| Platform | Access mode | Status without credentials |
|---|---|---|
| Daraz | Open Platform API (partner approval) | `needs_credentials` (env vars listed) |
| Amazon | PA-API 5 (ratings/review counts; review text restricted by policy) | `needs_credentials` |
| Alibaba / AliExpress | Open Platform APIs | `needs_credentials` |
| Temu / SHEIN | **No public API; ToS forbids scraping** | `unsupported` (by design) |
| Reddit | Official OAuth API | `needs_credentials` |
| YouTube | Data API v3 (search + commentThreads) | `needs_credentials` |
| X | API v2 recent search (paid tier for reads) | `needs_credentials` |
| Facebook / Instagram | Graph API (search retired / App Review) | `needs_credentials` → `blocked` |

- With credentials configured in `backend/.env`, adapters perform **real**
  authorized calls (retry with exponential backoff, timeouts, upstream errors
  surfaced as `blocked`/`error`).
- When live access is unavailable and **“Include sample dataset”** is ON, the
  report is filled from a clearly-labelled synthetic corpus (EN/UR/Roman Urdu,
  sarcasm, spam, seller-vs-product complaints). Every layer marks it:
  `success_sample` status, SAMPLE badges, `data_source=sample` in DB, and an
  amber banner on the dashboard. Sample mode is **never** presented as real data.

---

## 4. Setup

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate   # or use system python
pip install -r requirements.txt
cp .env.example .env      # add credentials when you have them
alembic upgrade head      # or let init_db create tables automatically

# frontend deps are managed by the sandbox dev server (bun run dev, port 3000)
```

Run backend standalone: `cd backend && python3 -m uvicorn app.main:app --port 8317`
In the sandbox preview, the frontend starts it automatically via `/api/py-health`.

Run tests: `cd backend && python3 -m pytest tests/ -q` (51 tests).

### Environment variables (`backend/.env`)

All secrets come from env — see `backend/.env.example` for the full list
(platform credentials, `SQLALCHEMY_DATABASE_URL`, `TASK_QUEUE`, tuning knobs).
Never commit real credentials.

---

## 5. API summary

| Endpoint | Description |
|---|---|
| `GET /api/health` | service + DB status |
| `GET /api/platforms` | capability/status matrix for all 12 platforms |
| `POST /api/search` | create search job `{product_name, description?, platforms?, include_sample}` |
| `GET /api/jobs/{id}` | job status + per-platform status (poll) |
| `GET /api/jobs/{id}/report` | full aggregated report (verdict, comparison, aspects, languages, trends) |
| `GET /api/jobs/{id}/reviews` | filterable/sortable/paginated review explorer |
| `GET /api/jobs/{id}/export.csv` / `export.pdf` | exports |
| `GET /api/docs` | OpenAPI docs |
| `POST /api/chat` (Next.js) | grounded AI assistant (uses only collected data) |

### Verdict methodology

`score = 50 + 50 × confidence-weighted average of comment sentiment (−1..1)`.
Verdict thresholds on sentiment shares require ≥ 5 analyzed comments, else
**Insufficient Data**. Platforms with < 10 comments are flagged *low sample*
and excluded from ranking. Sentiment percentages describe the collected sample
only — they are not customer ratings or verified quality measures.
