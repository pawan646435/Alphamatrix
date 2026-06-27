# AlphaMatrix Functional Inventory

## Auth & User Management
| Feature | Domain | Endpoint/Route | Description |
|---------|--------|----------------|-------------|
| Email/Password Login | Auth | `POST /api/v1/auth/login` | Authenticate with email+password; returns mock JWT |
| Email/Password Signup | Auth | `POST /api/v1/auth/signup` | Register new user with email+password |
| Get Current User | Auth | `GET /api/v1/auth/me` | Returns current user info from token |
| Google Auth Login | Auth | Frontend only | Firebase Google sign-in with mock fallback |
| Firebase Auth | Auth | `useAuth` hook | Full Firebase auth wrapper with dev mock fallback |
| Protected Routes | Auth | `ProtectedRoute` component | Wraps watchlist/settings; redirects to /login |
| Session Token Storage | Auth | `localStorage` | Stores `alphamatrix_token` and `alphamatrix_user_email` |
| Profile Update | Settings | Frontend only | Edit display name |
| Theme Toggle | Settings | Frontend only | Dark/Light mode persisted to localStorage |
| Logout | Auth | Frontend + `handleLogout` | Clears token, navigates to /login |

## Stocks Domain (Backend: `app/api/v1/stocks.py`)
| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| Stock Search | `GET /api/v1/stocks/search?query=` | Search by symbol or company name (cached 10min) |
| Stock List | `GET /api/v1/stocks/list` | Paginated list with sector/CAGR/ROE/Debt/PE filters, sortable |
| Stock Detail | `GET /api/v1/stocks/detail/{symbol}` | Full metadata, price history, alpha breakdown; triggers AI briefing + dynamic ingestion |
| Stock AI Chat | `POST /api/v1/stocks/chat` | Chat about stocks with context-aware AI |
| Watchlist List | `GET /api/v1/stocks/watchlist` | Get user's watchlisted stocks |
| Watchlist Add | `POST /api/v1/stocks/watchlist?symbol=` | Add stock to watchlist |
| Watchlist Remove | `DELETE /api/v1/stocks/watchlist/{symbol}` | Remove stock from watchlist |
| Watchlist Analytics | `GET /api/v1/stocks/watchlist/analytics` | AI diagnostics: health score, strongest/weakest, risk concentration, sector exposure |
| Sector Details | `GET /api/v1/stocks/sector/{sector}` | Sector score, growth drivers, risks, top stocks, AI outlook |
| Stock Comparison | `GET /api/v1/stocks/compare?s1=&s2=` | Side-by-side metrics, 6-factor alpha breakdown, AI verdict |
| Market Regime | `GET /api/v1/stocks/market-regime` | AI market regime diagnosis (RISK ON/OFF/NEUTRAL) with confidence |
| Stock Status | `GET /api/v1/stocks/status/{symbol}` | Poll whether dynamic ingestion is ready |

## Mutual Funds Domain (Backend: `app/api/v1/funds.py`)
| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| Fund Search | `GET /api/v1/funds/search?query=` | Search all Indian MF schemes (in-memory MFapi cache) |
| Fund List | `GET /api/v1/funds/` | Paginated list with category/CAGR/expense/sharpe/PE filters |
| Fund Detail | `GET /api/v1/funds/{scheme_code}` | Full details + NAV history; triggers on-demand ingestion + AI summary |
| Fund Sync | `POST /api/v1/funds/sync/{scheme_code}` | Manual re-ingest and recompute metrics |
| Fund Sync All | `POST /api/v1/funds/sync-all` | Trigger overnight sync for all funds in background |
| In-Memory Fund Cache | API startup | Loads/caches all 10K+ Indian MF schemes from MFapi to disk |

## AI Domain (Backend: `app/api/v1/ai.py`)
| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| Semantic Query | `POST /api/v1/ai/semantic-query` | NLP → DB filters for mutual funds; Groq-parsed |
| AI Chat (Funds) | `POST /api/v1/ai/chat` | Chat about funds with context injection |
| Stock AI Briefing | Background | Generates multi-section equity briefing: Executive Summary, Investment Thesis, Performance, Fundamental, Sector, Macro, Geopolitical, Bull/Base/Bear cases, Risk Factors, Final Verdict, Confidence Score, Research Timeline |
| Fund AI Summary | Background | Generates bullet-point analysis with trajectory, macro overlay, recommendation stance |
| AI Sector Outlook | On-demand | Growth drivers, risks, score, narrative outlook |
| AI Watchlist Diagnostics | On-demand | Health score, aggregate summary, strongest/weakest, risk concentration, sector exposure |
| AI Stock Comparison | On-demand | Structured comparative verdict with sections |
| AI Market Regime | On-demand | RISK ON/OFF/NEUTRAL with confidence and explanation |
| AI News Analysis | On-demand | Impact direction, affected sectors, key companies, summary |

