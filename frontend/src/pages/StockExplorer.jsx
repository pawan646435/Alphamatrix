import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Filter, ChevronDown, ChevronUp, AlertCircle, RefreshCw } from 'lucide-react';
import { useGetStocks } from '../hooks/useStocks';
import StockLogo from '../components/StockLogo';

export default function StockExplorer() {
  const navigate = useNavigate();

  // Filter states
  const [sector, setSector] = useState('');
  const [minCagr, setMinCagr] = useState('');
  const [minRoe, setMinRoe] = useState('');
  const [maxDebtEquity, setMaxDebtEquity] = useState('');
  const [maxPe, setMaxPe] = useState('');
  
  // Sort states
  const [sortBy, setSortBy] = useState('alpha_score');
  const [sortOrder, setSortOrder] = useState('desc');

  const { stocks, loading, fetchStocks } = useGetStocks();

  // Fetch stocks based on filters
  const loadStocks = React.useCallback(() => {
    fetchStocks({
      sector: sector || undefined,
      min_cagr_3y: minCagr || undefined,
      min_roe: minRoe || undefined,
      max_debt_equity: maxDebtEquity || undefined,
      max_pe_ratio: maxPe || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
    });
  }, [fetchStocks, sector, minCagr, minRoe, maxDebtEquity, maxPe, sortBy, sortOrder]);

  useEffect(() => {
    loadStocks();
  }, [loadStocks]);

  // Toggle sorting
  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const handleRowClick = (symbol) => {
    navigate(`/stocks/detail/${symbol}`);
  };

  // Render sorting arrows
  const renderSortIcon = (field) => {
    if (sortBy !== field) return null;
    return sortOrder === 'asc' ? (
      <ChevronUp className="h-3.5 w-3.5 inline text-brand-primary ml-1" />
    ) : (
      <ChevronDown className="h-3.5 w-3.5 inline text-brand-primary ml-1" />
    );
  };

  const pct = (val) => (val !== null && val !== undefined ? `${(val * 100).toFixed(2)}%` : '—');
  const num = (val, dec = 2) => (val !== null && val !== undefined ? val.toFixed(dec) : '—');

  return (
    <div className="space-y-6 sm:space-y-8 pb-20">
      {/* Title */}
      <div className="flex justify-between items-end border-b border-brand-border pb-4 animate-fade-in-up">
        <div>
          <span className="font-mono text-[10px] text-brand-primary tracking-widest uppercase">[STORE_EXPLORER]</span>
          <h1 className="text-3xl font-extrabold text-black dark:text-white tracking-wide uppercase font-display mt-1">QUANTITATIVE EQUITIES MATRIX</h1>
        </div>
        <span className="font-mono text-[10px] text-brand-textMuted hidden md:inline">SYSTEM_STATUS: OK // STABLE_STATE</span>
      </div>

      {/* Query Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/*Traditional Filter Panel */}
        <div 
          className="lg:col-span-12 terminal-card shadow-xl space-y-4 animate-fade-in-up"
          style={{ animationDelay: '50ms' }}
        >
          <div className="flex items-center gap-2 text-brand-primary">
            <Filter className="h-4 w-4" />
            <h3 className="text-[10px] font-bold text-black dark:text-white uppercase tracking-wider font-display">System Quantitative Filters</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4 font-mono">
            <div className="space-y-1">
              <label className="text-[9px] text-brand-textMuted font-bold uppercase">Sector</label>
              <select
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="w-full bg-brand-bg border border-brand-border rounded-none px-2 py-2 min-h-[40px] text-[10px] text-black dark:text-white focus:outline-none"
              >
                <option value="">All Sectors</option>
                <option value="IT">IT</option>
                <option value="Banking">Banking</option>
                <option value="Auto">Auto</option>
                <option value="Defence">Defence</option>
                <option value="Energy">Energy</option>
                <option value="FMCG">FMCG</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-[9px] text-brand-textMuted font-bold uppercase">Min CAGR 3Y (%)</label>
              <input
                type="number"
                placeholder="e.g. 15"
                value={minCagr}
                onChange={(e) => setMinCagr(e.target.value)}
                className="w-full bg-brand-bg border border-brand-border rounded-none px-2.5 py-2 min-h-[40px] text-[10px] text-black dark:text-white focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[9px] text-brand-textMuted font-bold uppercase">Min ROE (%)</label>
              <input
                type="number"
                placeholder="e.g. 20"
                value={minRoe}
                onChange={(e) => setMinRoe(e.target.value)}
                className="w-full bg-brand-bg border border-brand-border rounded-none px-2.5 py-2 min-h-[40px] text-[10px] text-black dark:text-white focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[9px] text-brand-textMuted font-bold uppercase">Max Debt/Equity</label>
              <input
                type="number"
                step="0.1"
                placeholder="e.g. 0.5"
                value={maxDebtEquity}
                onChange={(e) => setMaxDebtEquity(e.target.value)}
                className="w-full bg-brand-bg border border-brand-border rounded-none px-2.5 py-2 min-h-[40px] text-[10px] text-black dark:text-white focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[9px] text-brand-textMuted font-bold uppercase">Max P/E Ratio</label>
              <input
                type="number"
                placeholder="e.g. 30"
                value={maxPe}
                onChange={(e) => setMaxPe(e.target.value)}
                className="w-full bg-brand-bg border border-brand-border rounded-none px-2.5 py-2 min-h-[40px] text-[10px] text-black dark:text-white focus:outline-none"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Grid Matrix Table */}
      <div 
        className="bg-brand-surface border border-brand-border shadow-2xl overflow-hidden animate-fade-in-up"
        style={{ animationDelay: '150ms' }}
      >
        <div className="overflow-x-auto scrollbar">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-brand-bg border-b border-brand-border text-[10px] text-brand-textMuted font-bold uppercase tracking-wider font-mono">
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary transition-colors" onClick={() => handleSort('symbol')}>
                  Symbol {renderSortIcon('symbol')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary transition-colors" onClick={() => handleSort('company_name')}>
                  Company Name {renderSortIcon('company_name')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary transition-colors" onClick={() => handleSort('sector')}>
                  Sector {renderSortIcon('sector')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('cagr_1y')}>
                  1Y Return {renderSortIcon('cagr_1y')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('cagr_3y')}>
                  3Y CAGR {renderSortIcon('cagr_3y')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('pe_ratio')}>
                  P/E Ratio {renderSortIcon('pe_ratio')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('roe')}>
                  ROE {renderSortIcon('roe')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('beta')}>
                  Beta {renderSortIcon('beta')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('alpha_score')}>
                  Alpha Score {renderSortIcon('alpha_score')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border text-[11px] text-black dark:text-white font-mono">
              {loading ? (
                <tr>
                  <td colSpan="9" className="py-16 text-center text-brand-textMuted">
                    <RefreshCw className="h-6 w-6 mx-auto animate-spin text-brand-primary" />
                    <p className="mt-3 text-[10px] font-mono">PROCESSING QUANTITATIVE FILTER PIPELINE...</p>
                  </td>
                </tr>
              ) : stocks.length === 0 ? (
                <tr>
                  <td colSpan="9" className="py-12 text-center text-brand-textMuted font-mono">
                    <AlertCircle className="h-6 w-6 mx-auto opacity-35 text-brand-primary" />
                    <p className="mt-2 text-[10px]">NO EQUITIES IN RELATIONAL STORE MATCH PARAMETERS</p>
                  </td>
                </tr>
              ) : (
                stocks.map((s) => (
                  <tr
                    key={s.symbol}
                    onClick={() => handleRowClick(s.symbol)}
                    className="hover:bg-brand-border/20 transition-colors cursor-pointer"
                  >
                    <td className="py-4 px-6 font-bold text-brand-primary">
                      {s.symbol}
                    </td>
                    <td className="py-4 px-6 font-semibold text-black dark:text-white max-w-sm truncate font-sans">
                      <div className="flex items-center gap-2.5 truncate">
                        <StockLogo symbol={s.symbol} size="sm" />
                        <span className="truncate">{s.company_name}</span>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <span className="text-[9px] font-bold px-2 py-0.5 border bg-brand-primary/10 text-brand-primary border-brand-primary/20">
                        [{s.sector.toUpperCase()}]
                      </span>
                    </td>
                    <td className="py-4 px-6 text-right font-bold text-brand-success">
                      {pct(s.cagr_1y)}
                    </td>
                    <td className="py-4 px-6 text-right text-black dark:text-white">
                      {pct(s.cagr_3y)}
                    </td>
                    <td className="py-4 px-6 text-right text-black dark:text-white font-semibold">
                      {num(s.pe_ratio, 1)}
                    </td>
                    <td className="py-4 px-6 text-right text-brand-success">
                      {s.roe ? `${s.roe.toFixed(1)}%` : '—'}
                    </td>
                    <td className="py-4 px-6 text-right text-brand-warning">
                      {num(s.beta)}
                    </td>
                    <td className="py-4 px-6 text-right font-bold text-brand-primary">
                      {s.alpha_score ? Math.round(s.alpha_score) : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
