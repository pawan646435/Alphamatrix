import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Search, RefreshCw, Star, History } from 'lucide-react';
import apiClient from '../services/api';

const POPULAR_STOCKS = [
  { symbol: 'TCS', company_name: 'Tata Consultancy Services Ltd.' },
  { symbol: 'RELIANCE', company_name: 'Reliance Industries Ltd.' },
  { symbol: 'INFY', company_name: 'Infosys Ltd.' },
  { symbol: 'HDFCBANK', company_name: 'HDFC Bank Ltd.' },
  { symbol: 'SBIN', company_name: 'State Bank of India' }
];

export default function StockSearchPicker({
  selectedSymbol,
  onSelect,
  excludeSymbol,
  placeholder = "Search stock symbol or name...",
  label = "Select Equity"
}) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState({});
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [recentSearches, setRecentSearches] = useState([]);
  const [selectedStockName, setSelectedStockName] = useState('');

  const inputWrapperRef = useRef(null);
  const dropdownRef = useRef(null);

  // Load recent searches from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('alphamatrix_recent_compares');
      if (saved) {
        setTimeout(() => setRecentSearches(JSON.parse(saved)), 0);
      }
    } catch (e) {
      console.error('Failed to load recent searches:', e);
    }
  }, []);

  // Update input text if selectedSymbol changes
  useEffect(() => {
    if (selectedSymbol) {
      setTimeout(() => setQuery(selectedSymbol), 0);
      const fetchStockName = async () => {
        try {
          const response = await apiClient.get('/stocks/search', { params: { query: selectedSymbol } });
          const match = response.data.find(s => s.symbol === selectedSymbol);
          if (match) {
            setSelectedStockName(match.company_name);
          }
        } catch (e) {
          console.error(e);
        }
      };
      fetchStockName();
    } else {
      setTimeout(() => {
        setQuery('');
        setSelectedStockName('');
      }, 0);
    }
  }, [selectedSymbol]);

  // Position the portal dropdown — fixed positioning does NOT need scrollX/scrollY offsets
  const updateDropdownPosition = useCallback(() => {
    if (!inputWrapperRef.current) return;
    const rect = inputWrapperRef.current.getBoundingClientRect();
    setDropdownStyle({
      position: 'fixed',
      top: rect.bottom + 2,
      left: rect.left,
      width: rect.width,
      zIndex: 99999,
    });
  }, []);

  // Outside click (mouse + touch) and window scroll/resize listener
  useEffect(() => {
    const handleOutside = (event) => {
      const inInput = inputWrapperRef.current && inputWrapperRef.current.contains(event.target);
      const inDropdown = dropdownRef.current && dropdownRef.current.contains(event.target);
      if (!inInput && !inDropdown) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('touchstart', handleOutside, { passive: true });
    window.addEventListener('scroll', updateDropdownPosition, true);
    window.addEventListener('resize', updateDropdownPosition);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('touchstart', handleOutside);
      window.removeEventListener('scroll', updateDropdownPosition, true);
      window.removeEventListener('resize', updateDropdownPosition);
    };
  }, [updateDropdownPosition]);

  useEffect(() => {
    if (showDropdown) {
      updateDropdownPosition();
    }
  }, [showDropdown, updateDropdownPosition]);

  // Debounced Search suggestions
  useEffect(() => {
    if (query.trim().length < 2 || query === selectedSymbol) {
      setTimeout(() => setResults([]), 0);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await apiClient.get('/stocks/search', { params: { query: query.trim() } });
        const filtered = response.data.filter(s => s.symbol !== excludeSymbol);
        setResults(filtered);
        setHighlightedIndex(-1);
      } catch (err) {
        console.error('Failed to search stocks:', err);
      } finally {
        setLoading(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query, excludeSymbol, selectedSymbol]);

  const handleSelect = (stock) => {
    onSelect(stock.symbol);
    setQuery(stock.symbol);
    setSelectedStockName(stock.company_name);
    setShowDropdown(false);

    // Save to recent searches
    const updatedRecent = [
      stock,
      ...recentSearches.filter(s => s.symbol !== stock.symbol)
    ].slice(0, 5);
    setRecentSearches(updatedRecent);
    localStorage.setItem('alphamatrix_recent_compares', JSON.stringify(updatedRecent));
  };

  // Keyboard navigation handler
  const handleKeyDown = (e) => {
    const visibleList = getVisibleList();
    if (!showDropdown || visibleList.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev + 1) % visibleList.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev - 1 + visibleList.length) % visibleList.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < visibleList.length) {
        handleSelect(visibleList[highlightedIndex]);
      }
    } else if (e.key === 'Escape') {
      setShowDropdown(false);
    }
  };

  const getVisibleList = () => {
    if (query.trim().length >= 2 && query !== selectedSymbol) {
      return results;
    }
    const filteredPopular = POPULAR_STOCKS.filter(s => s.symbol !== excludeSymbol);
    const filteredRecent = recentSearches.filter(s => s.symbol !== excludeSymbol);
    return [...filteredRecent, ...filteredPopular];
  };



  // Mobile-keyboard-safe max height — 40vh prevents the keyboard from covering results
  const dropdownContent = showDropdown ? (
    <div
      ref={dropdownRef}
      style={dropdownStyle}
      className="bg-brand-surface border border-brand-border shadow-2xl max-h-[40vh] overflow-y-auto divide-y divide-brand-border/40 font-mono text-xs scrollbar"
    >
      {/* Suggestions from typing */}
      {query.trim().length >= 2 && query !== selectedSymbol ? (
        results.length > 0 ? (
          results.map((item, idx) => (
            <button
              key={item.symbol}
              onClick={() => handleSelect(item)}
              // min-h-[44px] for touch target compliance
              className={`w-full text-left px-4 py-3 min-h-[44px] hover:bg-brand-border/40 text-black dark:text-white transition-colors flex items-center justify-between gap-3 group cursor-pointer ${
                highlightedIndex === idx ? 'bg-brand-border/40' : ''
              }`}
            >
              <div className="flex flex-col min-w-0">
                <span className="font-semibold text-black dark:text-white group-hover:text-brand-primary transition-colors">{item.symbol}</span>
                <span className="text-[10px] text-brand-textMuted truncate">{item.company_name}</span>
              </div>
              {item.sector && (
                <span className="shrink-0 text-brand-primary bg-brand-bg border border-brand-border/60 px-1.5 py-0.5 font-bold font-mono text-[9px] uppercase max-w-[80px] truncate">
                  {item.sector}
                </span>
              )}
            </button>
          ))
        ) : (
          <div className="px-4 py-4 text-brand-textMuted text-center min-h-[44px] flex items-center justify-center">
            {loading ? 'Searching...' : 'No matching equities found'}
          </div>
        )
      ) : (
        /* Empty Query / Focus Suggestions */
        <div>
          {/* Recent Searches */}
          {recentSearches.length > 0 && (
            <div>
              <div className="bg-brand-bg px-4 py-2 text-[8px] text-brand-primary font-bold border-b border-brand-border flex items-center gap-1.5 tracking-wider uppercase">
                <History className="w-3 h-3" /> RECENT SEARCHES
              </div>
              {recentSearches
                .filter(s => s.symbol !== excludeSymbol)
                .map((item, idx) => (
                  <button
                    key={`recent-${item.symbol}`}
                    onClick={() => handleSelect(item)}
                    className={`w-full text-left px-4 py-3 min-h-[44px] hover:bg-brand-border/40 text-black dark:text-white transition-colors flex items-center justify-between gap-3 group cursor-pointer ${
                      highlightedIndex === idx ? 'bg-brand-border/40' : ''
                    }`}
                  >
                    <div className="flex flex-col min-w-0">
                      <span className="font-semibold text-black dark:text-white group-hover:text-brand-primary transition-colors">{item.symbol}</span>
                      <span className="text-[10px] text-brand-textMuted truncate">{item.company_name}</span>
                    </div>
                  </button>
                ))}
            </div>
          )}

          {/* Popular Stocks */}
          <div>
            <div className="bg-brand-bg px-4 py-2 text-[8px] text-brand-primary font-bold border-b border-brand-border/40 flex items-center gap-1.5 tracking-wider uppercase">
              <Star className="w-3 h-3" /> POPULAR EQUITIES
            </div>
            {POPULAR_STOCKS
              .filter(s => s.symbol !== excludeSymbol)
              .map((item, idx) => {
                const displayIdx = idx + recentSearches.filter(s => s.symbol !== excludeSymbol).length;
                return (
                  <button
                    key={`popular-${item.symbol}`}
                    onClick={() => handleSelect(item)}
                    className={`w-full text-left px-4 py-3 min-h-[44px] hover:bg-brand-border/40 text-black dark:text-white transition-colors flex items-center justify-between gap-3 group cursor-pointer ${
                      highlightedIndex === displayIdx ? 'bg-brand-border/40' : ''
                    }`}
                  >
                    <div className="flex flex-col min-w-0">
                      <span className="font-semibold text-black dark:text-white group-hover:text-brand-primary transition-colors">{item.symbol}</span>
                      <span className="text-[10px] text-brand-textMuted truncate">{item.company_name}</span>
                    </div>
                  </button>
                );
              })}
          </div>
        </div>
      )}
    </div>
  ) : null;

  return (
    <div className="relative w-full font-mono text-xs" ref={inputWrapperRef}>
      <label className="block text-[9px] font-bold text-brand-primary uppercase tracking-wider font-mono mb-1">
        {label}
      </label>
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-brand-textMuted pointer-events-none" />
        <input
          type="text"
          inputMode="search"
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck="false"
          placeholder={placeholder}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShowDropdown(true);
            updateDropdownPosition();
          }}
          onFocus={() => {
            setShowDropdown(true);
            updateDropdownPosition();
          }}
          onKeyDown={handleKeyDown}
          // min-h-[44px] ensures touch target compliance
          className="w-full pl-10 pr-10 py-3 min-h-[44px] bg-brand-bg border border-brand-border text-xs text-black dark:text-white placeholder-brand-textMuted focus:outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary transition-all font-mono"
        />
        {loading && (
          <RefreshCw className="absolute right-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-brand-primary animate-spin" />
        )}
      </div>
      {selectedStockName && query === selectedSymbol && (
        <div className="text-[9px] text-brand-textMuted mt-1 uppercase tracking-wide truncate max-w-full">
          {selectedStockName}
        </div>
      )}

      {/* Dropdown Portal */}
      {typeof document !== 'undefined' && createPortal(dropdownContent, document.body)}
    </div>
  );
}
