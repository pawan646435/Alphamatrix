/**
 * useQueries.js — React Query hooks for AlphaMatrix
 *
 * Replaces manual useEffect+useState fetch patterns with React Query.
 * Provides: automatic deduplication, background refresh, stale-while-revalidate,
 * retry handling, and shared cache across all page instances.
 *
 * staleTime strategy:
 *   Stock prices       → 60s    (live market data)
 *   News               → 5min   (live feeds)
 *   Market regime      → 1hr    (macro classification)
 *   Stock master/detail→ 6hr    (fundamental data)
 *   Fund data          → 1hr    (NAV data)
 *   Fund list          → 5min   (explorer grid)
 */
import { useQuery } from '@tanstack/react-query';
import apiClient from '../services/api';

// ─── SECTOR STANDARDIZATION REGISTRY ─────────────────────────────────────────
export const SECTORS = {
  BANKING: { key: 'BANKING', label: 'Banking', dbSectors: ['Financial Services', 'Banking'] },
  IT: { key: 'IT', label: 'IT', dbSectors: ['IT', 'Technology'] },
  AUTO: { key: 'AUTO', label: 'Auto', dbSectors: ['Auto', 'Consumer Cyclical'] },
  ENERGY: { key: 'ENERGY', label: 'Energy', dbSectors: ['Energy'] },
  DEFENCE: { key: 'DEFENCE', label: 'Defence', dbSectors: ['Defence'] },
  FMCG: { key: 'FMCG', label: 'FMCG', dbSectors: ['FMCG'] },
  PHARMA: { key: 'PHARMA', label: 'Pharma', dbSectors: ['Pharma', 'Healthcare'] },
  METALS: { key: 'METALS', label: 'Metals', dbSectors: ['Metals', 'Basic Materials'] },
  INFRASTRUCTURE: { key: 'INFRASTRUCTURE', label: 'Infrastructure', dbSectors: ['Infrastructure'] },
  CHEMICALS: { key: 'CHEMICALS', label: 'Chemicals', dbSectors: ['Chemicals'] },
  CONSUMER_DURABLES: { key: 'CONSUMER_DURABLES', label: 'Consumer Durables', dbSectors: ['Consumer Durables'] },
  REALTY: { key: 'REALTY', label: 'Realty', dbSectors: ['Realty', 'Real Estate'] },
  TELECOM: { key: 'TELECOM', label: 'Telecom', dbSectors: ['Telecom', 'Communication Services'] },
  PSU: { key: 'PSU', label: 'PSU', dbSectors: ['PSU'] },
  CAPITAL_GOODS: { key: 'CAPITAL_GOODS', label: 'Capital Goods', dbSectors: ['Capital Goods'] },
};

export function getStandardizedSector(dbSector) {
  if (!dbSector) return { key: 'UNKNOWN', label: 'Unknown' };
  const sectorClean = dbSector.trim();
  const sectorLower = sectorClean.toLowerCase();
  
  for (const info of Object.values(SECTORS)) {
    if (info.dbSectors.some(s => s.toLowerCase() === sectorLower)) {
      return { key: info.key, label: info.label };
    }
  }
  return { key: 'UNKNOWN', label: sectorClean };
}

// ─── STALE TIME CONSTANTS ────────────────────────────────────────────────────
export const STALE = {
  LIVE:          60_000,          // 1 min — live prices
  NEWS:          5 * 60_000,      // 5 min — news feeds
  REGIME:        60 * 60_000,     // 1 hr  — market regime
  MASTER:        6 * 60 * 60_000, // 6 hr  — fundamentals
  FUND:          60 * 60_000,     // 1 hr  — NAV data
  FUND_LIST:     5 * 60_000,      // 5 min — fund explorer grid
  SEARCH:        30 * 60_000,     // 30 min — search results
  BACKTEST:      24 * 60 * 60_000,// 24 hr — backtest summary
  BACKTEST_STOCK:12 * 60 * 60_000,// 12 hr — per-stock backtest
};

// ─── QUERY KEY FACTORIES ─────────────────────────────────────────────────────
export const qk = {
  stockList:       (params = {}) => ['stocks', 'list', params],
  stockDetail:     (symbol)      => ['stocks', 'detail', symbol],
  stockHistory:    (symbol)      => ['stocks', 'history', symbol],
  marketRegime:    ()            => ['stocks', 'market-regime'],
  sectorDetails:   (sector)      => ['stocks', 'sector', sector],
  fundList:        (params = {}) => ['funds', 'list', params],
  fundDetail:      (code)        => ['funds', 'detail', code],
  newsIndia:       (cat)         => ['news', 'india', cat],
  newsGlobal:      (cat)         => ['news', 'global', cat],
  watchlist:       ()            => ['watchlist'],
  backtestSummary: ()            => ['stocks', 'backtest', 'summary'],
  backtestStock:   (symbol)      => ['stocks', 'backtest', symbol],
};

