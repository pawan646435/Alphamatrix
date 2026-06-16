import { useState, useCallback } from 'react';
import apiClient from '../services/api';

// Hook to query the stocks list with filters
export function useGetStocks() {
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchStocks = useCallback(async (params = {}) => {
    setLoading(true);
    setError(null);
    try {
      // Clean undefined params
      const cleanParams = {};
      Object.keys(params).forEach(key => {
        if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
          cleanParams[key] = params[key];
        }
      });
      
      const response = await apiClient.get('/stocks/list', { params: cleanParams });
      setStocks(response.data);
    } catch (err) {
      setError(err.detail || 'Failed to fetch stocks.');
    } finally {
      setLoading(false);
    }
  }, []);

  return { stocks, loading, error, fetchStocks };
}

// Hook to retrieve detailed performance and price history for a stock
export function useGetStockDetail() {
  const [stockDetail, setStockDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [discovering, setDiscovering] = useState(false);
  const [discoveringMessage, setDiscoveringMessage] = useState('');

  const fetchDetail = useCallback(async (symbol) => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(`/stocks/detail/${symbol}`, {
        validateStatus: (s) => s < 500, // Allow 202 to pass through
      });
      if (response.status === 202 && response.data?.status === 'discovering') {
        setDiscovering(true);
        setDiscoveringMessage(response.data.message || `Discovering ${symbol}...`);
        setStockDetail(null);
      } else {
        setDiscovering(false);
        setDiscoveringMessage('');
        setStockDetail(response.data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.detail || 'Failed to fetch stock details.');
    } finally {
      setLoading(false);
    }
  }, []);

  const checkStatus = useCallback(async (symbol) => {
    if (!symbol) return null;
    try {
      const response = await apiClient.get(`/stocks/status/${symbol}`);
      return response.data;
    } catch {
      return null;
    }
  }, []);

  return { stockDetail, loading, error, fetchDetail, setStockDetail, discovering, discoveringMessage, checkStatus };
}


// Cache to store search results for memoization
const stockSearchCache = new Map();

// Hook to search the seeded stocks index
export function useSearchStocks() {
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const search = useCallback(async (query) => {
    if (!query || query.length < 2) {
      setSearchResults([]);
      return;
    }
    
    const queryClean = query.trim().toLowerCase();
    
    // Return cached results instantly
    if (stockSearchCache.has(queryClean)) {
      setSearchResults(stockSearchCache.get(queryClean));
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/stocks/search', { params: { query: queryClean } });
      stockSearchCache.set(queryClean, response.data);
      setSearchResults(response.data);
    } catch (err) {
      setError(err.detail || 'Failed to search stocks.');
    } finally {
      setLoading(false);
    }
  }, []);

  return { searchResults, loading, error, search, setSearchResults };
}

// Hook for AI Stock Chat Analyst
export function useStockAIChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const sendMessage = useCallback(async (text, symbol = null, history = []) => {
    if (!text) return;
    
    // Optimistic local update
    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setError(null);
    
    try {
      // Map message history to schema format
      const formattedHistory = history.map(m => ({
        role: m.role,
        content: m.content
      }));
      
      const response = await apiClient.post('/stocks/chat', {
        message: text,
        scheme_code: symbol ? 0 : null, // Scheme code field placeholder
        history: formattedHistory
      });
      
      const assistantMsg = { role: 'assistant', content: response.data.response };
      setMessages((prev) => [...prev, assistantMsg]);
      return response.data;
    } catch (err) {
      const errMsg = err.detail || 'Failed to communicate with AI analyst.';
      setError(errMsg);
      setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${errMsg}` }]);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, loading, error, sendMessage, clearChat, setMessages };
}

// Hook to manage watchlist items & portfolio diagnostics
export function useWatchlist() {
  const [watchlist, setWatchlist] = useState([]);
  const [diagnostics, setDiagnostics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [diagLoading, setDiagLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchWatchlist = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/stocks/watchlist');
      setWatchlist(response.data);
    } catch (err) {
      setError(err.detail || 'Failed to fetch watchlist.');
    } finally {
      setLoading(false);
    }
  }, []);

  const addToWatchlist = useCallback(async (symbol) => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.post('/stocks/watchlist', null, { params: { symbol } });
      await fetchWatchlist();
    } catch (err) {
      setError(err.detail || 'Failed to add to watchlist.');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [fetchWatchlist]);

  const removeFromWatchlist = useCallback(async (symbol) => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.delete(`/stocks/watchlist/${symbol}`);
      await fetchWatchlist();
    } catch (err) {
      setError(err.detail || 'Failed to remove from watchlist.');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [fetchWatchlist]);

  const fetchDiagnostics = useCallback(async () => {
    setDiagLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/stocks/watchlist/analytics');
      setDiagnostics(response.data);
    } catch (err) {
      setError(err.detail || 'Failed to generate diagnostics.');
    } finally {
      setDiagLoading(false);
    }
  }, []);

  return { 
    watchlist, 
    diagnostics, 
    loading, 
    diagLoading, 
    error, 
    fetchWatchlist, 
    addToWatchlist, 
    removeFromWatchlist, 
    fetchDiagnostics 
  };
}

// Hook to load Sector Lab metrics
export function useGetSectorDetails() {
  const [sectorDetails, setSectorDetails] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchSectorDetails = useCallback(async (sectorName) => {
    if (!sectorName) return;
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(`/stocks/sector/${sectorName}`);
      setSectorDetails(response.data);
    } catch (err) {
      setError(err.detail || 'Failed to fetch sector lab details.');
    } finally {
      setLoading(false);
    }
  }, []);

  return { sectorDetails, loading, error, fetchSectorDetails };
}

// Hook to load market regime macro diagnostics
export function useMarketRegime() {
  const [marketRegime, setMarketRegime] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchMarketRegime = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/stocks/market-regime');
      setMarketRegime(response.data);
    } catch (err) {
      setError(err.detail || 'Failed to fetch market regime diagnostics.');
    } finally {
      setLoading(false);
    }
  }, []);

  return { marketRegime, loading, error, fetchMarketRegime };
}

// Hook to compare two equities
export function useGetStockComparison() {
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchComparison = useCallback(async (s1, s2) => {
    if (!s1 || !s2) return;
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/stocks/compare', { params: { s1: s1.toUpperCase(), s2: s2.toUpperCase() } });
      setComparison(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.detail || 'Failed to fetch comparison.');
    } finally {
      setLoading(false);
    }
  }, []);

  return { comparison, loading, error, fetchComparison, setComparison };
}

