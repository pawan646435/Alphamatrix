import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, RefreshCw, Cpu, Layers } from 'lucide-react';
import apiClient from '../services/api';

export default function GlobalSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Debounced search
  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await apiClient.get('/search', { params: { query: query.trim() } });
        setResults(response.data);
      } catch (err) {
        console.error('Failed to search:', err);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query]);

  const handleSelect = (item) => {
    setShowDropdown(false);
    setQuery('');
    if (item.type === 'stock') {
      navigate(`/stocks/detail/${item.symbol}`);
    } else {
      navigate(`/detail/${item.scheme_code}`);
    }
  };

  // Group results
  const stocks = results.filter((r) => r.type === 'stock');
  const funds = results.filter((r) => r.type === 'fund');

  return (
    <div className="relative w-full max-w-xl z-50 font-mono text-xs" ref={dropdownRef}>
      <div className="relative">
        <Search className="absolute left-4 top-3.5 h-4 w-4 text-brand-textMuted" />
        <input
          type="text"
          placeholder="Search Stocks or Mutual Funds (e.g. TCS, Reliance, Parag Parikh)..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShowDropdown(true);
          }}
          onFocus={() => setShowDropdown(true)}
          className="w-full pl-11 pr-10 py-3 bg-brand-bg border border-brand-border text-xs text-black dark:text-white placeholder-brand-textMuted focus:outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary transition-all font-mono"
        />
        {loading && (
          <RefreshCw className="absolute right-4 top-3.5 h-4 w-4 text-brand-primary animate-spin" />
        )}
      </div>

      {showDropdown && query.trim().length >= 2 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-brand-surface border border-brand-border shadow-2xl max-h-[380px] overflow-y-auto divide-y divide-brand-border scrollbar z-50">
          
          {/* Stocks Section */}
          {stocks.length > 0 && (
            <div>
              <div className="bg-brand-bg px-4 py-1.5 text-[9px] text-brand-primary font-bold border-b border-brand-border flex items-center gap-1.5 tracking-wider">
                <Cpu className="w-3 h-3" /> EQUITIES
              </div>
              <div className="divide-y divide-brand-border/40">
                {stocks.map((item) => (
                  <button
                    key={item.symbol}
                    onClick={() => handleSelect(item)}
                    className="w-full text-left px-4 py-2.5 hover:bg-brand-border/40 text-black dark:text-white transition-colors flex items-center justify-between gap-3 group"
                  >
                    <span className="truncate group-hover:text-brand-primary transition-colors font-semibold">{item.name}</span>
                    <span className="shrink-0 text-brand-primary bg-brand-bg border border-brand-border/60 px-1.5 py-0.5 font-bold font-mono text-[9px]">
                      {item.symbol}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Mutual Funds Section */}
          {funds.length > 0 && (
            <div>
              <div className="bg-brand-bg px-4 py-1.5 text-[9px] text-brand-primary font-bold border-b border-brand-border flex items-center gap-1.5 tracking-wider">
                <Layers className="w-3 h-3" /> MUTUAL FUNDS
              </div>
              <div className="divide-y divide-brand-border/40">
                {funds.map((item) => (
                  <button
                    key={item.scheme_code}
                    onClick={() => handleSelect(item)}
                    className="w-full text-left px-4 py-2.5 hover:bg-brand-border/40 text-black dark:text-white transition-colors flex items-center justify-between gap-3 group"
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

          {results.length === 0 && !loading && (
            <div className="px-4 py-4 text-center text-brand-textMuted">
              No matching assets found.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