## Search Domain
| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| Global Search | `GET /api/v1/search?query=&type=` | Unified search across stocks (FTS5/ILIKE) and funds; Yahoo Finance fallback for unknown tickers |
| Stock Search | `GET /api/v1/stocks/search` | Dedicated stock search by symbol/name |
| Fund Search | `GET /api/v1/funds/search` | Dedicated fund search from in-memory master list |

## News Domain
| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| News List | `GET /api/v1/news/list?stream=&category=` | Live financial news from Yahoo Finance (India/Global, 6 categories) |
| News Analyze | `POST /api/v1/news/analyze` | AI impact analysis on individual articles |
| Impact Classification | Client-side | Keywords-based HIGH/MEDIUM/LOW impact tagging |
| News Caching | `CacheService` | 5-min TTL per stream+category combo |

## System Health
| Feature | API Endpoint | Description |
|---------|--------------|-------------|
| Root Health | `GET /` | API welcome + status |
| Simple Health | `GET /health` | Basic ok status |
| DB Health | `GET /api/v1/db-health` | DB connection + table row counts |

## Frontend Pages
| Page | Route | Key Features |
|------|-------|--------------|
| Home (Funds) | `/`, `/funds` | Hero, stats cards, 5 asset class buttons → explorer, scatterplot, floating AI chat |
| Explorer (Funds) | `/explorer`, `/funds/explorer` | NLP semantic query bar, standard filters, sortable data table |
| Fund Detail | `/detail/:schemeCode`, `/funds/detail/:schemeCode` | Meta, 9 metric cards, interactive NAV chart, AI briefing, data source links, contextual chat, investment stance verdict |
| Stock Home | `/stocks` | Hero, stats (count, avg CAGR, peak alpha, market regime), 6 sector buttons, risk scatterplot, floating AI chat |
| Stock Explorer | `/stocks/explorer` | 5 filters (sector, min CAGR, min ROE, max D/E, max PE), sortable 9-column table |
| Stock Detail | `/stocks/detail/:symbol` | Dynamic discovery UX, meta + sector tags, alpha score breakdown, 9 metric cards, price chart, research timeline, full AI briefing (9 sections), investment verdict card, contextual chat |
| Stock Sector | `/stocks/sector/:sectorName` | Sector score, growth drivers, risks, AI outlook, top stocks list |
| Stock Compare | `/stocks/compare` | 2-stock search pickers, swap, progress telemetry, side-by-side metrics table (6 categories), 6-factor alpha comparison bars, AI verdict report, comparison price chart |
| Stock Watchlist | `/stocks/watchlist` | Saved positions list, AI diagnostics panel (health score, strongest, weakest, risk, sector) |
| News | `/news` | India/Global tabs, 6 category filters, article cards with impact badges, AI analysis side drawer |
| Login | `/login` | Email/password form, Google auth button |
| Signup | `/signup` | Email/password + confirm, Google auth |
| Settings | `/settings` | Profile name edit, dark/light theme, session info, logout |

## Frontend Components
| Component | File | Description |
|-----------|------|-------------|
| AlphaMatrixLogo | `components/AlphaMatrixLogo.jsx` | Animated SVG logo with glow |
| GlobalSearch | `components/GlobalSearch.jsx` | Unified search with debounce + dropdown results |
| StockSearchPicker | `components/StockSearchPicker.jsx` | Stock search for compare mode |
| InteractiveChart | `components/charts/InteractiveChart.jsx` | Recharts AreaChart for NAV/price history |
| StockRiskScatterplot | `components/charts/StockRiskScatterplot.jsx` | Recharts ScatterChart: Beta vs CAGR |
| RiskScatterplot | `components/charts/RiskScatterplot.jsx` | Sharpe vs CAGR scatter for funds |
| StockComparisonChart | `components/charts/StockComparisonChart.jsx` | Dual-line comparison chart |
| AnalystResponseCard | `components/AnalystResponseCard.jsx` | Chat message bubble with markdown |
| StockLogo | `components/StockLogo.jsx` | Auto-generated color-coded stock avatar |
| FundLogo | `components/FundLogo.jsx` | Auto-generated color-coded fund avatar |
| CardGridSkeleton | `components/skeletons/Skeletons.jsx` | Loading skeleton grid |
| CardSkeleton | `components/skeletons/Skeletons.jsx` | Individual loading skeleton |
| NewsCardSkeleton | `components/skeletons/Skeletons.jsx` | News-specific loading skeleton |

