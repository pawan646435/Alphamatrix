import { useState, useCallback } from 'react';
import apiClient from '../services/api';

// Hook to query the mutual funds list with filters
export function useGetFunds() {
  const [funds, setFunds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchFunds = useCallback(async (params = {}) => {
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
      
      const response = await apiClient.get('/funds/', { params: cleanParams });
      setFunds(response.data);
    } catch (err) {
      setError(err.detail || 'Failed to fetch funds.');
    } finally {
      setLoading(false);
    }
  }, []);

  return { funds, loading, error, fetchFunds };
}

// Hook to retrieve detailed performance and NAV history for a fund
export function useGetFundDetail() {
  const [fundDetail, setFundDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchDetail = useCallback(async (schemeCode) => {
    if (!schemeCode) return;
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(`/funds/${schemeCode}`);
      setFundDetail(response.data);
    } catch (err) {
      setError(err.detail || 'Failed to fetch fund details.');
    } finally {
      setLoading(false);
    }
  }, []);

  return { fundDetail, loading, error, fetchDetail };
}

// Cache to store search results for memoization
const searchCache = new Map();

// Hook to search the full 10,000+ Indian mutual funds master index
export function useSearchFunds() {
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const search = useCallback(async (query) => {
    if (!query || query.length < 3) {
      setSearchResults([]);
      return;
    }
    
    const queryClean = query.trim().toLowerCase();
    
    // Return cached results instantly
    if (searchCache.has(queryClean)) {
      setSearchResults(searchCache.get(queryClean));
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/funds/search', { params: { query: queryClean } });
      searchCache.set(queryClean, response.data);
      setSearchResults(response.data);
    } catch (err) {
      setError(err.detail || 'Failed to search funds.');
    } finally {
      setLoading(false);
    }
  }, []);

  return { searchResults, loading, error, search, setSearchResults };
}

// Hook for AI Semantic Query parsing
export function useSemanticQuery() {
  const [matchedFunds, setMatchedFunds] = useState([]);
  const [parsedFilters, setParsedFilters] = useState(null);
  const [sqlExplanation, setSqlExplanation] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const executeSemanticQuery = useCallback(async (queryText) => {
    if (!queryText) return;
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.post('/ai/semantic-query', { query: queryText });
      setMatchedFunds(response.data.matched_funds || []);
      setParsedFilters(response.data.parsed_filters || null);
      setSqlExplanation(response.data.sql_explanation || '');
      return response.data;
    } catch (err) {
      setError(err.detail || 'Failed to execute semantic query.');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { matchedFunds, parsedFilters, sqlExplanation, loading, error, executeSemanticQuery, setMatchedFunds, setParsedFilters };
}

// Hook for AI Chat Analyst
export function useAIChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const sendMessage = useCallback(async (text, schemeCode = null, history = []) => {
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
      
      const response = await apiClient.post('/ai/chat', {
        message: text,
        scheme_code: schemeCode,
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

// Hook to trigger manual fund synchronizations
export function useSyncFund() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const sync = useCallback(async (schemeCode) => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.post(`/funds/sync/${schemeCode}`);
      return response.data;
    } catch (err) {
      setError(err.detail || 'Sync failed.');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { sync, loading, error };
}