// ─── STOCK HOOKS ─────────────────────────────────────────────────────────────

/** Returns the full list of seeded stocks with optional filters */
export function useStockList(params = {}) {
  return useQuery({
    queryKey: qk.stockList(params),
    queryFn: async () => {
      const cleanParams = Object.fromEntries(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
      );
      const { data } = await apiClient.get('/stocks/list', { params: cleanParams });
      return data;
    },
    staleTime: STALE.LIVE,
  });
}

/** Returns detailed stock data for a symbol. Handles 202 discovering state with auto-polling. */
export function useStockDetail(symbol, options = {}) {
  return useQuery({
    queryKey: qk.stockDetail(symbol),
    queryFn: async () => {
      const response = await apiClient.get(`/stocks/detail/${symbol}`, {
        validateStatus: (s) => s < 500,
      });
      return response.data;
    },
    enabled: !!symbol,
    staleTime: 3600000, // 1 hour
    gcTime: 86400000,    // 24 hours
    retry: 1,
    ...options
  });
}

/** Split React Query hooks for optimized parallel stock details load */

export function useStockMeta(symbol, options = {}) {
  return useQuery({
    queryKey: ['stocks', 'detail', symbol, 'meta'],
    queryFn: async () => {
      const { data } = await apiClient.get(`/stocks/detail/${symbol}/meta`, {
        // Allow 202 (discovering) and 404 through — don't throw for these
        validateStatus: (s) => (s >= 200 && s < 300) || s === 404,
      });
      return data;
    },
    enabled: !!symbol,
    staleTime: 86400000, // 24 hours (cleared for new stocks after ingestion)
    gcTime: 86400000,
    // Don't retry 404 — stock is permanently not found on NSE/BSE
    retry: (failureCount, error) => {
      if (error?.status === 404) return false;
      return failureCount < 2;
    },
    ...options
  });
}

export function useStockMetrics(symbol, options = {}) {
  return useQuery({
    queryKey: ['stocks', 'detail', symbol, 'metrics'],
    queryFn: async () => {
      const { data } = await apiClient.get(`/stocks/detail/${symbol}/metrics`);
      return data;
    },
    enabled: !!symbol,
    staleTime: 86400000, // 24 hours
    gcTime: 86400000,
    retry: 1,
    ...options
  });
}

export function useStockChart(symbol, period = "3y", options = {}) {
  return useQuery({
    queryKey: ['stocks', 'detail', symbol, 'chart', period],
    queryFn: async () => {
      const { data } = await apiClient.get(`/stocks/detail/${symbol}/chart`, {
        params: { period }
      });
      return data;
    },
    enabled: !!symbol,
    staleTime: 3600000, // 1 hour
    gcTime: 3600000,
    retry: 1,
    ...options
  });
}

export function useStockBriefing(symbol, options = {}) {
  return useQuery({
    queryKey: ['stocks', 'detail', symbol, 'briefing'],
    queryFn: async () => {
      const { data } = await apiClient.get(`/stocks/detail/${symbol}/briefing`);
      return data;
    },
    enabled: !!symbol,
    staleTime: 86400000, // 24 hours
    gcTime: 86400000,
    retry: 1,
    ...options
  });
}

export function useStockNews(symbol, options = {}) {
  return useQuery({
    queryKey: ['stocks', 'detail', symbol, 'news'],
    queryFn: async () => {
      const { data } = await apiClient.get(`/stocks/detail/${symbol}/news`);
      return data;
    },
    enabled: !!symbol,
    staleTime: 900000, // 15 minutes
    gcTime: 900000,
    retry: 1,
    ...options
  });
}

/**
 * useStockStatus — Progressive Discovery Pipeline v3
 *
 * Polls /stocks/status/{symbol} every 4s while the stock is not READY.
 * Returns { status, available_sections, pending_sections, progress,
 *           stage_message, current_price, company_name, ... }
 *
 * The caller uses available_sections to decide which page sections to render.
 */
