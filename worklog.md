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

---
Task ID: 2
Agent: main (Z.ai)
Task: Replace synthetic sample data with REAL platform API data (user demand: "i want real data not the sample dataset, use platforms API to access the comments")

Work Log:
- Verified live connectivity from sandbox with curl probes: Reddit direct JSON 403 (datacenter block), Arctic-Shift Reddit archive 200, HN Algolia 200, Daraz catalog ajax 200, YouTube/X/eBay/Reddit-OAuth reachable-but-need-keys, Daraz mtop h5 gateway nonexistent (review text truly needs Open Platform), Steam appreviews redirects (dropped)
- Discovered Arctic-Shift quirks: text-search (body=/title=) aggressively rate-limited (HTTP 422 "Timeout. Maybe slow down a bit"), light per-subreddit fetches always fine; multi-word queries 422
- New backend/app/integrations/live_sources.py: ArcticShiftClient (paced 2s, retry w/ backoff, graceful text-search degradation), collect_reddit (fetch-and-filter by distinctive product tokens + opportunistic text-search booster + thread expansion for matched posts, drops [removed]/[deleted]/bots), HackerNewsAdapter (stories + comments, HTML-stripped), fetch_daraz_catalog (40 listings: rating, review_count, price, seller, sold count)
- RedditAdapter now LIVE w/o creds (OAuth path kept, auto-selected when REDDIT_CLIENT_ID/SECRET set); DarazAdapter returns aggregate_items (new AdapterResult field) + Open Platform text reviews when creds; HackerNewsAdapter registered (13 platforms total)
- New PlatformListing model (+alembic revision c7f2a91b4e10) persisted in pipeline; aggregation adds marketplace_listings section to report (clearly labelled as platform-side counters, NOT sentiment)
- live_capability metadata on adapters (live / requires_credentials / not_available) exposed via /api/platforms, sorted live-first
- Sample corpus quarantined: SearchRequest.include_sample default False, UI toggle removed, orchestrator comments clarify test-only; conftest hermetic _hermetic_adapters fixture (offline stubs) keeps pytest deterministic
- Frontend: home hero badge "3 live sources", LIVE chips on platform picker, green live-data notice replaces amber sample toggle; overview tab green LIVE banner + Marketplace rating snapshots card; methodology tab documents verified matrix; chrome footer updated; chat route context includes marketplace_listings + live-data reminders
- .env.example documents new settings (REDDIT_SUBREDDITS, REDDIT_LOOKBACK_DAYS, ARCTIC_MIN_INTERVAL_SECONDS, HN_*, DARAZ_CATALOG_MAX_ITEMS); README data-access table rewritten with verified statuses
- E2E REAL test: "iPhone 15" job -> reddit 73 real mentions, hackernews 120 real items, daraz 40 real listings (avg 4.8, 160 ratings); 189 collected -> 85 analyzed (13 spam, 91 low-relevance); verdict Mixed Feedback 53.1; dashboard/browser verified (LIVE DATA badge, charts, explorer with real dated Reddit comments, marketplace snapshots card)

Stage Summary:
- Platform now runs on REAL data only: Reddit (public archive), Hacker News (Algolia), Daraz PK (catalog aggregates); 10 remaining platforms honest as needs_credentials/not_available, real authorized clients activate from .env
- 59 pytest cases green (incl. 7 new live-source tests w/ mocked HTTP); sample corpus reachable only from tests
- Key lesson: Arctic-Shift text-search 422s under bursts - always use light fetch+local filter as primary; requests params must send daraz ajax as string "true"
- Real job id for reference: dbcc5fd9-0a38-4ea4-adc8-ce004acdf936 (iPhone 15, live)

---
Task ID: 3
Agent: main (Z.ai)
Task: Show REAL comments + enforce 50-comment minimum + add YouTube API (user: "it does not show the comments... get min 50 comments... also fetch the Youtube API as well")

