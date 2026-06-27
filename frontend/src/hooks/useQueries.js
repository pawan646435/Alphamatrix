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
  DEFENCE: { key: 'DEFENCE', label: 'Defence', dbSectors: ['Defence', 'Industrials'] },
  FMCG: { key: 'FMCG', label: 'FMCG', dbSectors: ['FMCG', 'Consumer Defensive'] },
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
  LIVE:    60_000,          // 1 min — live prices
  NEWS:    5 * 60_000,      // 5 min — news feeds
  REGIME:  60 * 60_000,     // 1 hr  — market regime
  MASTER:  6 * 60 * 60_000, // 6 hr  — fundamentals
  FUND:    60 * 60_000,     // 1 hr  — NAV data
  FUND_LIST: 5 * 60_000,   // 5 min — fund explorer grid
  SEARCH:  30 * 60_000,    // 30 min — search results
};

// ─── QUERY KEY FACTORIES ─────────────────────────────────────────────────────
export const qk = {
  stockList:      (params = {}) => ['stocks', 'list', params],
  stockDetail:    (symbol)      => ['stocks', 'detail', symbol],
  stockHistory:   (symbol)      => ['stocks', 'history', symbol],
  marketRegime:   ()            => ['stocks', 'market-regime'],
  sectorDetails:  (sector)      => ['stocks', 'sector', sector],
  fundList:       (params = {}) => ['funds', 'list', params],
  fundDetail:     (code)        => ['funds', 'detail', code],
  newsIndia:      (cat)         => ['news', 'india', cat],
  newsGlobal:     (cat)         => ['news', 'global', cat],
  watchlist:      ()            => ['watchlist'],
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
    staleTime: STALE.MASTER,
    retry: 1,
    ...options
  });
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
  return useQuery({
    queryKey: qk.watchlist(),
    queryFn: async () => {
      const { data } = await apiClient.get('/stocks/watchlist');
      return data;
    },
    staleTime: STALE.LIVE,
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
    staleTime: STALE.FUND,
    retry: 1,
    ...options
  });
}

// ─── NEWS HOOKS ──────────────────────────────────────────────────────────────

/** Returns India market news feed */
export function useNewsIndia(category = 'all') {
  return useQuery({
    queryKey: qk.newsIndia(category),
    queryFn: async () => {
      const { data } = await apiClient.get('/news/list', { params: { stream: 'india', category } });
      return data || [];
    },
    staleTime: STALE.NEWS,
  });
}

/** Returns global market news feed */
export function useNewsGlobal(category = 'all') {
  return useQuery({
    queryKey: qk.newsGlobal(category),
    queryFn: async () => {
      const { data } = await apiClient.get('/news/list', { params: { stream: 'global', category } });
      return data || [];
    },
    staleTime: STALE.NEWS,
  });
}
