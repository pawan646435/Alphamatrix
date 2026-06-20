import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Filter, Search, ChevronDown, ChevronUp, Sparkles, MessageCircle, AlertCircle, RefreshCw, Layers } from 'lucide-react';
import { useGetFunds, useSemanticQuery } from '../hooks/useFunds';
import FundLogo from '../components/FundLogo';

export default function Explorer() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const categoryParam = searchParams.get('category');

  // Filter states
  const [category, setCategory] = useState(categoryParam || '');
  const [minCagr1y, setMinCagr1y] = useState('');
  const [minCagr, setMinCagr] = useState('');
  const [maxExpense, setMaxExpense] = useState('');
  const [minSharpe, setMinSharpe] = useState('');
  const [maxPe, setMaxPe] = useState('');
  
  // Sort states
  const [sortBy, setSortBy] = useState('cagr_3y');
  const [sortOrder, setSortOrder] = useState('desc');

  // Semantic query state
  const [semanticQueryText, setSemanticQueryText] = useState('');
  const [usingSemantic, setUsingSemantic] = useState(false);

  const { funds, loading: standardLoading, fetchFunds } = useGetFunds();
  const { 
    matchedFunds: aiFunds, 
    parsedFilters, 
    sqlExplanation, 
    loading: aiLoading, 
    executeSemanticQuery,
    setMatchedFunds,
    setParsedFilters
  } = useSemanticQuery();

  // Load initial parameters or change parameters
  useEffect(() => {
    if (categoryParam) {
      setCategory(categoryParam);
    }
  }, [categoryParam]);

  // Fetch standard funds based on filters
  const loadFunds = React.useCallback(() => {
    setUsingSemantic(false);
    fetchFunds({
      category: category || undefined,
      min_cagr_1y: minCagr1y || undefined,
      min_cagr_3y: minCagr || undefined,
      max_expense_ratio: maxExpense || undefined,
      min_sharpe_ratio: minSharpe || undefined,
      max_pe_ratio: maxPe || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
    });
  }, [fetchFunds, category, minCagr1y, minCagr, maxExpense, minSharpe, maxPe, sortBy, sortOrder]);

  useEffect(() => {
    if (!usingSemantic) {
      loadFunds();
    }
  }, [loadFunds, usingSemantic]);

  // Trigger semantic query
  const handleSemanticSearchSubmit = async (e) => {
    e.preventDefault();
    if (!semanticQueryText.trim()) return;
    setUsingSemantic(true);
    await executeSemanticQuery(semanticQueryText);
  };

  // Toggle sorting
  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const handleRowClick = (schemeCode) => {
    navigate(`/detail/${schemeCode}`);
  };

  const handleClearSemantic = () => {
    setUsingSemantic(false);
    setSemanticQueryText('');
    setMatchedFunds([]);
    setParsedFilters(null);
    loadFunds();
  };

  // Render sorting arrows
  const renderSortIcon = (field) => {
    if (sortBy !== field) return null;
    return sortOrder === 'asc' ? <ChevronUp className="h-3.5 w-3.5 inline text-brand-primary ml-1" /> : <ChevronDown className="h-3.5 w-3.5 inline text-brand-primary ml-1" />;
  };

  const activeFunds = usingSemantic ? aiFunds : funds;
  const isLoading = standardLoading || aiLoading;

  return (
    <div className="space-y-8 pb-16">
      {/* Title */}
      <div className="flex justify-between items-end border-b border-brand-border pb-4 animate-fade-in-up">
        <div>
          <span className="font-mono text-[10px] text-brand-primary tracking-widest uppercase">[STORE_EXPLORER]</span>
          <h1 className="text-3xl font-extrabold text-black dark:text-white tracking-wide uppercase font-display mt-1">QUANTITATIVE EXPLORER MATRIX</h1>
        </div>
        <span className="font-mono text-[10px] text-brand-textMuted hidden md:inline">SYSTEM_STATUS: OK // STABLE_STATE</span>
      </div>

      {/* Query Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* NLP Semantic Query Bar */}
        <div 
          className="lg:col-span-8 terminal-card shadow-xl space-y-4 animate-fade-in-up"
          style={{ animationDelay: '50ms' }}
        >
          <div className="flex items-center gap-2 text-brand-primary">
            <Sparkles className="h-4 w-4" />
            <h3 className="text-[10px] font-bold text-black dark:text-white uppercase tracking-wider font-display">Semantic AI NLP Filter</h3>
          </div>
          
          <form onSubmit={handleSemanticSearchSubmit} className="flex gap-2 font-mono">
            <input
              type="text"
              placeholder='e.g., "high-yield mid caps with low risk" or "small caps with sharpe > 1.2"'
              value={semanticQueryText}
              onChange={(e) => setSemanticQueryText(e.target.value)}
              className="flex-1 bg-brand-bg border border-brand-border rounded-none px-4 py-2.5 text-xs text-black dark:text-white focus:outline-none focus:border-brand-primary"
            />
            <button
              type="submit"
              disabled={isLoading}
              className="bg-brand-primary hover:bg-brand-primaryHover disabled:opacity-50 text-black font-extrabold text-[10px] px-5 py-2.5 transition-colors flex items-center gap-1.5 shrink-0 border border-brand-primary"
            >
              Parse & Query
            </button>
          </form>

          {/* Collapsible details of AI parsed outcome */}
          {usingSemantic && parsedFilters && (
            <div className="bg-brand-bg border border-brand-primary/20 p-4 space-y-3 font-mono text-xs">
              <div className="flex justify-between items-center">
                <span className="text-[9px] font-bold text-brand-primary uppercase">Llama 3.3 SQL Parser Metadata</span>
                <button 
                  onClick={handleClearSemantic}
                  className="text-[9px] text-brand-danger hover:underline font-bold"
                >
                  Clear AI Filters [ESC]
                </button>
              </div>
              <p className="text-[11px] text-black dark:text-white italic">"{sqlExplanation}"</p>
              <div className="flex flex-wrap gap-2 text-[10px] text-brand-textMuted font-mono">
                {Object.entries(parsedFilters).map(([k, v]) => v !== null && (
                  <span key={k} className="bg-brand-surface px-2.5 py-1 border border-brand-border">
                    {k}: <span className="text-brand-primary">{String(v)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Traditional Filter Panel */}
        <div 
          className="lg:col-span-4 terminal-card shadow-xl space-y-4 animate-fade-in-up"
          style={{ animationDelay: '100ms' }}
        >
          <div className="flex items-center gap-2 text-brand-primary">
            <Filter className="h-4 w-4" />
            <h3 className="text-[10px] font-bold text-black dark:text-white uppercase tracking-wider font-display">Standard System Filters</h3>
          </div>

          <div className="grid grid-cols-2 gap-3 font-mono">
            <div className="space-y-1">
              <label className="text-[9px] text-brand-textMuted font-bold uppercase">Category</label>
              <select
                value={category}
                onChange={(e) => { setCategory(e.target.value); setUsingSemantic(false); }}
                className="w-full bg-brand-bg border border-brand-border rounded-none px-2 py-1.5 text-[10px] text-black dark:text-white focus:outline-none"
              >
                <option value="">All Categories</option>
                <option value="Large Cap">Large Cap</option>
                <option value="Mid Cap">Mid Cap</option>
                <option value="Small Cap">Small Cap</option>
                <option value="Index">Index</option>
                <option value="Sectoral">Sectoral</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-[9px] text-brand-textMuted font-bold uppercase">Min CAGR 1Y (%)</label>
              <input
                type="number"
                placeholder="e.g. 10"
                value={minCagr1y}
                onChange={(e) => { setMinCagr1y(e.target.value); setUsingSemantic(false); }}
                className="w-full bg-brand-bg border border-brand-border rounded-none px-2.5 py-1.5 text-[10px] text-black dark:text-white focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[9px] text-brand-textMuted font-bold uppercase">Min CAGR 3Y (%)</label>
              <input
                type="number"
                placeholder="e.g. 15"
                value={minCagr}
                onChange={(e) => { setMinCagr(e.target.value); setUsingSemantic(false); }}
                className="w-full bg-brand-bg border border-brand-border rounded-none px-2.5 py-1.5 text-[10px] text-black dark:text-white focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[9px] text-brand-textMuted font-bold uppercase">Min Sharpe</label>
              <input
                type="number"
                step="0.1"
                placeholder="e.g. 1.0"
                value={minSharpe}
                onChange={(e) => { setMinSharpe(e.target.value); setUsingSemantic(false); }}
                className="w-full bg-brand-bg border border-brand-border rounded-none px-2.5 py-1.5 text-[10px] text-black dark:text-white focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[9px] text-brand-textMuted font-bold uppercase">Max P/E</label>
              <input
                type="number"
                placeholder="e.g. 25"
                value={maxPe}
                onChange={(e) => { setMaxPe(e.target.value); setUsingSemantic(false); }}
                className="w-full bg-brand-bg border border-brand-border rounded-none px-2.5 py-1.5 text-[10px] text-black dark:text-white focus:outline-none"
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
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary transition-colors" onClick={() => handleSort('fund_name')}>
                  Fund Name {renderSortIcon('fund_name')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary transition-colors" onClick={() => handleSort('category')}>
                  Category {renderSortIcon('category')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('cagr_1y')}>
                  1Y CAGR {renderSortIcon('cagr_1y')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('cagr_3y')}>
                  3Y CAGR {renderSortIcon('cagr_3y')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('cagr_5y')}>
                  5Y CAGR {renderSortIcon('cagr_5y')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('sharpe_ratio')}>
                  Sharpe {renderSortIcon('sharpe_ratio')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('alpha')}>
                  Alpha {renderSortIcon('alpha')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('pe_ratio')}>
                  P/E Ratio {renderSortIcon('pe_ratio')}
                </th>
                <th className="py-4 px-6 select-none cursor-pointer hover:text-brand-primary text-right transition-colors" onClick={() => handleSort('expense_ratio')}>
                  Exp Ratio {renderSortIcon('expense_ratio')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border text-[11px] text-black dark:text-white font-mono">
              {isLoading ? (
                <tr>
                  <td colSpan="9" className="py-16 text-center text-brand-textMuted">
                    <RefreshCw className="h-6 w-6 mx-auto animate-spin text-brand-primary" />
                    <p className="mt-3 text-[10px] font-mono">PROCESSING ANALYTICS PIPELINE...</p>
                  </td>
                </tr>
              ) : activeFunds.length === 0 ? (
                <tr>
                  <td colSpan="9" className="py-12 text-center text-brand-textMuted font-mono">
                    <AlertCircle className="h-6 w-6 mx-auto opacity-35 text-brand-primary" />
                    <p className="mt-2 text-[10px]">NO ENTRIES IN RELATIONAL STORE MATCH FILTERS</p>
                  </td>
                </tr>
              ) : (
                activeFunds.map((fund) => (
                  <tr
                    key={fund.scheme_code}
                    onClick={() => handleRowClick(fund.scheme_code)}
                    className="hover:bg-brand-border/20 transition-colors cursor-pointer"
                  >
                    <td className="py-4 px-6 font-semibold text-black dark:text-white max-w-sm truncate font-sans">
                      <div className="flex items-center gap-2.5 truncate">
                        <FundLogo fundName={fund.fund_name} size="sm" />
                        <span className="truncate">{fund.fund_name}</span>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <span className={`text-[9px] font-bold px-2 py-0.5 border ${
                        fund.category === 'Large Cap' ? 'bg-indigo-500/5 text-indigo-400 border-indigo-500/20' :
                        fund.category === 'Mid Cap' ? 'bg-brand-primary/10 text-brand-primary border-brand-primary/20' :
                        fund.category === 'Small Cap' ? 'bg-brand-danger/5 text-brand-danger border-brand-danger/20' :
                        fund.category === 'Index' ? 'bg-brand-success/5 text-brand-success border-brand-success/20' :
                        'bg-brand-warning/5 text-brand-warning border-brand-warning/20'
                      }`}>
                        [{fund.category.toUpperCase().replace(' ', '_')}]
                      </span>
                    </td>
                    <td className="py-4 px-6 text-right font-bold text-brand-success">
                      {fund.cagr_1y !== null && fund.cagr_1y !== undefined ? `${(fund.cagr_1y * 100).toFixed(2)}%` : '—'}
                    </td>
                    <td className="py-4 px-6 text-right text-black dark:text-white">
                      {fund.cagr_3y !== null && fund.cagr_3y !== undefined ? `${(fund.cagr_3y * 100).toFixed(2)}%` : '—'}
                    </td>
                    <td className="py-4 px-6 text-right text-brand-textMuted">
                      {fund.cagr_5y !== null && fund.cagr_5y !== undefined ? `${(fund.cagr_5y * 100).toFixed(2)}%` : '—'}
                    </td>
                    <td className="py-4 px-6 text-right font-bold text-brand-primary">
                      {fund.sharpe_ratio !== null && fund.sharpe_ratio !== undefined ? fund.sharpe_ratio.toFixed(2) : '—'}
                    </td>
                    <td className="py-4 px-6 text-right text-brand-warning font-semibold">
                      {fund.alpha !== null && fund.alpha !== undefined ? `${(fund.alpha * 100).toFixed(2)}%` : '—'}
                    </td>
                    <td className="py-4 px-6 text-right text-black dark:text-white">
                      {fund.pe_ratio !== null && fund.pe_ratio !== undefined ? fund.pe_ratio.toFixed(1) : '—'}
                    </td>
                    <td className="py-4 px-6 text-right text-brand-textMuted">
                      {fund.expense_ratio !== null && fund.expense_ratio !== undefined ? `${fund.expense_ratio.toFixed(2)}%` : '—'}
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
