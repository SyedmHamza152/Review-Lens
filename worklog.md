# Worklog

---
Task ID: 1
Agent: main (Z.ai)
Task: Build AI-Powered Product Review Intelligence Platform (Next.js frontend + Python FastAPI backend)

Work Log:
- Initialized fullstack env; checked sandbox: Python 3.12, FastAPI/uvicorn/pandas/sklearn/reportlab preinstalled; no PostgreSQL/Redis -> SQLAlchemy+SQLite (postgres-ready SQLALCHEMY_DATABASE_URL), inline background threads (Celery-swappable TASK_QUEUE)
- Gateway: Caddy proxies ?XTransformPort=8317 to Python backend; Reddit/e-commerce APIs blocked w/o credentials -> adapters report honest status (needs_credentials/blocked/unsupported) + clearly-labelled sample corpus mode
- Built backend/app: core (config/db), models (search_jobs, job_platform_status, product_matches, reviews, report_cache; dedup constraints), schemas (pydantic)
- NLP engine: language detection (EN/UR-script/Roman-Urdu/mixed w/ loanword handling + confidence), Roman Urdu variant normalizer (100+ variants), merged EN/RU/URD lexicons, context sentiment (negation window +-3, intensifiers, adversative clause split -> Mixed, non-neutral clause scoring), ABSA (11 aspects, product-vs-seller scope), gloss translator, spam/relevance/dedup
- Integrations: BaseAdapter contract; 6 marketplace + 6 social adapters (real OAuth/API-key flows coded; honest status when creds missing); sample_corpus (3 archetypes: phone/earbuds/sneakers, ~100 curated multilingual comments + spam examples)
- Orchestrator: parallel adapter collection (workers do HTTP only; DB on main thread - fixed segfault from shared Session), pipeline, aggregation (verdict 0-100, thresholds, comparison w/ low-sample flags, aspects, languages, weekly trends)
- API: /api/health /platforms /search /jobs/{id} /jobs/{id}/report /jobs/{id}/reviews (8 filters) /export.csv /export.pdf (reportlab 3-page report)
- Backend persistence: sandbox reaps stray/detached processes; fixed by spawning uvicorn as NON-detached child of persistent next-server via /api/py-health route (health-check + spawn + wait; idempotent). Never detach children here.
- Frontend: single-page SPA (home -> progress -> dashboard) in src/app/page.tsx with URL-hash persistence (#/job/{id}); components in src/components/reviewintel: chrome, home-view (search + platform picker + sample toggle w/ disclosure), progress-view (poll), charts (Recharts: donut/stacked/volume/trend/aspect/lang pie/by-language), overview/comparison/explorer/assistant/methodology tabs; TanStack Query
- AI assistant: /api/chat (Node runtime) fetches report + representative reviews from Python backend, builds bounded evidence block, z-ai-web-dev-sdk LLM with strict anti-hallucination rules (discloses sample mode, cites platforms, refuses insufficient data)
- Tests: 51 pytest cases pass; evaluation on 120 labeled PK comments (tests/data/eval_dataset.tsv): EN acc .87/F1 .83, RU 1.00/1.00, URD 1.00/1.00, mixed .88/.87; lang-detect .76; overall macroF1 .93 (after non-neutral clause scoring fix + sarcasm heuristic fix)
- Alembic scaffold + initial migration generated & applied (backend/alembic/versions/afb0d1ea9230_initial_schema.py)
- Agent Browser e2e verified via gateway :81: home render, search submit, progress, dashboard (verdict/donut/aspect/lang charts), comparison (low-sample flags), explorer (filters/badges/expand), assistant (2 grounded answers w/ sample-mode disclosure + Roman Urdu quotes), methodology tab, insufficient-data flow (honest), mobile 390px layout, exports CSV/PDF through gateway; fixed verdict-bar color bug; removed instrumentation.ts (edge-runtime warnings; py-health route covers spawn)
- Docs: README.md (architecture, NLP, data-access reality table, setup, API, methodology), backend/.env.example, backend/.env (no real creds)

Stage Summary:
- Working MVP delivered: search -> collect -> multilingual analyze -> dashboard -> compare -> explorer -> AI chat -> CSV/PDF export
- Backend: port 8317 (child of next-server), DB backend/data/review_intel.db, 51 tests green
- Frontend: SPA on /, emerald/teal theme, responsive, honest SAMPLE badges everywhere
- Key lessons: SQLAlchemy Sessions are not thread-safe (job threads must not share); sandbox process reaper kills detached/orphan processes; XTransformPort gateway only works through Caddy (:81), not raw :3000