## Data Ingestion
| Feature | File | Description |
|---------|------|-------------|
| Fund Ingestion | `workers/ingestion.py` | Fetches NAV from MFapi, computes CAGR/Sharpe/Sortino/Alpha/Beta, stores in DB |
| Stock Seeding | `workers/stock_ingestion.py` | Seeds 50+ Indian stocks with synthetic price history, computes metrics, populates search indices |
| Dynamic Stock Ingestion | `workers/stock_ingestion.py:dynamic_ingest_stock` | On-demand yfinance fetch for any NSE stock |
| Overnight Sync | `workers/cron_jobs.py` | Batch re-ingest all funds, recompute metrics |
| AI Summary Gen | `workers/ingestion.py:generate_summary_background` | Background Groq-generated fund analysis |
| AI Stock Briefing | `api/v1/stocks.py:generate_briefing_background` | Background Groq-generated equity briefing with live yfinance data |

## Infrastructure
| Component | Description |
|-----------|-------------|
| Vercel Deployment | `vercel_app.py` for serverless functions |
| GZip Middleware | Compresses JSON > 1KB |
| Cache-Control Middleware | Sets `Cache-Control` headers for cacheable GET endpoints |
| Timing Middleware | Captures request timing |
| Rate Limiting | `check_rate_limit` dependency on search/list endpoints |
| Redis Cache | Optional, graceful fallback; used for search, detail, news, analytics |
| SQLite (local) / PostgreSQL (Neon) | Dual-DB via SQLAlchemy async |
| FTS5 (SQLite) / ILIKE+Trigram (PG) | Search index backends |

## Backend Models
| Model | Table | Key Fields |
|-------|-------|------------|
| FundMaster | `fund_masters` | scheme_code, fund_name, category, cagr_1y/3y/5y, sharpe_ratio, sortino_ratio, alpha, beta, pe_ratio, expense_ratio, ai_summary |
| NAVHistory | `nav_histories` | scheme_code, date, nav |
| StockMaster | `stock_masters` | symbol, company_name, isin, sector, industry, market_cap, pe/pb_ratio, roe, debt_equity, dividend_yield, beta, alpha_score, cagr_1y/3y/5y, ai_summary |
| StockPriceHistory | `stock_price_histories` | symbol, date, close |
| WatchlistItem | `watchlist_items` | email, symbol |
| User | `users` | id, email, hashed_password, is_active |

## AI Services
| Service | Function | Model | Fallback |
|---------|----------|-------|----------|
| Semantic Query Parser | `parse_semantic_query` | Groq llama-3.3-70b-versatile | Rule-based mock parser |
| Fund AI Chat | `run_ai_chat` | Groq llama-3.3-70b-versatile | Mock chat response |
| Stock AI Chat | `run_stock_chat` | Groq llama-3.3-70b-versatile | Mock stock chat |
| Stock Briefing | `generate_stock_briefing` | Groq llama-3.3-70b-versatile | Structured mock briefing |
| Fund Analysis | `generate_fund_analysis` | Groq llama-3.3-70b-versatile | Mock bullet analysis |
| Sector Outlook | `generate_sector_outlook` | Groq llama-3.3-70b-versatile | Mock sector outlook |
| Stock Comparison | `generate_stock_comparison` | Groq llama-3.3-70b-versatile | Mock comparison |
| Watchlist Analytics | `generate_watchlist_analytics` | Groq llama-3.3-70b-versatile | Mock diagnostics |
| Market Regime | `get_market_regime_diagnostics` | Groq llama-3.3-70b-versatile | Mock regime analysis |

## Upcoming / Placeholder Features
| Feature | Status | Location |
|---------|--------|----------|
| Portfolio Tracker | [Soon] | Explore dropdown, profile dropdown |
| Saved Research | [Soon] | Explore dropdown, profile dropdown, settings |
| Saved Comparisons | [Soon] | Profile dropdown, settings |
| Notification Prefs | [Coming Soon] | Settings page |
| Plan Type / Subscription | [Coming Soon] | Settings page |