export function useStockStatus(symbol, options = {}) {
  return useQuery({
    queryKey: ['stocks', 'status', symbol],
    queryFn: async () => {
      const { data } = await apiClient.get(`/stocks/status/${symbol}`, {
        validateStatus: (s) => (s >= 200 && s < 300) || s === 404,
      });
      return data;
    },
    enabled: !!symbol,
    staleTime: 0,          // always fresh — pipeline state changes frequently
    gcTime: 60000,
    refetchInterval: (query) => {
      const data = query?.state?.data;
      if (!data) return 4000;
      const done = data.status === 'READY' || data.status === 'NOT_FOUND';
      return done ? false : 4000;
    },
    retry: (failureCount, error) => {
      if (error?.status === 404) return false;
      return failureCount < 2;
    },
    ...options
  });
}

/**
 * advanceIngestionPipeline — fire-and-forget POST to run the next pipeline step.
 * Returns a promise. The caller does NOT need to await it — it fires and the
 * /status poll will pick up the state change in the next interval.
 */
export async function advanceIngestionPipeline(symbol) {
  try {
    const { data } = await apiClient.post(`/stocks/ingest/${symbol}`);
    return data;
  } catch (err) {
    // Swallow non-critical errors — the /status poll will show the real state
    console.warn(`[Pipeline] /ingest/${symbol} failed:`, err?.response?.data || err.message);
    return null;
  }
}

/** Returns market regime macro diagnostics */
export function useMarketRegime() {
  return useQuery({
    queryKey: qk.marketRegime(),
    queryFn: async () => {
      const { data } = await apiClient.get('/stocks/market-regime');
      return data;
    },
    staleTime: STALE.REGIME,
  });
}

/** Returns sector lab details for a sector */
export function useSectorDetails(sectorName) {
  return useQuery({
    queryKey: qk.sectorDetails(sectorName),
    queryFn: async () => {
      const { data } = await apiClient.get(`/stocks/sector/${sectorName}`);
      return data;
    },
    enabled: !!sectorName,
    staleTime: STALE.MASTER,
  });
}

/** Returns the user's watchlist */
export function useWatchlistQuery() {
  const token = typeof window !== 'undefined' ? localStorage.getItem('alphamatrix_token') : null;
  return useQuery({
    queryKey: qk.watchlist(),
    queryFn: async () => {
      const { data } = await apiClient.get('/stocks/watchlist');
      return data;
    },
    staleTime: STALE.LIVE,
    enabled: !!token,
  });
}

// ─── FUND HOOKS ──────────────────────────────────────────────────────────────

/** Returns fund list with optional filters */
export function useFundList(params = {}) {
  return useQuery({
    queryKey: qk.fundList(params),
    queryFn: async () => {
      const cleanParams = Object.fromEntries(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
      );
      const { data } = await apiClient.get('/funds/', { params: cleanParams });
      return data;
    },
    staleTime: STALE.FUND_LIST,
  });
}

/** Returns detailed fund data including NAV history and background AI generation auto-polling */
export function useFundDetail(schemeCode, options = {}) {
  return useQuery({
    queryKey: qk.fundDetail(schemeCode),
    queryFn: async () => {
      const { data } = await apiClient.get(`/funds/${schemeCode}`);
      return data;
    },
    enabled: !!schemeCode,
    staleTime: 3600000, // 1 hour
    gcTime: 86400000,    // 24 hours
    cacheTime: 86400000, // 24 hours compatibility
    retry: 1,
    ...options
  });
}

// ─── NEWS HOOKS ──────────────────────────────────────────────────────────────

/** Returns India market news feed — multi-source aggregated */
export function useNewsIndia(category = 'all') {
  return useQuery({
    queryKey: qk.newsIndia(category),
    queryFn: async () => {
      const { data } = await apiClient.get('/news/india', { params: { category } });
      return data || [];
    },
    staleTime: STALE.NEWS,
  });
}

/** Returns global market news feed — multi-source aggregated */
export function useNewsGlobal(category = 'all') {
  return useQuery({
    queryKey: qk.newsGlobal(category),
    queryFn: async () => {
      const { data } = await apiClient.get('/news/global', { params: { category } });
      return data || [];
    },
    staleTime: STALE.NEWS,
  });
}

/** Returns aggregate backtesting summary for the verdict engine */
export function useBacktestSummary() {
  return useQuery({
    queryKey: qk.backtestSummary(),
    queryFn: async () => {
      const { data } = await apiClient.get('/stocks/backtest/summary');
      return data;
    },
    staleTime: STALE.BACKTEST,
    retry: 1,
  });
}

/** Returns per-stock backtest results */
export function useStockBacktest(symbol) {
  return useQuery({
    queryKey: qk.backtestStock(symbol),
    queryFn: async () => {
      const { data } = await apiClient.get(`/stocks/backtest/${symbol}`);
      return data;
    },
    staleTime: STALE.BACKTEST_STOCK,
    enabled: !!symbol,
    retry: 1,
  });
}
