# AlphaMatrix — Architecture & Technical Report

> Generated 2026-07-10 for external AI-assisted optimization planning. All facts below are pulled directly from source in this repository (not from documentation aspirations) — file paths and line numbers are given so claims can be re-verified against current code.

---

## 1. Overview

**AlphaMatrix** is a quantitative research terminal for **Indian mutual funds and equities**. It combines deterministic multi-factor scoring engines (no ML/LLM in the scoring path), a multi-source news aggregator, LLM-generated research briefings grounded by a separate deterministic rubric, historical verdict backtesting, and a Bloomberg-Terminal-styled UI.

**Design principle (load-bearing, not decorative):** *"AI explains the verdict, the engine decides the verdict."* Every BUY/HOLD/AVOID rating comes from a deterministic formula over financial ratios and price data. Groq's LLM is only ever asked to narrate an already-computed score — a rubric-based grounding layer (`briefing_intelligence.py`) hard-anchors the LLM's verdict language and a post-hoc validator penalizes the LLM if it contradicts the anchor.

**Target users:** retail/prosumer Indian equity and mutual-fund investors who want institutional-style multi-factor analysis without a Bloomberg terminal subscription — the persona implied throughout (sector benchmarks are NSE/Screener.in Indian-market medians, CAGR benchmarks assume INR categories, watchlist/portfolio features assume a single retail user, not a multi-tenant institutional workflow).

**Deployment URLs:**
- Frontend (production): `https://alphamatrix-alpha.vercel.app/`
- Backend (production): `https://alphamatrixbackend.vercel.app` (also the default value of `BACKEND_URL` in `backend/app/core/config.py:50` — used by QStash to call back into the API)
- Local dev: frontend `http://localhost:5173`, backend `http://localhost:8000`

**Repo layout:** monorepo, two independently-deployed Vercel projects (`backend/`, `frontend/`), no shared package/build step between them — they only communicate over HTTP.

---

## 2. Tech Stack (exact versions)

### Frontend — `frontend/package.json` + `package-lock.json` (resolved)
This is a **Vite + React SPA, not Next.js** — no SSR, no file-based routing, no API routes on the frontend side. Worth flagging since Next.js is a common assumption for React deployments on Vercel.

| Package | Declared | Resolved (lockfile) |
|---|---|---|
| react / react-dom | ^19.2.6 | **19.2.7** |
| vite | ^8.0.12 | **8.0.16** |
| @tanstack/react-query (+devtools) | ^5.101.1 | 5.101.1 |
| react-router-dom | ^7.17.0 | 7.17.0 |
| axios | ^1.17.0 | 1.17.0 |
| firebase | ^12.15.0 | 12.15.0 |
| recharts | ^3.8.1 | 3.8.1 |
| tailwindcss | ^3.4.19 | 3.4.19 |
| lucide-react | ^1.17.0 | — |
| eslint | ^10.3.0 | — |

Build: `vite build` → static `dist/`. Routing is 100% client-side (React Router v7); `frontend/vercel.json` rewrites all paths to `/index.html`.

### Backend — `backend/requirements.txt` (floor pins) + `pip freeze` (actually installed in `.venv`)

| Package | Pinned floor | Installed |
|---|---|---|
| fastapi | >=0.110.0 | **0.137.1** |
| uvicorn[standard] | >=0.28.0 | 0.49.0 |
| pydantic / pydantic-settings | >=2.6.0 / >=2.2.0 | 2.13.4 / 2.14.1 |
| sqlalchemy[asyncio] | >=2.0.28 | 2.0.51 |
| asyncpg | >=0.29.0 | 0.31.0 |
| aiosqlite | >=0.20.0 | — |
| pandas | >=2.2.0 | **3.0.3** |
| numpy | >=1.26.0 | **2.4.6** |
| httpx | >=0.27.0 | 0.28.1 |
| redis | >=5.0.3 | **8.0.0** |
| groq | >=0.9.0 | **1.4.0** |
| openai | >=1.14.0 | — (imported nowhere active; see §9) |
| python-jose[cryptography] | >=3.3.0 | — |
| passlib[bcrypt] | >=1.7.4 | — |
| yfinance | >=1.4.1 | 1.4.1 |
| curl_cffi | >=0.7.0 | — |

Python: `backend/runtime.txt` pins **`python3.12`** for Vercel; the local `.venv` is actually running **3.14.5** — a version drift between local dev and the deploy target worth being aware of when debugging "works locally, fails on Vercel."

**Database:** PostgreSQL via **Neon** (serverless, connection-pooled) in production; SQLite (`aiosqlite`) is the zero-config local default. Driver: SQLAlchemy 2.0 async + `asyncpg`.

**Cache/queue:** **Upstash Redis** (REST API in production, since Vercel functions can't hold a persistent TCP connection cheaply; raw TCP `redis-py` locally) + **Upstash QStash** as an async job queue for the stock-ingestion pipeline (works around Vercel's function-duration limits — no separate worker process exists).

**AI:** Groq, model **`llama-3.3-70b-versatile`** (hardcoded constant `AI_MODEL` in `backend/app/services/ai_agent.py:12`), used for every LLM feature in the app — briefings, chat, semantic search parsing, news impact analysis, comparisons, sector outlooks. No other model/provider is actually wired despite `openai` being in requirements.

**Auth:** Firebase (email/password + Google) is the *real* identity system — verified server-side in `backend/app/core/security.py` by fetching Google's public certs and validating the RS256 JWT locally (no Firebase Admin SDK, no server-side Firebase project config needed). A separate legacy `app/api/v1/auth.py` mock-JWT system also exists (accepts any password ≥6 chars) — dead code path from an earlier phase, not used by the current frontend flows except possibly stale references.

---

## 3. Architecture

### 3.1 Folder structure

