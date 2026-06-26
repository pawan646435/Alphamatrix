"""
Centralized Redis cache TTL constants for AlphaMatrix.

All TTL values in seconds. Using constants prevents magic numbers being
scattered across route files and makes tuning a single-file operation.
"""

# ---------------------------------------------------------------------------
# Real-time / Price Data
# ---------------------------------------------------------------------------
STOCK_PRICE_TTL = 60          # 1 minute  — live price data, refresh frequently
STOCK_LIST_TTL = 300          # 5 minutes — top stocks grid, refreshes on market moves

# ---------------------------------------------------------------------------
# Market Analysis
# ---------------------------------------------------------------------------
STOCK_MASTER_TTL = 21_600     # 6 hours   — fundamental data (PE, ROE etc.), slow-changing
STOCK_HISTORY_TTL = 86_400    # 24 hours  — historical price series, daily granularity
MARKET_REGIME_TTL = 3_600     # 1 hour    — macro regime classification
SECTOR_LAB_TTL = 86_400       # 24 hours  — sector analytics, daily granularity
WATCHLIST_ANALYTICS_TTL = 1_800  # 30 min — portfolio diagnostics

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
SEARCH_RESULT_TTL = 1_800     # 30 minutes — search index results (stable dataset)
STOCK_SEARCH_TTL = 600        # 10 minutes — stock-specific search results

# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------
NEWS_FEED_TTL = 300           # 5 minutes  — live news feed from yfinance

# ---------------------------------------------------------------------------
# AI / LLM Responses (expensive to generate — cache aggressively)
# ---------------------------------------------------------------------------
AI_ANALYSIS_TTL = 86_400      # 24 hours   — stock briefing and AI summaries
AI_COMPARISON_TTL = 86_400    # 24 hours   — AI stock comparison verdicts
WATCHLIST_DIAGNOSTICS_TTL = 86_400  # 24 hours — AI watchlist portfolio analysis

# ---------------------------------------------------------------------------
# Fund Data
# ---------------------------------------------------------------------------
FUND_DETAIL_TTL = 3_600       # 1 hour    — fund NAV detail
FUND_LIST_TTL = 3_600         # 1 hour    — fund list / explorer
