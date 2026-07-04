# AlphaMatrix Functional Inventory

> Last verified against backend `app/` and `frontend/src/` source (July 2026). Endpoint paths, models, and services below are read directly from code, not aspirational.

## Auth & User Management
| Feature | Domain | Endpoint/Route | Description |
|---------|--------|----------------|-------------|
| Email/Password Login | Auth | `POST /api/v1/auth/login` | Mock login — accepts any password ≥6 chars, issues a fake bearer token. Legacy/demo path. |
| Email/Password Signup | Auth | `POST /api/v1/auth/signup` | Mock registration, same fake-token issuance. |
| Get Current User (mock) | Auth | `GET /api/v1/auth/me` | Returns user info decoded from the mock bearer token. |
| Firebase Auth (real) | Auth | `services/firebase.js` + `core/security.py` | Actual production auth: Firebase email/password + Google sign-in on the frontend; backend verifies Firebase ID tokens against Google's public keys in `get_current_user_email` (used by watchlist/settings, not the mock `auth.py` tokens). |
| Protected Routes | Auth | `ProtectedRoute` component | Wraps `/stocks/watchlist` and `/settings`; redirects to `/login` if `useAuth()` has no user. |
| Session Token Storage | Auth | `localStorage` | Firebase token + `alphamatrix_user_email`. |
| Theme Toggle | Settings | Frontend only | Dark/Light mode persisted to localStorage. |
| Logout | Auth | Settings page | Clears session, navigates to `/login`. |

## Stocks Domain (Backend: `app/api/v1/stocks.py`, `internal.py`)

AlphaMatrix ingests stocks **progressively** rather than in one blocking request. A stock row moves through a state machine: `DISCOVERING → DISCOVERED → INGESTING → ANALYTICS_RUNNING → READY` (or `FAILED`). See "Progressive Discovery & QStash Pipeline" below for the full mechanics.

| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| Stock Search | `GET /api/v1/stocks/search` | Symbol/name search against seeded stocks, Redis-cached 10 min. |
| Stock List | `GET /api/v1/stocks/list` | Paginated, filterable (sector/CAGR/ROE/D-E/PE), sortable grid. Redis-cached 5 min. |
| Stock Detail (legacy) | `GET /api/v1/stocks/detail/{symbol}` | Monolithic detail (meta+metrics+chart+AI) in one call; kept for backward compatibility. |
| Stock Meta (split) | `GET /api/v1/stocks/detail/{symbol}/meta` | Entry point of the progressive pipeline — returns immediately (<300ms) with a `DISCOVERING` placeholder while ingestion runs in the background, or full data if already `READY` (24h cache). |
| Stock Metrics (split) | `GET /api/v1/stocks/detail/{symbol}/metrics` | Fundamentals + Alpha Score factor breakdown, 24h cache. |
| Stock Chart (split) | `GET /api/v1/stocks/detail/{symbol}/chart` | Price history — DB for `3y`, live yfinance for `5y`/`max`. 1hr cache. |
| Stock Briefing (split) | `GET /api/v1/stocks/detail/{symbol}/briefing` | AI equity briefing; generated synchronously (7s timeout) if not yet cached. |
| Stock News (split) | `GET /api/v1/stocks/detail/{symbol}/news` | Recent yfinance news for the symbol, 15 min cache. |
| Ingestion Status | `GET /api/v1/stocks/status/{symbol}` | Adaptive polling endpoint (1.5s→3s) returning `available_sections`/`pending_sections`/`progress`/`stage_message` so the UI can render sections as they become ready. |
| Advance Ingestion | `POST /api/v1/stocks/ingest/{symbol}` | Frontend-driven fallback that runs exactly the next pipeline step (used when QStash isn't configured, e.g. Vercel Hobby). |
| Stock AI Chat | `POST /api/v1/stocks/chat` | Context-aware chat, auto-detects the symbol mentioned in the message. |
| Watchlist List | `GET /api/v1/stocks/watchlist` | User's watchlisted stocks (auth required). |
| Watchlist Add | `POST /api/v1/stocks/watchlist` | Add stock to watchlist (auth required). |
| Watchlist Remove | `DELETE /api/v1/stocks/watchlist/{symbol}` | Remove from watchlist (auth required). |
| Watchlist Analytics | `GET /api/v1/stocks/watchlist/analytics` | AI diagnostics: health score, strongest/weakest, sector concentration, risk. |
| Sector Details | `GET /api/v1/stocks/sector/{sector}` | Sector score, growth drivers/risks, top stocks, AI outlook. |
| Stock Comparison | `GET /api/v1/stocks/compare` | Side-by-side metrics, 6-factor Alpha Score breakdown, AI verdict. |
| Market Regime | `GET /api/v1/stocks/market-regime` | AI market regime diagnosis (bullish/bearish/neutral) with confidence. |
| Backtest Summary | `GET /api/v1/stocks/backtest/summary` | Aggregate verdict-accuracy stats across the universe. |
| Backtest Per-Stock | `GET /api/v1/stocks/backtest/{symbol}` | T+30/90/180/365 return vs NIFTY 50 for one symbol. |
| Prewarm (cron) | `GET /api/v1/stocks/prewarm` | Daily Vercel Cron job — pre-ingests NIFTY 50 + Next 50 + popular mid-caps in chunks of 3, skipping `READY` rows, respecting a 50s soft deadline. |
| Cold Misses | `GET /api/v1/stocks/cold-misses` | Admin view of the Redis sorted set tracking most-searched not-yet-seeded symbols, used to grow the prewarm universe data-drivenly. |
| Admin Prewarm (legacy) | `POST /api/v1/stocks/admin/prewarm` | Older manual NIFTY 50 prewarm trigger. |

### Progressive Discovery & QStash Pipeline

- **Trigger**: Navigating to an unseeded/incomplete symbol calls `GET /stocks/detail/{symbol}/meta`. If QStash is configured (`QSTASH_TOKEN` + `QSTASH_CURRENT_SIGNING_KEY` + `BACKEND_URL`), the endpoint stubs a `DISCOVERING` row, writes an initial Redis progress key, `await`s `publish_ingestion_job(symbol)` (synchronously — Vercel freezes the function the instant a response is sent, so fire-and-forget tasks would be killed), and returns 202 immediately.
- **QStash callback**: QStash POSTs to `POST /api/v1/internal/ingest-background`, verified via `Upstash-Signature` JWT (HMAC-SHA256 over `header.payload` using `QSTASH_CURRENT_SIGNING_KEY`, falling back to `QSTASH_NEXT_SIGNING_KEY` during key rotation; body hash claim checked in both padded/unpadded base64url forms).
- **Pipeline stages**, each committing DB state and a Redis `ingest_progress:{symbol}` blob:
  1. `quick_discover_stock` — Stage 0, yfinance `.info` only (name/sector/ISIN/market cap/PE/PB/ROE/D-E/current price), status → `DISCOVERED`.
  2. `ingest_step1_history` — 3y OHLC download into `StockPriceHistory`, status → `INGESTING`.
  3. `ingest_step2_analytics` — full Alpha Score model (`calculate_institutional_ratings`), status → `ANALYTICS_RUNNING`.
  4. `ingest_step3_briefing` — Groq AI equity briefing + bull/bear/verdict parsing, status → `READY`.
- A Redis `pipeline_lock:{symbol}` (`SETNX`, 120s TTL) makes QStash retries idempotent.
- **Fallback (no QStash / Vercel Hobby)**: `/meta` runs `quick_discover_stock` inline, and the frontend drives the remaining steps one at a time via `POST /stocks/ingest/{symbol}` (`advanceIngestionPipeline`), each call bounded to fit Hobby's 10s function limit.
- **Frontend polling**: `useStockMeta` fires once (no polling); `useStockStatus` is the sole polling hook, stopping once `status` is `READY`/`FAILED`/`NOT_FOUND`. `StockDetail.jsx` renders chart/metrics/briefing/news incrementally based on `available_sections`.

## Mutual Funds Domain (Backend: `app/api/v1/funds.py`)
| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| Fund Search | `GET /api/v1/funds/search` | Search all Indian MF schemes (in-memory MFapi.in master list, disk-cached). |
| Fund List | `GET /api/v1/funds/` | Paginated list with category/CAGR/expense/Sharpe/PE filters. |
| Fund Detail | `GET /api/v1/funds/{scheme_code}` | Full details + NAV history; triggers on-demand ingestion + AI summary if stale/missing. |
| Fund Rating Breakdown | `GET /api/v1/funds/{scheme_code}/rating` | Fund Rating Engine v1 factor breakdown. |
| Category Peers | `GET /api/v1/funds/category/{category}/peers` | Sorted peer comparison within a category. |
| Fund Sync | `POST /api/v1/funds/sync/{scheme_code}` | Manual re-ingest + recompute metrics for one fund. |
| Fund Sync All | `POST /api/v1/funds/sync-all` | Batch re-ingest all funds (admin/heavy). |

## AI Domain (Backend: `app/services/ai_agent.py`, exposed via `api/v1/ai.py` + inline in `stocks.py`/`funds.py`)
| Feature | API Endpoint / Function | Model | Fallback |
|---------|------------------------|-------|----------|
| Semantic Query | `POST /api/v1/ai/semantic-query` | `groq llama-3.3-70b-versatile` | Rule-based mock parser |
| Fund AI Chat | `POST /api/v1/ai/chat` | Groq | Mock chat response |
| Stock AI Chat | `POST /api/v1/stocks/chat` | Groq | Mock stock chat |
| Stock AI Briefing | `generate_stock_briefing` (pipeline stage 3 / on-demand) | Groq, grounded by `services/briefing_intelligence.py`'s deterministic rubric | Structured mock briefing |
| Fund AI Summary | `generate_fund_analysis` (background) | Groq | Mock bullet analysis |
| Sector Outlook | `generate_sector_outlook` | Groq | Mock sector outlook |
| Stock Comparison | `generate_stock_comparison` | Groq | Mock comparison |
| Watchlist Analytics | `generate_watchlist_analytics` | Groq | Mock diagnostics |
| Market Regime | `get_market_regime_diagnostics` | Groq | Mock regime analysis |
| News Impact Analysis | `POST /api/v1/news/analyze` | Groq | Keyword-based mock |

All Groq calls gracefully fall back to deterministic mock responses when `GROQ_API_KEY` is unset — scoring engines never depend on AI availability.

## Search Domain
| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| Global Search | `GET /api/v1/search/` | Unified search across stocks (FTS5/ILIKE+trigram) and funds; falls back to a 4s-timeout yfinance quick-check that surfaces unlisted tickers as a `discover: true` suggestion. |
| Stock Search | `GET /api/v1/stocks/search` | Dedicated stock search. |
| Fund Search | `GET /api/v1/funds/search` | Dedicated fund search from the in-memory master list. |

## News Domain (Backend: `app/services/news_aggregator.py`, `api/v1/news.py`)
| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| India News | `GET /api/v1/news/india` | ET Markets + Moneycontrol + Business Standard + Livemint RSS, yfinance fallback. 10 min cache. |
| Global News | `GET /api/v1/news/global` | Reuters + CNBC RSS, yfinance fallback. 10 min cache. |
| News List (legacy) | `GET /api/v1/news/list` | Redirects to `/india` or `/global` by `stream` param. |
| News Analyze | `POST /api/v1/news/analyze` | Groq impact-direction/sector/company analysis for one headline. |
| Multi-Source Dedup | `news_aggregator.py` | Jaccard similarity (threshold 0.65) merges near-identical headlines across sources. |
| Event Classification | `news_aggregator.py` | Regex-based POSITIVE/NEGATIVE event tagging (order wins, earnings beats/misses, downgrades, etc). |

## System Health
| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| Root Health | `GET /` | API welcome + status. |
| Simple Health | `GET /health` | Basic ok status. |
| DB Health | `GET /api/v1/db-health` | DB connection + table row counts. |

## Frontend Pages
| Page | Route | Key Features |
|------|-------|--------------|
| Home (Funds) | `/`, `/funds` | Hero, stats cards, asset-class buttons, risk scatterplot, `GlobalSearch`, `FloatingChatAssistant`. |
| Explorer (Funds) | `/explorer`, `/funds/explorer` | NLP semantic query bar, standard filters, sortable data table. |
| Fund Detail | `/detail/:schemeCode`, `/funds/detail/:schemeCode` | Metric cards, NAV chart, AI summary, sync button, contextual chat. |
| Stock Home | `/stocks` | Hero, stats, market regime, sector buttons, risk scatterplot, `GlobalSearch`, `FloatingChatAssistant`. |
| Stock Explorer | `/stocks/explorer` | Sector/CAGR/ROE/D-E/PE filters, sortable table. |
| Stock Detail | `/stocks/detail/:symbol` | Progressive-discovery UX: renders meta → metrics → chart → briefing → news as each becomes ready; watchlist toggle, backtest panel, contextual chat. |
| Stock Sector | `/stocks/sector/:sectorName` | Sector score, growth drivers/risks, AI outlook, top stocks list. |
| Stock Compare | `/stocks/compare` | 2-stock picker, side-by-side metrics, 6-factor Alpha comparison, AI verdict, comparison chart. |
| Stock Watchlist | `/stocks/watchlist` | Saved positions + AI diagnostics panel (auth required). |
| News | `/news` | India/Global tabs, category filters, AI analysis drawer. |
| Login / Signup | `/login`, `/signup` | Firebase email/password + Google auth. |
| Settings | `/settings` | Profile, theme toggle, logout (auth required). |

## Frontend Components
| Component | File | Description |
|-----------|------|-------------|
| AlphaMatrixLogo | `components/AlphaMatrixLogo.jsx` | Animated SVG brand logo. |
| GlobalSearch | `components/GlobalSearch.jsx` | Unified stock+fund search bar with debounce + autocomplete dropdown. |
| StockSearchPicker | `components/StockSearchPicker.jsx` | Stock picker used in Compare mode. |
| FloatingChatAssistant | `components/FloatingChatAssistant.jsx` | Shared floating AI chat drawer used on `Home`/`StockHome`; mobile-aware full-screen bottom sheet below 640px. |
| InteractiveChart | `components/charts/InteractiveChart.jsx` | Recharts area chart for NAV/price history; uses `useIsMobile` to adapt density on small screens. |
| StockRiskScatterplot | `components/charts/StockRiskScatterplot.jsx` | Beta vs CAGR scatter for stocks. |
| RiskScatterplot | `components/charts/RiskScatterplot.jsx` | Sharpe vs CAGR scatter for funds. |
| StockComparisonChart | `components/charts/StockComparisonChart.jsx` | Dual-line comparison chart, mobile-aware via `useIsMobile`. |
| AnalystResponseCard | `components/AnalystResponseCard.jsx` | AI chat/briefing message renderer. |
| BriefingReport | `components/BriefingReport.jsx` | Stock Detail's AI Equity Briefing panel — parses `[FACT:]`/`[DATA]`/`[ANALYTICAL]`/`[MACRO CONTEXT]` tags into footnotes/labeled paragraphs, renders the consolidated rubric-vs-Alpha-Score verdict card and divergence explanation, bull/base/bear case cards, and risk factor cards. |
| StockLogo / FundLogo | `components/StockLogo.jsx`, `components/FundLogo.jsx` | Auto-generated color-coded avatars. |
| Skeletons | `components/skeletons/Skeletons.jsx` | `CardSkeleton`, `CardGridSkeleton`, `NewsCardSkeleton` loading placeholders. |

## Frontend Hooks
| Hook | File | Description |
|------|------|-------------|
| useQueries | `hooks/useQueries.js` | Modern React Query layer: split stock endpoints, `useStockStatus` adaptive polling, `advanceIngestionPipeline`, fund/news/backtest hooks, per-domain `staleTime` tuning. |
| useIsMobile | `hooks/useIsMobile.js` | Reactive `matchMedia('(max-width: 639px)')` hook; drives responsive chart rendering. |
| useSearchCache | `hooks/useSearchCache.js` | Client-side LRU cache (100 entries) in front of the search API. |
| useAuth | `hooks/useAuth.js` | Wrapper around Firebase `AuthContext`. |
| useDebounce | `hooks/useDebounce.js` | Generic debounce for search inputs. |
| useFunds / useStocks | `hooks/useFunds.js`, `hooks/useStocks.js` | Older imperative `useState`/`useCallback` fetch hooks (pre-React-Query, still used in a few places). |

## Data Ingestion
| Feature | File | Description |
|---------|------|-------------|
| Progressive Stock Pipeline | `workers/stock_ingestion.py` | `quick_discover_stock` / `ingest_step1_history` / `ingest_step2_analytics` / `ingest_step3_briefing` — see pipeline section above. |
| Alpha Score Model | `workers/stock_ingestion.py:calculate_institutional_ratings` | 5-factor deterministic composite scoring (fundamental/valuation/technical/risk/sector-relative); drives `investor_verdict`/`trader_verdict`. |
| Briefing Grounding Rubric | `services/briefing_intelligence.py:score_verdict` | Independent 5-pillar rubric (valuation/quality/momentum/risk/technical) anchoring the AI briefing's verdict + citations/labels/anomaly flags; `compute_divergence_reason` explains any disagreement with the Alpha Score model (pillar-level, not just a flag) and is stored as `divergence_reason` in the briefing's `meta`. |
| QStash Publish | `services/qstash.py:publish_ingestion_job` | Publishes an ingestion job to Upstash QStash for async background execution. |
| QStash Verify | `services/qstash.py:verify_qstash_signature` | HMAC-SHA256 JWT verification of inbound QStash webhooks. |
| QStash Webhook Handler | `api/v1/internal.py:ingest_background` | Runs all 4 pipeline stages sequentially under a Redis lock. |
| Fund Ingestion | `workers/ingestion.py:ingest_fund` | Fetches NAV from mfapi.in, computes CAGR/Sharpe/Sortino/Alpha/Beta via Fund Rating Engine, stores in DB. |
| Fund Seeding | Bootstrap on startup | Seeds initial fund universe from MFapi.in. |
| Overnight Fund Sync | `workers/cron_jobs.py:run_overnight_sync` | Re-ingests all `FundMaster` rows with `force_recompute=True`. |
| Stock Prewarm (cron) | `api/v1/stocks.py` `/prewarm` | Daily Vercel Cron pre-ingesting the popular stock universe; cold-miss-aware. |

## Infrastructure
| Component | Description |
|-----------|--------------|
| Vercel Deployment | `vercel_app.py` entrypoint; `vercel.json` defines the daily `/prewarm` cron and function `maxDuration`. |
| QStash (Upstash) | Async background job queue driving the stock ingestion pipeline outside the request/response cycle, working around Vercel's short function timeouts. |
| Combined ASGI Middleware | `main.py` — single pure-ASGI middleware (not `BaseHTTPMiddleware`, which buffers/breaks on Vercel) doing global exception → JSON 500, `Cache-Control` headers on whitelisted GETs, and `X-Response-Time` timing. |
| GZip Middleware | Compresses JSON responses > 1KB. |
| Rate Limiting | `check_rate_limit` — Redis sliding-window dependency on search/list endpoints. |
| Redis / Upstash | Dual-mode client (`core/redis.py`) — real TCP redis-py locally, Upstash REST API on Vercel. Used for search/detail/news caching, ingestion progress, distributed locks, cold-miss tracking. |
| SQLite (local) / PostgreSQL (Neon) | Dual-DB via async SQLAlchemy (`core/database.py`), with a Redis-backed flag to skip re-running migrations on every serverless cold start. |
| FTS5 (SQLite) / ILIKE+Trigram (Postgres) | Search index backends for stock/fund text search. |

## Backend Models
| Model | Table | Key Fields |
|-------|-------|------------|
| StockMaster | `stock_masters` | symbol (PK), company_name, isin, sector, industry, market_cap, pe/pb_ratio, roe, debt_equity, dividend_yield, beta, cagr_1y/3y/5y, alpha_score + sub-scores (fundamental/valuation/technical/risk/sector_relative/quality/event/confidence), investor_verdict, trader_verdict, trend_structure, bull_case/bear_case/verdict_rationale/ai_summary, `ingestion_status`, current_price, exchange |
| StockPriceHistory | `stock_price_histories` | symbol (FK), date, close |
| WatchlistItem | `watchlist_items` | email, symbol (FK), unique(email, symbol) |
| FundMaster | `fund_masters` | scheme_code (PK), fund_name, category, cagr_1y/3y/5y, sharpe_ratio, sortino_ratio, alpha, beta, fund_score, fund_verdict, expense_ratio, aum, category_rank/category_count, ai_summary/bull_case/bear_case/fund_rationale |
| NAVHistory | `nav_histories` | scheme_code (FK), date, nav |
| User | `users` | id, email, hashed_password, is_active — largely vestigial; real identity is Firebase-based |

## Upcoming / Placeholder Features
| Feature | Status | Location |
|---------|--------|----------|
| Portfolio Tracker | [Soon] | Explore dropdown, profile dropdown |
| Saved Research | [Soon] | Explore dropdown, profile dropdown, settings |
| Saved Comparisons | [Soon] | Profile dropdown, settings |
| Notification Prefs | [Coming Soon] | Settings page |
| Plan Type / Subscription | [Coming Soon] | Settings page |