```
backend/
  api/index.py            # Vercel ASGI entrypoint — imports app.main:app as `handler`
  vercel.json              # rewrites all paths → api/index.py, maxDuration 60s/512MB, 2 crons
  app/
    api/v1/
      stocks.py (2191 LOC) # by far the largest route file — grid list, split detail
                            #   endpoints, ingestion status/advance, compare, watchlist,
                            #   sector, market-regime, backtest, prewarm, cold-misses
      funds.py (572 LOC)   # fund CRUD, rating breakdown, category peers, sync/sync-all
      internal.py (188 LOC)# QStash-only webhook: runs all 4 ingestion stages
      news.py (298 LOC)    # india/global multi-source feeds, legacy /list, /analyze
      search.py (259 LOC)  # unified stock+fund search, yfinance discovery fallback
      ai.py                # semantic-query + fund chat
      auth.py               # legacy mock JWT (see §3 note above)
    models/                # SQLAlchemy ORM: fund.py, stock.py, user.py
    schemas/               # Pydantic response models
    services/
      fund_rating_engine.py     # 6-factor deterministic fund scoring
      briefing_intelligence.py  # deterministic rubric + prompt builder + validator
      news_aggregator.py (354 LOC)  # RSS fetch + regex XML parse + Jaccard dedup
      backtesting.py (284 LOC)      # T+30/90/180/365 verdict-accuracy engine
      qstash.py (202 LOC)           # publish + HMAC-SHA256 JWT webhook verification
      ai_agent.py                   # all Groq calls, mock fallbacks
      analytics.py                  # CAGR/Sharpe/Sortino/drawdown math
      cache_service.py              # thin Redis key/TTL wrapper (search/news/AI)
    workers/
      stock_ingestion.py (2506 LOC) # Alpha Score model + 4-stage progressive pipeline
      ingestion.py                  # fund NAV ingestion
      cron_jobs.py                  # overnight fund re-sync
    core/
      database.py           # dual SQLite/Postgres async engine, lazy cold-start init
      redis.py               # dual-mode client: TCP redis-py OR Upstash REST
      security.py             # Firebase verification + in-process rate limiter (see §9)
      cache_ttl.py             # centralized TTL constants
      config.py                # pydantic-settings

frontend/
  src/
    pages/        # Home, Explorer, Detail (funds); StockHome, StockExplorer,
                   #   StockDetail, StockSector, StockCompare, StockWatchlist (stocks);
                   #   News, Login, Signup, Settings
    components/    # GlobalSearch, FloatingChatAssistant, BriefingReport, charts/*
    hooks/
      useQueries.js   # current React Query layer — split endpoints, adaptive polling
      useFunds.js / useStocks.js  # legacy imperative fetch hooks, still partially used
    services/       # api.js (axios instance), auth.js, firebase.js
```

### 3.2 Deployment model — both apps are Vercel Serverless Functions, not long-running servers

- **Backend**: `backend/vercel.json` rewrites every path to a single serverless function `api/index.py`, which just imports and re-exports the FastAPI `app` object as `handler` (Vercel's Python runtime wraps this as an ASGI handler). `maxDuration: 60`, `memory: 512` (MB). There is **no dedicated worker/queue process** — everything must fit inside a single request/response lifecycle or be handed off asynchronously to QStash.
- Two Vercel Crons defined in the same file: `GET /api/v1/stocks/prewarm` daily at `21:00 UTC`, and `GET /health` daily at `03:00 UTC` (keepalive/cold-start ping).
- **Frontend**: static Vite build served from Vercel's static/edge layer; `frontend/vercel.json` is just an SPA catch-all rewrite to `index.html`.
- **Cold starts** are a first-class design constraint, not an afterthought — see `database.py`'s Redis-flag-gated migration skip (`_check_migration_done`/`_set_migration_done`, `backend/app/core/database.py:105-125`) and the lazy DB-init pattern in `main.py` (`_ensure_db_ready`, since `@app.on_event("startup")` doesn't reliably fire on Vercel).

### 3.3 Frontend ↔ Backend communication

