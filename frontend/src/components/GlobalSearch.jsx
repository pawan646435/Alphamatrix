import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useLocation } from 'react-router-dom';
import { Search, RefreshCw, Cpu, Layers, Zap } from 'lucide-react';
import apiClient from '../services/api';

export default function GlobalSearch() {
  const navigate = useNavigate();
  const location = useLocation();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState({});
  const inputWrapperRef = useRef(null);
  const dropdownRef = useRef(null);

  // Position the portal dropdown to exactly match the input width/position
  // NOTE: fixed positioning does NOT need scrollX/scrollY offsets
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

  useEffect(() => {
    const close = (event) => {
      const inInput = inputWrapperRef.current && inputWrapperRef.current.contains(event.target);
      const inDropdown = dropdownRef.current && dropdownRef.current.contains(event.target);
      if (!inInput && !inDropdown) {
        setShowDropdown(false);
      }
    };
    // Support both mouse and touch events for mobile outside-click detection
    document.addEventListener('mousedown', close);
    document.addEventListener('touchstart', close, { passive: true });
    window.addEventListener('scroll', updateDropdownPosition, true);
    window.addEventListener('resize', updateDropdownPosition);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('touchstart', close);
      window.removeEventListener('scroll', updateDropdownPosition, true);
      window.removeEventListener('resize', updateDropdownPosition);
    };
  }, [updateDropdownPosition]);

  // Update position whenever dropdown visibility changes
  useEffect(() => {
    if (showDropdown) {
      updateDropdownPosition();
    }
  }, [showDropdown, updateDropdownPosition]);

  // Debounced search
  useEffect(() => {
    if (query.trim().length < 2) {
      setTimeout(() => setResults([]), 0);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const type = location.pathname.startsWith('/stocks') ? 'stock' : 'fund';
        const response = await apiClient.get('/search', { params: { query: query.trim(), type } });
        setResults(response.data);
      } catch (err) {
        console.error('Failed to search:', err);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query, location.pathname]);

  const handleSelect = (item) => {
    setShowDropdown(false);
    setQuery('');
    if (item.type === 'stock') {
      navigate(`/stocks/detail/${item.symbol}`);
    } else {
      navigate(`/detail/${item.scheme_code}`);
    }
  };

  const handleDiscover = (tickerQuery) => {
    setShowDropdown(false);
    setQuery('');
    const ticker = tickerQuery.trim().toUpperCase().replace(/[^A-Z0-9&]/g, '');
    navigate(`/stocks/detail/${ticker}`);
  };

  const stocks = results.filter((r) => r.type === 'stock');
  const funds = results.filter((r) => r.type === 'fund');
  const looksLikeTicker = query.trim().length >= 2 && query.trim().length <= 15 && !query.includes(' ');
  const noResults = !loading && results.length === 0 && query.trim().length >= 2;

  const shouldShowDropdown = showDropdown && query.trim().length >= 2;

  // Mobile-keyboard-safe max height: use 40vh so keyboard doesn't cover the list
  const dropdownContent = shouldShowDropdown ? (
    <div
      ref={dropdownRef}
      style={dropdownStyle}
      className="bg-brand-surface border border-brand-border shadow-2xl max-h-[40vh] overflow-y-auto divide-y divide-brand-border font-mono text-xs scrollbar"
    >
      {/* Stocks Section */}
      {stocks.length > 0 && (
        <div>
          <div className="bg-brand-bg px-4 py-2 text-[9px] text-brand-primary font-bold border-b border-brand-border flex items-center gap-1.5 tracking-wider">
            <Cpu className="w-3 h-3" /> EQUITIES
          </div>
          <div className="divide-y divide-brand-border/40">
            {stocks.map((item) => (
              <button
                key={item.symbol}
                onClick={() => item.discover ? handleDiscover(item.symbol) : handleSelect(item)}
                // min-h-[44px] ensures touch target compliance
                className="w-full text-left px-4 py-3 min-h-[44px] hover:bg-brand-border/40 text-black dark:text-white transition-colors flex items-center justify-between gap-3 group cursor-pointer"
              >
                <span className="truncate group-hover:text-brand-primary transition-colors font-semibold">{item.name}</span>
                <div className="flex items-center gap-1.5 shrink-0">
                  {item.discover && (
                    <span className="flex items-center gap-0.5 text-brand-primary bg-brand-primary/10 border border-brand-primary/40 px-1.5 py-0.5 text-[8px] font-bold tracking-wide">
                      <Zap className="w-2 h-2" /> DISCOVER
                    </span>
                  )}
                  <span className="text-brand-primary bg-brand-bg border border-brand-border/60 px-1.5 py-0.5 font-bold font-mono text-[9px]">
                    {item.symbol}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Mutual Funds Section */}
      {funds.length > 0 && (
        <div>
          <div className="bg-brand-bg px-4 py-2 text-[9px] text-brand-primary font-bold border-b border-brand-border flex items-center gap-1.5 tracking-wider">
            <Layers className="w-3 h-3" /> MUTUAL FUNDS
          </div>
          <div className="divide-y divide-brand-border/40">
            {funds.map((item) => (
              <button
                key={item.scheme_code}
                onClick={() => handleSelect(item)}
                className="w-full text-left px-4 py-3 min-h-[44px] hover:bg-brand-border/40 text-black dark:text-white transition-colors flex items-center justify-between gap-3 group cursor-pointer"
              >
                <span className="truncate group-hover:text-brand-primary transition-colors font-semibold">{item.name}</span>
                <span className="shrink-0 text-brand-textMuted bg-brand-bg border border-brand-border/60 px-1.5 py-0.5 font-mono text-[9px]">
                  {item.scheme_code}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Dynamic Discovery suggestion */}
      {noResults && looksLikeTicker && location.pathname.startsWith('/stocks') && (
        <div className="px-4 py-3 space-y-2">
          <p className="text-brand-textMuted text-[10px]">
            No indexed results for <span className="text-white font-bold">"{query}"</span>
          </p>
          <button
            onClick={() => handleDiscover(query)}
            className="w-full flex items-center gap-2 px-3 py-3 min-h-[44px] bg-brand-primary/10 border border-brand-primary/40 hover:bg-brand-primary/20 transition-colors group cursor-pointer"
          >
            <Zap className="h-3 w-3 text-brand-primary shrink-0" />
            <span className="text-[10px] font-bold text-brand-primary">
              Discover <span className="uppercase">{query.trim()}</span> on NSE
            </span>
            <span className="ml-auto text-[9px] text-brand-textMuted group-hover:text-brand-primary transition-colors hidden sm:inline">
              → Auto-ingest from Yahoo Finance
            </span>
          </button>
        </div>
      )}

      {noResults && (!looksLikeTicker || !location.pathname.startsWith('/stocks')) && (
        <div className="px-4 py-4 text-center text-brand-textMuted">
          No matching assets found.
        </div>
      )}
    </div>
  ) : null;

  return (
    <div className="relative w-full max-w-xl font-mono text-xs" ref={inputWrapperRef}>
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-brand-textMuted pointer-events-none" />
        <input
          type="text"
          inputMode="search"
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck="false"
          // Short placeholder on mobile, full one on sm+
          placeholder="Search stocks & funds..."
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
          // min-h-[44px] ensures the input itself is a 44px touch target
          className="w-full pl-11 pr-10 py-3 min-h-[44px] bg-brand-bg border border-brand-border text-xs text-black dark:text-white placeholder-brand-textMuted focus:outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary transition-all font-mono"
        />
        {loading && (
          <RefreshCw className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-brand-primary animate-spin" />
        )}
      </div>

      {/* Render dropdown via portal so it escapes ALL parent overflow/z-index constraints */}
      {typeof document !== 'undefined' && createPortal(dropdownContent, document.body)}
    </div>
  );
}
