import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Star, RefreshCw, Cpu, ShieldAlert, Sparkles, XCircle, Search, HelpCircle, AlertCircle } from 'lucide-react';
import { useWatchlist } from '../hooks/useStocks';
import StockLogo from '../components/StockLogo';

export default function StockWatchlist() {
  const navigate = useNavigate();
  const { watchlist, diagnostics, loading, diagLoading, error, fetchWatchlist, removeFromWatchlist, fetchDiagnostics } = useWatchlist();

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  // Trigger diagnostics update once watchlist is loaded or empty
  useEffect(() => {
    if (watchlist.length > 0 && !diagnostics && !diagLoading) {
      fetchDiagnostics();
    }
  }, [watchlist, diagnostics, diagLoading, fetchDiagnostics]);

  const handleStockClick = (symbol) => {
    navigate(`/stocks/detail/${symbol}`);
  };

  const handleRemove = async (e, symbol) => {
    e.stopPropagation();
    try {
      await removeFromWatchlist(symbol);
      // Re-trigger diagnostics update after removal
      if (watchlist.length > 1) {
        fetchDiagnostics();
      }
    } catch (err) {
      console.error("Failed to remove watchlist item", err);
    }
  };

  const pct = (val) => (val !== null && val !== undefined ? `${(val * 100).toFixed(2)}%` : '—');
  const num = (val, dec = 2) => (val !== null && val !== undefined ? val.toFixed(dec) : '—');

  return (
    <div className="space-y-6 sm:space-y-8 pb-20">
      {/* Title */}
      <div className="flex justify-between items-end border-b border-brand-border pb-4 animate-fade-in-up">
        <div>
          <span className="font-mono text-[10px] text-brand-primary tracking-widest uppercase">[PORTFOLIO_WATCHLIST]</span>
          <h1 className="text-3xl font-extrabold text-black dark:text-white tracking-wide uppercase font-display mt-1">AI WATCHLIST DIAGNOSTICS</h1>
        </div>
        <span className="font-mono text-[10px] text-brand-textMuted hidden md:inline">SYSTEM_STATUS: OK // WATCH_SYNCED</span>
      </div>

      {loading ? (
        <div className="border border-brand-border p-16 text-center space-y-4 max-w-2xl mx-auto font-mono bg-brand-surface animate-fade-in-up">
          <RefreshCw className="h-8 w-8 text-brand-primary mx-auto animate-spin" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Loading Watchlist...</h3>
        </div>
      ) : error ? (
        <div className="border border-brand-border p-16 text-center space-y-4 max-w-2xl mx-auto font-mono bg-brand-surface animate-fade-in-up">
          <AlertCircle className="h-8 w-8 text-brand-danger mx-auto" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Failed to Load</h3>
          <p className="text-brand-textMuted text-xs">{error}</p>
        </div>
      ) : watchlist.length === 0 ? (
        <div className="border border-brand-border p-16 text-center space-y-4 max-w-2xl mx-auto font-mono bg-brand-surface animate-fade-in-up">
          <Star className="h-12 w-12 text-brand-primary opacity-30 mx-auto animate-pulse-subtle" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Watchlist is Empty</h3>
          <p className="text-brand-textMuted text-xs leading-relaxed max-w-md mx-auto">
            Your equity watch list has no saved items. Go to the dashboard or search terminal and add stocks like **TCS**, **Reliance**, or **HAL** to track diagnostics.
          </p>
          <button
            onClick={() => navigate('/stocks')}
            className="bg-brand-primary hover:bg-brand-primaryHover text-black text-[10px] font-bold px-5 py-2.5 transition-colors border border-brand-primary inline-flex items-center gap-1.5"
          >
            <Search className="h-3.5 w-3.5" /> Search Seeded Stocks
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Saved watchlist grid */}
          <div 
            className="lg:col-span-7 space-y-4 animate-fade-in-up"
            style={{ animationDelay: '50ms' }}
          >
            <div className="flex justify-between items-center border-b border-brand-border pb-2">
              <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider">Watchlisted Positions</h3>
              <span className="font-mono text-[9px] text-brand-textMuted uppercase">Positions Count: {watchlist.length}</span>
            </div>

            <div className="bg-brand-surface border border-brand-border shadow-2xl divide-y divide-brand-border">
              {watchlist.map((s) => (
                <div
                  key={s.symbol}
                  onClick={() => handleStockClick(s.symbol)}
                  className="p-4 hover:bg-brand-border/20 transition-colors cursor-pointer flex items-center justify-between gap-4 group"
                >
                  <div className="flex items-center gap-3 min-w-0 pr-3">
                    <StockLogo symbol={s.symbol} size="sm" />
                    <div className="truncate">
                      <span className="font-bold text-xs text-brand-primary block group-hover:underline">{s.symbol}</span>
                      <span className="text-[10px] text-brand-textMuted truncate block font-sans">{s.company_name}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 sm:gap-6 font-mono text-[10px] shrink-0 text-right">
                    <div>
                      <span className="text-brand-textMuted block text-[8px] uppercase font-bold">1Y return</span>
                      <span className="text-brand-success font-bold">{pct(s.cagr_1y)}</span>
                    </div>
                    <div className="hidden sm:block">
                      <span className="text-brand-textMuted block text-[8px] uppercase font-bold">PE Ratio</span>
                      <span className="text-black dark:text-white font-bold">{num(s.pe_ratio, 1)}</span>
                    </div>
                    <div className="bg-brand-bg px-2.5 py-1 border border-brand-border/60 rounded flex flex-col items-center min-w-[42px]">
                      <span className="text-[7px] text-brand-textMuted uppercase font-bold">ALPHA</span>
                      <span className="text-brand-primary font-bold text-xs">{s.alpha_score ? Math.round(s.alpha_score) : '—'}</span>
                    </div>
                    <button
                      onClick={(e) => handleRemove(e, s.symbol)}
                      className="text-brand-textMuted hover:text-brand-danger transition-colors p-2 min-h-[44px] min-w-[44px] flex items-center justify-center"
                      aria-label="Remove from watchlist"
                    >
                      <XCircle className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Diagnostics Briefing Panel */}
          <div 
            className="lg:col-span-5 border border-brand-border bg-brand-surface shadow-2xl p-5 sm:p-6 flex flex-col justify-between animate-fade-in-up"
            style={{ animationDelay: '100ms' }}
          >
            <div>
              <div className="flex justify-between items-center border-b border-brand-border pb-3">
                <div className="flex items-center gap-2 text-brand-primary">
                  <Cpu className="h-4 w-4 animate-pulse-subtle" />
                  <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">AI Portfolio Diagnostics</h3>
                </div>
                <button
                  onClick={fetchDiagnostics}
                  disabled={diagLoading}
                  className="p-1 border border-brand-border hover:border-brand-primary text-brand-primary disabled:opacity-40 flex items-center justify-center"
                  title="Force Diagnostics Refresh"
                >
                  <RefreshCw className={`h-3 w-3 ${diagLoading ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {diagLoading ? (
                <div className="py-24 text-center space-y-3 font-mono text-brand-textMuted">
                  <RefreshCw className="h-6 w-6 mx-auto animate-spin text-brand-primary" />
                  <p className="text-[9px] uppercase tracking-wider animate-pulse">Running cognitive diversification models...</p>
                </div>
              ) : diagnostics ? (
                <div className="space-y-5 pt-4 font-mono text-xs">
                  {/* Score */}
                  <div className="flex items-center justify-between bg-brand-bg border border-brand-border p-3">
                    <span className="text-[9px] text-brand-textMuted uppercase font-bold font-display">Watchlist Health Score</span>
                    <span className="text-xl font-bold text-brand-primary">{diagnostics.health_score}/100</span>
                  </div>

                  {/* Summary */}
                  <div className="space-y-1">
                    <span className="text-[9px] text-brand-primary uppercase font-bold font-display">[Aggregate Health Summary]</span>
                    <p className="text-brand-textMuted leading-relaxed font-sans">{diagnostics.ai_summary}</p>
                  </div>

                  {/* Upgraded Diagnoses List */}
                  <div className="space-y-4 pt-2 border-t border-brand-border/40">
                    <div className="space-y-1">
                      <span className="text-[9px] text-brand-success uppercase font-bold font-display flex items-center gap-1.5">
                        <Sparkles className="h-3 w-3" /> Strongest Position
                      </span>
                      <p className="text-brand-textMuted font-sans pl-4 border-l border-brand-success/30">{diagnostics.strongest_position}</p>
                    </div>

                    <div className="space-y-1">
                      <span className="text-[9px] text-brand-danger uppercase font-bold font-display flex items-center gap-1.5">
                        <ShieldAlert className="h-3 w-3" /> Weakest Link
                      </span>
                      <p className="text-brand-textMuted font-sans pl-4 border-l border-brand-danger/30">{diagnostics.weakest_position}</p>
                    </div>

                    <div className="space-y-1">
                      <span className="text-[9px] text-brand-primary uppercase font-bold font-display flex items-center gap-1.5">
                        <Cpu className="h-3 w-3" /> Risk Concentration
                      </span>
                      <p className="text-brand-textMuted font-sans pl-4 border-l border-brand-primary/30">{diagnostics.risk_concentration}</p>
                    </div>

                    <div className="space-y-1">
                      <span className="text-[9px] text-brand-warning uppercase font-bold font-display flex items-center gap-1.5">
                        <Star className="h-3 w-3 animate-pulse-subtle" /> Sector Exposure Balance
                      </span>
                      <p className="text-brand-textMuted font-sans pl-4 border-l border-brand-warning/30">{diagnostics.sector_exposure}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-20 text-center text-brand-textMuted font-mono text-xs">
                  <HelpCircle className="h-6 w-6 opacity-30 mx-auto mb-2 text-brand-primary" />
                  <p>Click the refresh icon to compile portfolio diagnostics.</p>
                </div>
              )}
            </div>

            <div className="text-[8px] font-mono text-brand-textMuted pt-4 border-t border-brand-border/40">
              [GENERATOR: Llama-3.3-70b-versatile // COMPILED: RAG_DIAGNOSTICS]
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