- Plain REST/JSON over `axios` (`frontend/src/services/api.js`), no GraphQL, no websockets.
- Auth: Firebase ID token attached as a Bearer token; backend validates it per-request against Google's public keys (cached in-process for 1 hour, `security.py:78`).
- **Long-running work is never done synchronously in a GET** for stocks — see the progressive-discovery/QStash pipeline in §5.3. The frontend polls a `/status/{symbol}` endpoint (adaptive 1.5s→3s interval) and renders sections (`meta`/`metrics`/`chart`/`briefing`/`news`) incrementally as they land, rather than blocking on one big response.
- Funds use a **different, older pattern**: `GET /funds/{scheme_code}` triggers `BackgroundTasks.add_task(...)` (FastAPI's in-process background task, not QStash) for ingestion/AI-summary generation, and the client just re-polls the same detail endpoint until `ai_summary` stops being the placeholder string. This is architecturally inconsistent with the stock pipeline's explicit QStash migration — see §9.

### 3.4 Environment variables (names only — see `backend/.env.example` and README)

```
DATABASE_URL                      # postgresql+asyncpg://... (Neon) or sqlite+aiosqlite:// (local default)
REDIS_URL                         # optional direct TCP redis (local dev)
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
QSTASH_URL                        # defaults to https://qstash.upstash.io
QSTASH_TOKEN
QSTASH_CURRENT_SIGNING_KEY
QSTASH_NEXT_SIGNING_KEY           # optional, key-rotation window
BACKEND_URL                       # public backend URL QStash calls back into
GROQ_API_KEY
OPENAI_API_KEY                    # declared, effectively unused (see §9)
SECRET_KEY                        # JWT signing for the legacy mock auth
BENCHMARK_SCHEME_CODE             # default 120687 = HDFC Nifty 50 Index Fund
RISK_FREE_RATE                    # default 0.06
```
No Firebase env vars are needed server-side — token verification hits Google's public JWKS endpoint directly. Firebase config lives client-side only, in `frontend/src/services/firebase.js`.

---

## 4. Database Schema

SQLAlchemy declarative models, dual-backend (SQLite locally / Postgres+Neon in prod). Migrations are hand-rolled `ALTER TABLE ADD COLUMN IF NOT EXISTS` blocks run in `init_db()` (`backend/app/core/database.py`) — **no Alembic**, no versioned migration files. A Redis flag (`alphamatrix:schema_v3_done`, 30-day TTL) gates whether the slow ALTER/CREATE INDEX path runs on a given cold start; `create_all` (idempotent, fast) always runs.

### `stock_masters` (`app/models/stock.py`)
PK: `symbol` (String50). Columns: `company_name`, `isin`, `sector`, `industry`, `market_cap`, `pe_ratio`, `pb_ratio`, `roe`, `debt_equity`, `dividend_yield`, `beta`, `cagr_1y/3y/5y`, `alpha_score` (0–100) plus 8 sub-scores (`fundamental_score`, `valuation_score`, `technical_score`, `risk_score`, `sector_relative_score`, `quality_score`, `event_score`, `confidence_score`), `investor_verdict`, `trader_verdict`, `trend_structure`, `bull_case`/`bear_case`/`verdict_rationale` (Text), `ai_summary` (Text — full briefing markdown), `ingestion_status` (state machine, default `"READY"`), `current_price`, `exchange`, `last_updated`.
Relationships: `price_history` (1:N → `StockPriceHistory`, cascade delete), `watchlist_items` (1:N → `WatchlistItem`, cascade delete).

### `stock_price_histories`
PK `id`; `symbol` FK→`stock_masters.symbol` (CASCADE); `date`; `close`. Composite index `idx_stock_price_symbol_date(symbol, date)`.

### `watchlist_items`
PK `id`; `email`; `symbol` FK→`stock_masters.symbol` (CASCADE); `added_at`. Unique composite index `idx_watchlist_email_symbol(email, symbol)`.

### `fund_masters` (`app/models/fund.py`)
PK: `scheme_code` (Integer). Columns: `isin`, `fund_name`, `category`, `sub_category`, `pe_ratio`, `expense_ratio`, `cagr_1y/3y/5y`, `sharpe_ratio`, `sortino_ratio`, `alpha`, `beta`, `fund_score` (0–100), `fund_verdict`, `std_deviation`, `max_drawdown`, `aum`, `consistency_score`, `category_rank`, `category_count`, `category_avg_cagr_3y/sharpe/alpha`, `ai_summary`/`bull_case`/`bear_case`/`fund_rationale`, `last_updated`.
Relationship: `nav_history` (1:N → `NAVHistory`, cascade delete).

### `nav_histories`
PK `id`; `scheme_code` FK→`fund_masters.scheme_code` (CASCADE); `date`; `nav`. Index `idx_nav_scheme_date(scheme_code, date)`.

### `users`
PK `id`; `email` (unique); `hashed_password`; `is_active`; `is_superuser`. **Vestigial** — real identity is Firebase; this table only backs the legacy mock-auth path.

### Sort-heavy indexes
`idx_stock_alpha_score` (desc), `idx_stock_cagr3y` (desc), `idx_fund_cagr3y` (desc), `idx_fund_sharpe` (desc) — added specifically because `alpha_score`/`cagr_3y`/`sharpe_ratio` are the default sort columns on the list/explorer endpoints.

### Search indexes (separate from the migration-flag path, backend-specific)
- **SQLite**: FTS5 virtual tables `stock_search_index(symbol, company_name, exchange UNINDEXED)` and `fund_search_index(scheme_code, scheme_name)`.
- **Postgres**: `pg_trgm` extension + plain tables `stock_search_index`/`fund_search_index` with GIN trigram indexes on `symbol`/`company_name`/`scheme_name`, plus trigram indexes directly on `stock_masters.company_name` and `fund_masters.fund_name`.

### Migration status
No formal migration framework/history — schema evolves via idempotent `ADD COLUMN IF NOT EXISTS` in `init_db()`, executed once per cold start-generation (gated by the Redis flag). This means **schema changes require bumping the Redis flag key name** (currently `schema_v3_done`) to force re-run, or the new columns silently won't be added on already-migrated deployments until the flag expires (30 days) or is manually cleared.

---

## 5. Core Business Logic

### 5.1 Stock Institutional Rating Engine v2 — "Alpha Score" (`backend/app/workers/stock_ingestion.py:calculate_institutional_ratings`, lines 863–1112)

Six intermediate 0–100 sub-scores feed a weighted final score:

```python
final_score = (
    0.25 * fundamental_score +
    0.15 * quality_score +
    0.20 * valuation_score +
    0.15 * technical_score +
    0.15 * risk_score +
    0.10 * sector_relative_score
)
# Overheat penalties applied AFTER the weighted sum:
if rsi > 75.0: final_score -= 10.0
if pe > sect_pe * 1.8: final_score -= 15.0
if dma_200 and latest_price > dma_200 * 1.30: final_score -= 10.0
final_score = round(max(0.0, min(100.0, final_score)), 1)
```

Note this differs slightly from the README's documented 5-factor formula (fundamental/valuation/technical/risk/sector, 30/20/20/15/15) — the **actual shipped code** is a 6-factor model with `quality_score` split out and different weights (25/15/20/15/15/10). The README is stale on this point; the code above is ground truth.

- **Fundamental (25%)**: weighted blend of ROE, ROCE, operating margin, net margin, revenue growth, profit growth, FCF sign, and 1Y/3Y CAGR consistency. All inputs default to sane placeholder values when missing (e.g. `roe or 15.0`) rather than nulling out the score.
- **Quality (15%)**: margin stability, cash conversion (FCF+growth combo), debt quality (`100 - de*60`), returns stability.
- **Valuation (20%)**: P/E and P/B scored *relative to live sector averages* (`get_sector_averages`, DB-computed, Redis-cached 24h key `sector_averages:{sector}`), plus EV/EBITDA and PEG against fixed thresholds. PE≤0 (loss-making) scores 0 outright.
- **Technical (15%)**: RSI, MACD bullish/bearish, price vs 50-DMA, price vs 200-DMA, 50-DMA vs 200-DMA alignment — each computed from `calculate_technical_indicators` over the stored 3-year daily close series (pandas rolling windows/EWM). **Hard-capped at 45 if `trend_structure == "BEARISH"`** (swing high/low structure detector, `detect_trend_structure`).
- **Risk (15%)**: debt/equity risk, interest coverage risk, promoter-holding risk (binary ≥45% threshold), beta-derived volatility risk, and a news-derived `event_score` (regex classification of recent headlines into positive/negative event categories, §5.4-adjacent).
- **Sector Relative (10%)**: ROE/D-E/3Y-CAGR of the stock vs. the same live sector averages used in valuation.
- **Confidence score**: `completeness% - divergence_penalty - sector_penalty - news_penalty`, where `divergence_penalty` fires if `|fundamental_score - technical_score| > 25` (data/momentum disagreement flag), floor 10.

Verdict mapping (both investor and trader verdicts currently use the **same** `map_verdict` function — the README's separate momentum-biased "Trader Verdict Mapping" table does not correspond to any different formula in the current code; `investor_verdict` and `trader_verdict` are set to the identical value at lines 1095–1096):
```
≥74 STRONG BUY · ≥66 BUY · ≥56 HOLD · ≥46 REDUCE · else AVOID
```

### 5.2 Fund Rating Engine v1 (`backend/app/services/fund_rating_engine.py`)

Cleanly separated pure-function module, 6 weighted factors:
```python
WEIGHTS = {"cagr": 0.25, "consistency": 0.15, "risk": 0.20, "quality": 0.15, "alpha": 0.15, "peer": 0.10}
```
- **CAGR (25%)**: 1Y/3Y/5Y scored against category-specific benchmarks (`CATEGORY_CAGR_BENCHMARKS`: Large Cap 12/12/12%, Mid Cap 15/16/16%, Small Cap 18/20/20%, Index 10/11/11%, plus Sectoral/Flexi Cap/ELSS/Debt/Hybrid), time-weighted 20/50/30 across 1Y/3Y/5Y.
- **Consistency (15%)**: prefers a precomputed `std_deviation`; falls back to computing rolling-12-month-return variance directly from NAV history if fewer than 252 data points aren't available for the precomputed path.
- **Risk (20%)**: Sharpe (40%) + Sortino (35%) + Max Drawdown (25%), each piecewise-scored against fixed thresholds (e.g. Sharpe ≥1.5→95, Drawdown ≤5%→95).
- **Quality (15%)**: expense ratio (65%, category-aware bands — index funds judged much stricter than active equity) + AUM (35%, penalizes both <₹100Cr and >₹50,000Cr).
- **Alpha (15%)**: piecewise score of alpha vs Nifty 50.
- **Peer (10%)**: percentile of `category_rank`/`category_count`.

Verdict bands: `≥90 Elite · ≥75 Strong · ≥60 Good · ≥45 Average · else Avoid`. Includes `compute_std_deviation`/`compute_max_drawdown` helper functions that derive these metrics directly from a NAV price list when not otherwise available, and `generate_ai_fund_prompt` — a strict "explain, don't decide" prompt template fed to Groq for the Bull/Bear/Rationale cards.

### 5.3 Progressive Stock Discovery Pipeline (QStash-driven, `stock_ingestion.py` + `api/v1/internal.py` + `services/qstash.py`)

State machine on `StockMaster.ingestion_status`: `DISCOVERING → DISCOVERED → INGESTING → ANALYTICS_RUNNING → READY` (or `FAILED`).

1. `GET /stocks/detail/{symbol}/meta` on an unseeded symbol stubs a `DISCOVERING` row and calls `await publish_ingestion_job(symbol)` **synchronously before returning** — comment in code explains why: *"Vercel freezes the function the instant a response is sent, so fire-and-forget tasks would be killed."* Returns 202 in <300ms.
2. QStash POSTs to `POST /api/v1/internal/ingest-background`, verified via `Upstash-Signature` — a hand-rolled HMAC-SHA256 JWT verifier (`qstash.py:_verify_jwt`, lines 82–155) that checks `exp`, `iss=="Upstash"`, `sub` (destination URL, soft-fail on mismatch), body-hash claim (checked against both padded and unpadded base64url forms — a real Upstash quirk the code explicitly works around), and finally the HMAC signature itself using `hmac.compare_digest`. Supports **key rotation** by trying `QSTASH_CURRENT_SIGNING_KEY` then `QSTASH_NEXT_SIGNING_KEY`.
3. The webhook handler runs all 4 stages **sequentially in one invocation**, under a Redis `SETNX` lock `pipeline_lock:{symbol}` (120s TTL) to make QStash's automatic retries idempotent:
   - `quick_discover_stock` — yfinance `.info` only (name/sector/ISIN/market cap/PE/PB/ROE/D-E/price) → `DISCOVERED`
   - `ingest_step1_history` — 3y OHLC download into `StockPriceHistory` → `INGESTING`
   - `ingest_step2_analytics` — full `calculate_institutional_ratings` → `ANALYTICS_RUNNING`
   - `ingest_step3_briefing` — Groq briefing + bull/bear/verdict parsing → `READY`
4. Frontend's `useStockStatus` hook polls `/status/{symbol}` at an adaptive 1.5s→3s interval, stopping on `READY`/`FAILED`/`NOT_FOUND`; `StockDetail.jsx` renders chart/metrics/briefing/news incrementally as `available_sections` grows.
5. **Fallback when QStash isn't configured** (e.g. Vercel Hobby tier, or `QSTASH_TOKEN` unset): `/meta` runs `quick_discover_stock` inline, then the frontend drives the rest itself, one step per call, via `POST /stocks/ingest/{symbol}` (`advanceIngestionPipeline`), each call bounded to fit a shorter function timeout.
6. yfinance fetches use a hard **4-second HTTP adapter timeout** and parallelize `hist`/`info`/`news` fetches via a 3-worker `ThreadPoolExecutor` (`fetch_ticker_data_yfinance`, lines 1123–1189) — falls back from NSE (`.NS`) to BSE (`.BO`) suffix if the first lookup returns empty.

### 5.4 AI Equity Briefing — grounding rubric + generation flow (`backend/app/services/briefing_intelligence.py`)

This is the most architecturally deliberate part of the codebase — a deterministic scoring layer sits **between** the raw metrics and the LLM, so the LLM's verdict is anchored rather than free-floating.

**Step 1 — Data quality assessment** (`assess_data_quality`): checks 12 required fields (`pe_ratio, pb_ratio, roe, debt_equity, dividend_yield, beta, cagr_1y/3y/5y, market_cap, alpha_score, sector`), flags anomalies (negative P/E, negative P/B, ROE>100%, D/E>5, |beta|>3), and produces a `HIGH`/`MEDIUM`/`LOW` confidence label from completeness %.

**Step 2 — Deterministic 5-pillar rubric** (`score_verdict`), independent from (but partially overlapping with) the Alpha Score model:
```python
PILLAR_WEIGHTS = {"valuation": 0.26, "quality": 0.21, "momentum": 0.17, "risk": 0.21, "technical": 0.15}
```
- Valuation: P/E and P/B vs. a **separate, hardcoded** `SECTOR_BENCHMARKS` table (18 Indian sectors + "Default"), distinct from the Alpha Score engine's live-DB `get_sector_averages()` — intentionally, per an in-code comment, because live DB averages "can be noisy or empty for sparsely-populated sectors."
- Quality: ROE and D/E vs. the same benchmark table.
- Momentum: 1Y CAGR vs. a flat 12% Nifty proxy, 3Y CAGR vs. sector median.
- Risk: `10 - beta*3`, clamped 0–10.
- Technical: **reuses the Alpha Score model's own `technical_score`** (rescaled ÷10) — this was a deliberate fix (per in-code comments referencing "PHASE 0 divergence analysis") so the rubric isn't blind to market-structure signals the Alpha Score model already computes.
- Verdict bands: `≥7.5 → BUY/STRONG BUY · ≥6.5 → BUY/ACCUMULATE · ≥4.5 → HOLD · ≥3.5 → SELL/REDUCE · else SELL/STRONG SELL`.

**Step 3 — Verdict reconciliation** (`check_verdict_divergence` + `compute_divergence_reason`): the rubric's 3-tier BUY/HOLD/SELL direction is compared against the Alpha Score model's `investor_verdict`/`trader_verdict` (normalized from the 5-tier scale via `ALPHA_VERDICT_TO_DIRECTION`). If they diverge, `compute_divergence_reason` builds a **pillar-grounded explanation** — identifies the rubric's strongest/weakest pillar, computes a rank-distance magnitude ("Opposite-direction" vs "Adjacent-tier"), and explicitly names the two pillars the rubric *doesn't* model that the Alpha Score model does (`RUBRIC_MISSING_PILLARS = ["Fundamental (ROCE/margins/growth)", "Sector Relative (live peer comparison)"]`) — rather than surfacing a generic "verdicts disagree" flag.

**Step 4 — Prompt construction** (`build_briefing_prompt`): builds a system prompt with 7 numbered rules the LLM must follow:
1. Cite every factual claim as `[FACT: metric_name=value]`.
2. Label every paragraph `[DATA]` or `[ANALYTICAL]`.
3. **Verdict is fixed to the rubric's `{verdict}`/`{stance}`** — the LLM may add nuance but "CANNOT reverse or contradict this direction"; a deliberate override must be flagged with a literal `"OVERRIDE NOTE: [reason]"` string for human review rather than silently substituted.
4. Flag missing fields with `"⚠️ DATA GAP: {field} unavailable"`.
5. No hallucination — no invented news/earnings-call content; macro context must be labelled `"[MACRO CONTEXT — external knowledge]"`, ≤2 sentences/section.
6. Flag detected anomalies with `"⚠️ ANOMALY"`.
7. (Conditional, only injected when `divergence['diverges']` is true) — instructs the LLM to include an exact-format `"NOTE: Rubric score (...) diverges from Alpha Score model (...). Reason: ..."` line in the Final Verdict section, using the pre-computed `gap_explanation` rather than inventing its own.

Required output sections (exact `### Header` strings, since the frontend parses these literally): Executive Summary, Performance Analysis, Fundamental Analysis, Sector Analysis, Macro Analysis, Geopolitical Analysis, Investment Thesis, Risk Factors, Research Timeline (3–5 dated entries with a specific `"- **Month Year - Event**: ... | Relevance Score: X/10 | Impact Assessment: High/Medium/Low"` format), Bull Case, Base Case, Bear Case, Final Verdict, Confidence Score.

**Step 5 — Post-hoc validation & trust score** (`validate_briefing_output`): starts at `trust_score = 100`, deducts 8 pts per missing required section, 20 pts if the verdict/stance string isn't found in the output (unless an explicit `OVERRIDE NOTE` is present, which is treated as a flagged deviation rather than a penalty), 3 pts per missing field not flagged with a data-gap marker, 5 pts if anomalies exist but aren't flagged, 15 pts if output is <300 words. `is_valid = trust_score >= 60 AND verdict_match AND no_missing_sections`.

**Step 6 — Storage payload** (`build_storage_payload`): persists `{text, meta: {trust_score, data_completeness_pct, confidence_label, missing_fields, anomalies, verdict_anchor: {verdict, stance, final_score, pillar_scores, diverges_from_alpha_score}, divergence_reason, validation_warnings, generated_at, briefing_version: "v2"}}` — this is what's cached in Redis and what `BriefingReport.jsx` renders (citation footnotes, colored reasoning-label paragraphs, consolidated rubric-vs-Alpha-Score verdict card).

**Model/generation params**: Groq `llama-3.3-70b-versatile` (`ai_agent.py:12`), invoked via `groq_client.chat.completions.create(model=AI_MODEL, messages=[...], timeout=30.0)` for most calls (semantic query parsing uses `response_format={"type": "json_object"}`). Briefing generation on the split `/detail/{symbol}/briefing` endpoint has a **7-second synchronous generation timeout** if not already cached (per FUNCTIONAL_INVENTORY.md, confirmed by the split-endpoint design intent). All Groq call sites fall back to deterministic mock text if `GROQ_API_KEY` is unset or the call throws — scoring engines never depend on AI availability.

---

## 6. Caching Strategy

Two Redis clients/abstractions coexist: a low-level `RedisClient` singleton (`core/redis.py`, dual TCP/REST-mode) and a higher-level `CacheService` (`services/cache_service.py`) with its own TTL constants — plus centralized constants in `core/cache_ttl.py`. **These two TTL constant sets partially overlap/duplicate** (e.g. `cache_ttl.AI_ANALYSIS_TTL = 86400` vs `cache_service.TTL_AI_ANALYSIS = 86400` — same value, defined twice in two files) — see §9.

### Redis client modes (`core/redis.py`)
- **Local/TCP**: real `redis-py` client (`redis.from_url(...)`), skipped automatically if `REDIS_URL` points at `localhost` while running on Vercel (`VERCEL` env var check).
- **Production/REST**: Upstash REST API via a **shared module-level `httpx.AsyncClient`** (`max_connections=20, max_keepalive_connections=10`, 5s timeout) — explicitly built this way because "creating a new AsyncClient per request wastes connection setup time."
- Every operation (`get`, `setex`, `set_nx`, `delete`, `keys`, `expire`, `zincrby`, `zrevrange`) has both a TCP and REST implementation; `set_nx` (used for distributed locks) **fails open** on Redis errors — "if Redis is broken, allow ingestion" — meaning lock guarantees silently degrade to none under a Redis outage rather than blocking ingestion.

### Cache key structure & TTLs (from `core/cache_ttl.py` + inline usage)

| Domain | Key pattern | TTL |
|---|---|---|
| Stock price/live | `stocks_list:{sector}:{filters}:{sort}:{skip}:{limit}` | 300s (`STOCK_LIST_TTL`) |
| Stock fundamentals | (via optimized split endpoints) | 21,600s (`STOCK_MASTER_TTL`, 6h) or 86,400s on the `/metrics` split endpoint (`OPTIMIZED_METRICS_TTL`) |
| Stock price history | chart split endpoint | 86,400s (`OPTIMIZED_CHART_TTL`) for DB-backed 3y; live yfinance 5y/max not cached the same way |
| Stock meta (progressive) | `/meta` split endpoint | 86,400s (`OPTIMIZED_METADATA_TTL`) once `READY` |
| Market regime | — | 3,600s (`MARKET_REGIME_TTL`) |
| Sector analytics | — | 86,400s (`SECTOR_LAB_TTL`) |
| Sector averages (Alpha Score input) | `sector_averages:{sector.lower()}` | 86,400s (hardcoded in `stock_ingestion.py:741`) |
| Watchlist AI diagnostics | — | 1,800s (`WATCHLIST_ANALYTICS_TTL`) |
| Search results | `global_search:{type}:{query.lower()}` | 1,800s (`SEARCH_RESULT_TTL`) via `CacheService`, or `TTL_SEARCH=3600` — **two different TTLs for what looks like the same concept, defined in two files** |
| Stock search | — | 600s (`STOCK_SEARCH_TTL`) |
| News feed | `news_feed:{stream}:{category}` | 900s (`TTL_NEWS`, `CacheService`) — README says "10 min", code says 15 min (`NEWS_FEED_TTL=300` in `cache_ttl.py` also disagrees, at 5 min) — **three different TTL values for "news cache" across README/cache_ttl.py/cache_service.py** |
| AI briefing text | `ai_briefing:{symbol_or_scheme_upper}` | 86,400s (`TTL_AI_ANALYSIS`) or 604,800s (`OPTIMIZED_AI_TTL`, 7 days, on the newer split-endpoint path) |
| AI comparison verdict | `stock_compare_verdict:{s1}:{s2}` | 86,400s (`AI_COMPARISON_TTL`) |
| Fund detail (split) | `fund:{scheme_code}`, `fund_chart:{scheme_code}`, `fund_metrics:{scheme_code}`, `fund_ai:{scheme_code}` | 3,600s (`FUND_DETAIL_TTL`) |
| Fund list | — | 3,600s (`FUND_LIST_TTL`) |
| Dashboard stats | `dashboard:stats` | 300s (`TTL_DASHBOARD`) |
| Backtest summary | `backtest:summary:v3` | 86,400s (hardcoded in route, matches README's "24hr") |
| Backtest per-stock | — | 43,200s (README: 12h; not independently verified in a constants file — likely hardcoded at the route) |
| Ingestion progress | `ingest_progress:{symbol}` | 60–120s, written at each pipeline stage |
| Ingestion lock | `pipeline_lock:{symbol}` (QStash retries) / `ingesting:{symbol}` (legacy dynamic-ingest path) | 120s, `SETNX` |
| Cold-miss tracking | Redis sorted set, incremented via `zincrby` on real search misses | no TTL (persistent set, read via `zrevrange`) |
| DB migration flag | `alphamatrix:schema_v3_done` | 30 days |

### Invalidation
Mostly TTL-expiry (passive), not event-driven. Explicit invalidation exists for: `CacheService.invalidate_fund` (clears `fund_detail:{code}` + `dashboard:stats` together), `invalidate_stock`, `delete_news_feed` (used by `/news/analyze` presumably to force a refresh), and Redis key deletion when a fund's AI summary is regenerated (`redis_client.delete(f"fund_ai:{scheme_code}")` before re-queuing `generate_summary_background`). No cache-tag or dependency-graph invalidation system — each write path manually deletes the specific keys it knows are stale.

---

## 7. API Endpoints

Base path: `/api/v1`. Auth: `Depends(check_rate_limit)` (IP-based, in-process — see §9) gates almost every read endpoint; `Depends(get_current_user_email)` (Firebase JWT) gates watchlist routes only.

### Stocks (`api/v1/stocks.py`)
| Method | Path | Cache (server) | Notes |
|---|---|---|---|
| GET | `/stocks/search` | 10 min | symbol/name search |
| GET | `/stocks/list` | 5 min | filterable (sector/cagr/roe/de/pe), sortable, paginated (`skip`/`limit`) |
| GET | `/stocks/detail/{symbol}` | — | legacy monolithic (meta+metrics+chart+AI in one call) |
| GET | `/stocks/detail/{symbol}/meta` | 24h | progressive pipeline entry point, 202 while `DISCOVERING` |
| GET | `/stocks/detail/{symbol}/metrics` | 24h | fundamentals + Alpha Score breakdown |
| GET | `/stocks/detail/{symbol}/chart` | 1h | DB for `3y`, live yfinance for `5y`/`max` |
| GET | `/stocks/detail/{symbol}/briefing` | 24h–7d | synchronous generation w/ 7s timeout if uncached |
| GET | `/stocks/detail/{symbol}/news` | 15 min | yfinance news for symbol |
| GET | `/stocks/status/{symbol}` | — | ingestion progress, adaptive polling |
| POST | `/stocks/ingest/{symbol}` | — | advance pipeline one step (non-QStash fallback) |
| POST | `/api/v1/internal/ingest-background` | — | QStash webhook only, HMAC-verified |
| GET | `/stocks/market-regime` | 1h | BULLISH/BEARISH/SIDEWAYS + confidence |
| GET | `/stocks/sector/{sector}` | 30 min | sector score, peers, AI outlook |
| GET | `/stocks/compare?s1=&s2=` | AI verdict cached 24h | side-by-side + 6-factor breakdown both stocks |
| GET | `/stocks/backtest/summary` | 24h | aggregate accuracy, N+1 query pattern (see §9) |
| GET | `/stocks/backtest/{symbol}` | 12h | T+30/90/180/365 vs benchmark |
| GET | `/stocks/prewarm` | — | daily cron, cold-miss-aware |
| GET | `/stocks/cold-misses` | — | admin view of Redis sorted set |
| POST | `/stocks/chat` | — | body: chat message; auto-detects mentioned symbol |
| GET | `/stocks/watchlist` | — | **auth required** |
| POST | `/stocks/watchlist` | — | **auth required** |
| DELETE | `/stocks/watchlist/{symbol}` | — | **auth required** |
| GET | `/stocks/watchlist/analytics` | 30 min | **auth required**, AI portfolio diagnostics |
| POST | `/stocks/admin/prewarm` | — | legacy manual NIFTY 50 prewarm |

### Funds (`api/v1/funds.py`)
| Method | Path | Notes |
|---|---|---|
| GET | `/funds/search` | in-memory MFapi.in master list, disk-cached |
| GET | `/funds/` | paginated, filterable list |
| GET | `/funds/{scheme_code}` | full detail + NAV history; **self-healing**: creates skeleton row + `BackgroundTasks` ingest if missing |
| GET | `/funds/{scheme_code}/rating` | Fund Rating Engine v1 breakdown |
| GET | `/funds/category/{category}/peers` | sorted peer comparison |
| POST | `/funds/sync/{scheme_code}` | manual re-ingest |
| POST | `/funds/sync-all` | batch re-ingest, admin/heavy |

### News (`api/v1/news.py`)
`GET /news/india?category=`, `GET /news/global?category=` (10 min cache each), `GET /news/list` (legacy redirect), `POST /news/analyze` (per-article Groq impact analysis).

### Search / Auth / AI / System
- `GET /search/` — unified stock+fund search, 4s-timeout yfinance quick-check fallback for unlisted-ticker discovery.
- `POST /auth/register`, `POST /auth/login`, `GET /auth/me` — **legacy mock auth**, not the real Firebase flow.
- `POST /ai/semantic-query`, `POST /ai/chat` — NLP filter parsing + fund chat.
- `GET /`, `GET /health` (DB+Redis+AI status probe, never throws), `GET /api/v1/db-health` (row counts per table).

---

## 8. Data Ingestion

- **Stock fundamentals/prices**: **Yahoo Finance via `yfinance`**, NSE suffix `.NS` primary, `.BO` (BSE) fallback. Fetched through a `requests.Session` with a custom `TimeoutHTTPAdapter` enforcing a hard **4.0s** timeout, `hist`/`info`/`news` parallelized via a 3-worker `ThreadPoolExecutor` inside a thread (since yfinance is sync and the event loop must not block). Price history pulled at `3y` granularity, falling back to `2y`/`1y` if empty.
- **Mutual fund NAV data**: **MFAPI.in** (`workers/ingestion.py`) — free public Indian MF NAV API. Fund search uses an in-memory master list of scheme codes/names, disk-cached (`mf_master_list.json` present at repo root and inside `backend/`).
- **News**: RSS/XML from 6 sources — India: Economic Times Markets (credibility 0.82), Moneycontrol (0.80), Business Standard (0.80), Livemint (0.78); Global: Reuters Business (0.95), CNBC Finance (0.85); both streams fall back to yfinance news if all RSS sources fail. **Note**: `feedparser` is referenced in the README's tech-stack table but is **not actually a dependency or import anywhere** — the real implementation hand-parses RSS via `re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL)` in `_parse_rss_xml` (`news_aggregator.py:218`), a regex-based XML "parser" rather than a real XML/RSS library.
- **Refresh cadence**: stock prewarm cron runs daily at 21:00 UTC, pre-ingesting NIFTY 50 + Next 50 + popular mid-caps in chunks of 3, skipping already-`READY` rows, bounded to a 50s soft deadline (Vercel's 60s hard limit). Fund overnight sync (`workers/cron_jobs.py:run_overnight_sync`) re-ingests all funds with `force_recompute=True` — **no Vercel Cron entry currently wires this up** in `vercel.json` (only `/stocks/prewarm` and `/health` are scheduled) — see §9.
- **Cold-miss-driven universe growth**: real search misses for unseeded symbols increment a Redis sorted set (`zincrby`); `/stocks/cold-misses` surfaces the top entries so the prewarm universe can be data-drivenly expanded (currently a manual/observational step, not automatic).
- **Known external rate limits**: no explicit rate-limit handling/backoff visible for yfinance or MFAPI.in calls beyond the 4s client timeout — if Yahoo Finance throttles or blocks (a known real-world yfinance failure mode, hence the browser-spoofing `User-Agent` header and `curl_cffi` dependency for TLS fingerprint evasion), ingestion for that symbol simply fails and the stock is marked `FAILED`/left `DISCOVERING`.

---

## 9. Known Pain Points (from direct code reading — not speculative)

1. **In-process rate limiter breaks on serverless.** `check_rate_limit` (`core/security.py:35`) stores request timestamps in a **module-level Python dict** (`rate_limit_store: Dict[str, list]`). On Vercel, each invocation may run in a different/fresh function instance, so this rate limit is only effective within a single warm instance — it does not provide a real global rate limit in production. Contrast with the Redis-backed distributed locks used elsewhere in the same codebase (`pipeline_lock:{symbol}` etc.), which suggests the team is aware of this failure mode elsewhere but didn't apply the same fix here.

2. **Same in-process-state bug in fund ingestion dedup.** `ingesting_funds = set()` (`api/v1/funds.py:32`) is a module-level Python set used to prevent duplicate concurrent ingestion of the same fund — same class of bug as #1. The stock pipeline explicitly moved off in-memory locks to Redis (`pipeline_lock:{symbol}`) with an in-code comment explaining exactly why ("an in-memory set doesn't work across separate Vercel invocations"), but the fund pipeline was never migrated to match.

3. **Architectural split-brain between fund and stock background work.** Stocks moved to QStash specifically because "Vercel freezes the function the instant a response is sent, so fire-and-forget tasks would be killed" (comment in `stock_ingestion.py`). Funds still rely on FastAPI's `BackgroundTasks.add_task` (`funds.py:314,332,571`), which is exactly the pattern the stock pipeline's own comments say is unreliable on Vercel. Fund ingestion/AI-summary generation may be silently dropped on some fraction of requests in production.

4. **N+1 query pattern in `/stocks/backtest/summary`** (`api/v1/stocks.py:1925-1977`). Fetches up to 50 stock symbols, then issues **one separate `SELECT` per symbol** in a Python `for` loop to pull that symbol's full price history. Mitigated by a 24h cache, but every cache-cold hit (first request after TTL expiry, or after a deploy that flushes Redis) does up to 51 sequential round-trips to Neon.

5. **Duplicate/conflicting TTL constants.** `core/cache_ttl.py` and `services/cache_service.py` each define their own TTL constants for overlapping concepts (search results: 1800s vs 3600s; AI analysis: both define 86400s independently). News-feed TTL is documented three different ways: README says "10 min", `cache_ttl.NEWS_FEED_TTL` says 300s (5 min), `cache_service.TTL_NEWS` (the one actually used by `news.py`) says 900s (15 min). Tuning cache behavior requires knowing which of two files actually governs a given code path.

6. **README/code drift on the Alpha Score model.** README documents a 5-factor formula (fundamental 30% / valuation 20% / technical 20% / risk 15% / sector 15%) with distinct investor vs. trader (momentum-biased) verdict thresholds. The shipped `calculate_institutional_ratings` is a 6-factor model (25/15/20/15/15/10, quality split out) and **`investor_verdict` and `trader_verdict` are computed identically** — `map_verdict(final_score)` called twice with the same input (`stock_ingestion.py:1095-1096`). Anyone optimizing against the README's documented weights would be optimizing the wrong formula.

7. **`feedparser` and `curl_cffi` are declared/documented but effectively decorative or misdescribed.** README's tech table lists `feedparser` for RSS parsing; actual parsing is a regex over raw XML text (`_parse_rss_xml`). `curl_cffi` is in `requirements.txt` but no import was found in the modules reviewed — likely a residual dependency from an earlier yfinance TLS-fingerprint workaround. `openai` is also a declared dependency with no active call site — all AI goes through `groq`.

8. **No formal migration framework.** Schema changes are hand-written idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS` blocks inside `init_db()`, gated by a single Redis flag (`schema_v3_done`) that, once set, causes **all future migration blocks to be skipped** — including any added after that flag was set on a given environment, until the 30-day TTL lapses or the flag is manually cleared. Adding a new column requires either bumping the flag's key name or manually deleting it from Redis in each environment.

9. **Legacy/dead auth path still mounted.** `api/v1/auth.py`'s mock JWT system (accepts any password ≥6 chars, issues a fake bearer token) is still live at `/api/v1/auth/login|register|me`, separate from and inconsistent with the real Firebase-based `get_current_user_email` used everywhere else. Low risk (mock tokens are explicitly special-cased and rejected as "real" identity in `security.py`), but it's attack surface and confusion for anyone reading endpoint docs.

10. **Redis lock fail-open is a deliberate but real tradeoff.** `set_nx` in `core/redis.py` (used for `pipeline_lock`/`ingesting` locks) returns `True` (lock "acquired") on any Redis error or when Redis isn't configured — "fail open: if Redis is broken, allow ingestion." This avoids ingestion outright failing when Redis is down, but means the idempotency guarantee QStash retries depend on silently disappears exactly when Redis has problems — the failure mode is duplicate concurrent ingestion runs, not a hard error, which could be harder to notice.

11. **No pagination cap enforcement visible on `/stocks/list`** beyond the caller-supplied `limit` query param default of 50 — nothing in the route stops a client from requesting a very large `limit`, though in practice the dataset (~40 seeded + dynamically-ingested stocks) makes this low-risk today; will matter more as the ingested universe grows.

12. **Legacy vs. current endpoint duplication.** `/stocks/detail/{symbol}` (monolithic) is kept "for backward compatibility" alongside the 5 split endpoints (`meta`/`metrics`/`chart`/`briefing`/`news`) that do the same underlying work — any change to the Alpha Score/briefing logic must be kept in sync across both code paths, which is a source of exactly the kind of formula drift seen in #6.

13. **No load/latency test artifacts or logging pipeline found in-repo** (see §10) — optimization work will need to establish a baseline first; there is currently no historical data to compare against.

---

## 10. Performance Metrics

**No dedicated metrics/observability stack was found in the repository** — no APM integration (Sentry/Datadog/etc.), no structured logging sink beyond Python's stdlib `logging` to stdout (captured by Vercel's function logs), no load-test scripts, no cache-hit-rate dashboard.

What *does* exist, directly usable as a starting point for instrumentation:

- **Per-request timing header**: the pure-ASGI middleware in `main.py` (`combined_middleware`, lines 58–89) computes wall-clock duration per request and sets `X-Response-Time: {ms}ms` on every response, plus logs `"%s %s  %dms  status=%d"` for every `/api/` request. This is the closest thing to existing latency data — it's in Vercel's function logs, not aggregated anywhere queryable.
- **Cache hit/miss signaling**: `/stocks/list` sets `X-Cache: hit|miss` response header (`api/v1/stocks.py:441,499`) — same ad hoc pattern, not present on most other cached endpoints, not aggregated.
- **`GET /health`**: checks DB connectivity (`SELECT 1`), Redis connectivity (a `GET`), and Groq configuration status — a synthetic uptime probe (pinged daily by the `/health` Vercel Cron) rather than a performance metric.
- **`GET /api/v1/db-health`**: returns row counts for `users`/`fund_masters`/`stock_masters` — a data-volume snapshot, not a performance one.
- **Cache-Control headers**: `main.py` sets `Cache-Control: public, max-age=60, stale-while-revalidate=30` on GET responses for a fixed prefix allowlist (`/stocks/list`, `/stocks/detail/`, `/stocks/sector/`, `/stocks/market-regime`, `/funds/`, `/news/`, `/search`) — enables Vercel edge/browser caching on top of the Redis layer, but there's no visibility into how often that edge cache is actually hit.

**Recommendation for whoever picks this up for optimization**: before changing anything, add structured request logging (path, cache hit/miss, DB query count, Groq call latency) to a queryable sink, since right now every optimization claim would have to be validated against Vercel's raw text logs with no baseline to diff against.