Work Log:
- Probed Daraz review-text access with agent-browser network capture + JS-bundle grep: PDP uses mtop.global.detail.web.getDetailInfo on acs-m.daraz.pk -> RGV587_ERROR cloud_ip_bl (Alibaba datacenter-IP blocklist); storefront /pdp/review/getReviewList routes to SPA error page even with cookies/referer/trailing-slash. Conclusion: Daraz review TEXT unobtainable from this deployment (code-level fix impossible; Open Platform creds unlock it)
- Probed YouTube: InnerTube (public WEB client key, no credentials) search + comments BOTH live from sandbox; commentEntityPayload parsing + continuation pagination verified; googleapis reachable for official Data API v3
- live_sources.py: added YouTubeInnertubeClient (paced 1s, backoff, engagement-panel comment-token extraction, frameworkUpdates commentEntityPayload parsing, continuation pages, relative-time parser), collect_youtube (search "{product} review" -> up to 10 videos x 40 comments, video-scoped relevance_hint=0.6 - same rationale as marketplace product-page items), fetch_daraz_reviews (self-healing PDP attempt -> honest block note)
- YouTubeAdapter now LIVE without key (InnerTube) + official paginated Data API v3 path auto-selected when YOUTUBE_API_KEY set; DarazAdapter attempts review text then falls back to aggregates + honest note
- 50-comment minimum (MIN_COMMENTS_FOR_ANALYSIS=50): aggregation computes per-platform qualifying counts, below_minimum_platforms with exact message "Only N real comments found on X - below the 50-comment minimum, so sentiment analysis cannot be processed for this platform...", status rows annotated, verdict/aspects/languages/trends/ranking computed from qualifying platforms ONLY, verdict.basis + minimum_note + score null when nothing qualifies; comparison rows carry meets_minimum/analysis_processed/below_minimum_message with null percentages
- Frontend: types extended (Verdict.score nullable, basis, BelowMinimumPlatform, totals fields); overview shows amber per-platform banners + "Real comments collected" live preview card (fetches /reviews sort=relevance) + platforms-meeting-minimum stat + verdict null-safe; comparison tab: 50-min notice, "below 50 min" badge with tooltip message, em-dash percentages, chart filtered to processed rows; explorer gets below-minimum banners; dashboard header shows verdict basis; tsc clean
- Tests: +5 (InnerTube payload parsing e2e via mocked _post, relative-time parser, daraz blocked-note honesty, min-50 policy on real pipeline+aggregation, platforms listing youtube=live); test_full_search_flow updated for the honest insufficient-data branch; 63 passed
- E2E REAL (job fbbeff10-004a-45e4-89ea-de95f97f95c0, "cricket bat" + daraz + youtube): YouTube 120 real comments collected -> 116 analyzed (4 spam) >= 50 -> verdict Mixed Feedback 67/100, aspects (price 6, performance 4...), languages (113 en, 2 roman_urdu, 1 mixed), 11-week trends; Daraz: 40 live listings (avg 4.82, 2111 ratings) + 0 text comments -> exact below-minimum message; UI verified in browser (LIVE DATA badge, banners, real-comment preview, comparison badges, explorer rows w/ sentiment+language+source links); AI chat grounded (cites real YouTube comments, discloses sample limits)

Stage Summary:
- Comments now SHOW: overview preview card + explorer list real verbatim comments with platform/sentiment/language/date/source links
- Live platforms: YouTube (NEW, no key needed), Reddit archive, Hacker News, Daraz catalog aggregates; 9 others honest as needs_credentials/unsupported
- 50-comment minimum enforced per user spec: >=50 -> full analysis; <50 -> exact "comments less than 50 on that platform" message, raw comments still viewable, no fabricated analysis
- Daraz review text remains impossible from datacenter IPs (Alibaba anti-bot) - Open Platform creds (DARAZ_APP_KEY/SECRET) or non-datacenter deployment unlock it; message states this honestly

---
Task ID: 4
Agent: main (Z.ai)
Task: Implement official Daraz Open Platform API client (user pasted the Open Platform API test docs after "daraz does not able to fetch the comment")

Work Log:
- Researched official docs: open.daraz.com/doc/api.htm (Daraz mirrors Lazada Open Platform/LAZOP protocol - shared doc node IDs). Signature algorithm from official developer guide: sort params ASCII -> concat key+value -> prepend API path -> HMAC-SHA256 (sign_method=sha256) or HMAC-MD5 (sign_method=hmac) with app secret -> uppercase hex. Official worked example: secret "helloworld", /order/get -> 4190D32361CFB9581350222F345CB77F3B19F0E31D162316848A2C1FFD5FAB4A (reproduced verbatim in tests)
- Product Review API section: /review/seller/history/list (item_id + start/end ms, 7-day max span, 90-day history, max 50 pages -> id_list) + /review/seller/list/v2 (id_list max 10 -> review_content, ratings.overall_rating, submit_time, product_id, review_type). Endpoints: api.daraz.pk (PK), .com.bd, .lk, .com.np, shop.com.mm
- New backend/app/integrations/daraz_open_platform.py: DarazOpenPlatformClient (signed GET w/ epoch-ms timestamp, business-error mapping code!=0 -> DarazOpenPlatformError, TRAFFIC_CONTROL backoff, 0.35s pacing), sign_request/sign_request_hmac_md5, search_products (/products/get filter=search), collect_review_items orchestration (products -> 7-day window walk -> id dedupe -> batched bodies -> ReviewItem w/ rating/date/source_url/product PDP url, diagnostics per stage)
- Replaced the old placeholder _search_open_platform (wrong method name/MD5/datetime-format timestamp/wrong base URL) in DarazAdapter: open_platform_ready checks DARAZ_APP_KEY+SECRET+ACCESS_TOKEN; with creds -> official client first, real review text + honest seller-scope message; API errors -> BLOCKED with raw [code] message; missing creds -> catalog aggregates live + precise setup message (exact 3 env vars + open.daraz.com registration steps)
- Config: +DARAZ_ACCESS_TOKEN, DARAZ_COUNTRY (pk/bd/lk/np/mm), DARAZ_SIGN_METHOD (sha256|hmac), DARAZ_REVIEWS_TARGET=50, DARAZ_LOOKBACK_DAYS=90; .env.example rewritten with 5-step registration guide + seller-scope note
- registry.platform_listing exposes optional_env (unlock-only vars on live baseline); frontend types + PlatformChip tooltip shows "Unlocks more data with: DARAZ_APP_KEY . DARAZ_APP_SECRET . DARAZ_ACCESS_TOKEN"
- LIVE PROBE: signed /brands/get with dummy creds -> api.daraz.pk REACHABLE from this deployment, server replied business error InvalidAppKey (protocol accepted by real server; storefront RGV587 block does NOT affect the Open Platform gateway)
- Tests: new tests/test_daraz_open_platform.py, 11 cases (official signature vector, hex/order/endpoint tables, signed URL assembly, business error propagation, 403 mapping, full mocked collection e2e incl. 10-id batch limit + field mapping, empty product match, adapter w/o creds honest, adapter w/ creds collects, auth error surfacing). Full suite 74 passed
- E2E "cricket bat" + daraz + youtube (job 2a99496f-5ed5-4c62-afcd-c53057180ec3): YouTube 120 real comments -> 118 analyzed >= 50 -> verdict Mixed 72.3; Daraz 40 live listings + 0 text comments (no creds configured) with exact below-minimum message; browser-verified LIVE DATA badge, real comment cells in Review explorer, Daraz banner; screenshot download/cricket-bat-daraz-openplatform.png

Stage Summary:
- Daraz now speaks the REAL official Open Platform protocol (user-pasted docs implemented exactly): the moment DARAZ_APP_KEY + DARAZ_APP_SECRET + DARAZ_ACCESS_TOKEN are set in backend/.env, real buyer comments flow through the signed review APIs
- Gateway verified reachable from deployment -> credentials are the ONLY missing piece; message in UI tells the user exactly that + how to register
- Review APIs are seller-scoped by Daraz's design (authorized seller's own listings); system states this honestly instead of pretending otherwise
- 74 tests green; backend restarted via py-health spawn (pid 12153)
