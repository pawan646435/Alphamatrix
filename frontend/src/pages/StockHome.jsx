import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TrendingUp, Star, Cpu, Layers, ArrowUpRight, Activity, Target, Info } from 'lucide-react';
import { useStockAIChat } from '../hooks/useStocks';
import { useStockList, useMarketRegime, useBacktestSummary } from '../hooks/useQueries';
import StockRiskScatterplot from '../components/charts/StockRiskScatterplot';
import GlobalSearch from '../components/GlobalSearch';
import { CardGridSkeleton } from '../components/skeletons/Skeletons';
import FloatingChatAssistant from '../components/FloatingChatAssistant';

export default function StockHome() {
  const navigate = useNavigate();
  const { data: stocks = [], isLoading: stocksLoading } = useStockList();
  const { data: marketRegime, isLoading: regimeLoading } = useMarketRegime();
  const { data: backtestSummary } = useBacktestSummary();
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessage, setChatMessage] = useState('');
  
  const { messages, loading: chatLoading, sendMessage } = useStockAIChat();

  const handleSectorClick = (sectorKey) => {
    navigate(`/stocks/sector/${sectorKey}`);
  };

  const handleSendChat = (e) => {
    e.preventDefault();
    if (!chatMessage.trim()) return;
    sendMessage(chatMessage, null, messages);
    setChatMessage('');
  };

  // Sector list configuration
  const sectors = [
    { key: 'BANKING', name: 'Banking', desc: 'Financial engines driving retail and industrial expansion.', codeCount: 'HDFCBANK, ICICIBANK' },
    { key: 'IT', name: 'IT', desc: 'Software exports and enterprise digital transformation leaders.', codeCount: 'TCS, INFY' },
    { key: 'AUTO', name: 'Auto', desc: 'Commercial and passenger vehicle compounding growth.', codeCount: 'TATAMOTORS, M&M' },
    { key: 'ENERGY', name: 'Energy', desc: 'Refining, conglomerates, and green transition powerhouses.', codeCount: 'RELIANCE' },
    { key: 'DEFENCE', name: 'Defence', desc: 'Indigenization mandates and specialized aerospace manufacturers.', codeCount: 'HAL, BEL, BDL, MAZDOCK' },
    { key: 'FMCG', name: 'FMCG', desc: 'Resilient consumer staples and diversified conglomerates.', codeCount: 'HINDUNILVR, ITC, NESTLEIND' },
    { key: 'PHARMA', name: 'Pharma', desc: 'Pioneering healthcare, generic formulations, and active ingredients.', codeCount: 'SUNPHARMA, DRREDDY' },
    { key: 'METALS', name: 'Metals', desc: 'Foundational materials driving steel, manufacturing, and heavy extraction.', codeCount: 'TATASTEEL, JSWSTEEL' },
    { key: 'INFRASTRUCTURE', name: 'Infrastructure', desc: 'Civil engineering, roads, ports, and national building structures.', codeCount: 'LT' },
    { key: 'CHEMICALS', name: 'Chemicals', desc: 'Specialty chemicals, adhesives, and raw industrial compounds.', codeCount: 'PIDILITIND' },
    { key: 'CONSUMER_DURABLES', name: 'Consumer Durables', desc: 'Premium consumer goods, electronics, and lifestyle compounders.', codeCount: 'TITAN, VOLTAS' },
    { key: 'REALTY', name: 'Realty', desc: 'Residential real estate and commercial property developers.', codeCount: 'DLF' },
    { key: 'TELECOM', name: 'Telecom', desc: 'High-speed network backbones and digital infrastructure.', codeCount: 'BHARTIARTL' },
    { key: 'PSU', name: 'PSU', desc: 'Public sector enterprises spanning energy, mining, and state utilities.', codeCount: 'ONGC, NTPC' },
    { key: 'CAPITAL_GOODS', name: 'Capital Goods', desc: 'Heavy machinery and equipment powering industrial capacity.', codeCount: 'BHEL' },
  ];

  // Calculate statistics
  const stats = React.useMemo(() => {
    if (!stocks.length) return { avgCagr: '0.00%', peakAlpha: '0.00', activeCount: 0 };
    const validCagrs = stocks.filter(s => s.cagr_3y !== null).map(s => s.cagr_3y);
    const avgCagr = validCagrs.length ? (validCagrs.reduce((a, b) => a + b, 0) / validCagrs.length) * 100 : 0;
    const alphas = stocks.filter(s => s.alpha_score !== null).map(s => s.alpha_score);
    const peakAlpha = alphas.length ? Math.max(...alphas) : 0;
    
    return {
      avgCagr: `${avgCagr.toFixed(2)}%`,
      peakAlpha: peakAlpha.toFixed(1),
      activeCount: stocks.length
    };
  }, [stocks]);

  return (
    <div className="space-y-8 sm:space-y-12 pb-20">
      {/* Hero Display Panel */}
      <div
        className="relative border border-brand-border p-5 sm:p-8 md:p-12 overflow-hidden flex flex-col items-center text-center animate-fade-in-up bg-brand-surface"
      >
        {/* Subtle grid accent inside hero */}
        <div className="absolute inset-0 bg-gradient-to-b from-brand-primary/5 via-transparent to-brand-primary/5 opacity-40 pointer-events-none" />

        <div className="flex items-center gap-1.5 px-3 py-1 bg-brand-primary/10 border border-brand-primary/40 text-brand-primary text-[9px] sm:text-[10px] font-mono uppercase tracking-wider mb-3 sm:mb-5 animate-pulse-subtle">
          <Cpu className="h-3 w-3" /> EQUITIES INTEL CORE [LLAMA_3.3_70B_VERSATILE]
        </div>

        <h1 className="text-[1.65rem] sm:text-4xl md:text-5xl font-extrabold text-black dark:text-white tracking-tight leading-[1.15] sm:leading-none max-w-4xl font-display uppercase">
          EVALUATE EQUITIES WITH <span className="text-brand-primary">QUANTITATIVE RIGOR</span>
        </h1>

        <p className="text-brand-textMuted text-xs sm:text-sm md:text-base max-w-2xl mt-2.5 sm:mt-4 leading-relaxed font-sans">
          Analyze valuation multiples, multi-factor Alpha Scores, and historical returns across major NIFTY equities. Powered by Llama 3.3.
        </p>

        {/* Master Search Input */}
        <div className="mt-4 sm:mt-8 w-full flex justify-center">
          <GlobalSearch />
        </div>
      </div>

      {/* Analytics Overview Cards */}
      {stocksLoading ? (
        <CardGridSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
          <div className="terminal-card flex items-center gap-4 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
            <div className="w-10 h-10 border border-brand-border bg-brand-surface flex items-center justify-center text-brand-primary">
              <Layers className="h-4 w-4" />
            </div>
            <div>
              <p className="text-[10px] text-brand-textMuted uppercase font-bold tracking-wider font-display">EQUITIES MASTERSTORE</p>
              <h3 className="text-xl font-bold text-black dark:text-white mt-0.5 font-mono">{stats.activeCount} seeded</h3>
            </div>
          </div>

          <div className="terminal-card flex items-center gap-4 animate-fade-in-up hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]" style={{ animationDelay: '150ms' }}>
            <div className="w-10 h-10 border border-brand-primary bg-brand-surface flex items-center justify-center text-brand-primary">
              <TrendingUp className="h-4 w-4" />
            </div>
            <div>
              <p className="text-[10px] text-brand-textMuted uppercase font-bold tracking-wider font-display">AVG 3Y STOCKS YIELD</p>
              <h3 className="text-xl font-bold text-black dark:text-white mt-0.5 font-mono">{stats.avgCagr}</h3>
            </div>
          </div>

          <div className="terminal-card flex items-center gap-4 animate-fade-in-up hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]" style={{ animationDelay: '200ms' }}>
            <div className="w-10 h-10 border border-brand-primary bg-brand-surface flex items-center justify-center text-brand-primary">
              <Star className="h-4 w-4" />
            </div>
            <div>
              <p className="text-[10px] text-brand-textMuted uppercase font-bold tracking-wider font-display">PEAK ALPHA SCORE</p>
              <h3 className="text-xl font-bold text-black dark:text-white mt-0.5 font-mono">{stats.peakAlpha}/100</h3>
            </div>
          </div>

          <div className="terminal-card flex items-center gap-4 animate-fade-in-up hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]" style={{ animationDelay: '250ms' }}>
            <div className="w-10 h-10 border border-brand-primary bg-brand-surface flex items-center justify-center text-brand-primary shrink-0">
              <Activity className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[10px] text-brand-textMuted uppercase font-bold tracking-wider font-display">MARKET REGIME</p>
              {regimeLoading ? (
                <p className="text-[10px] font-mono text-brand-textMuted mt-0.5">Calculating...</p>
              ) : marketRegime ? (
                <div className="space-y-0.5">
                  <h3 className="text-sm font-bold text-black dark:text-white font-mono flex items-center gap-1.5 leading-none">
                    <span className={marketRegime.regime === 'RISK ON' ? 'text-green-500' : marketRegime.regime === 'RISK OFF' ? 'text-red-500' : 'text-yellow-500'}>
                      {marketRegime.regime}
                    </span>
                    <span className="text-[9px] font-mono text-brand-textMuted font-normal">({marketRegime.confidence}%)</span>
                  </h3>
                  <p className="text-[9px] text-brand-textMuted leading-tight truncate font-sans hover:text-clip hover:whitespace-normal" title={marketRegime.explanation}>
                    {marketRegime.explanation}
                  </p>
                </div>
              ) : (
                <p className="text-[10px] font-mono text-brand-textMuted mt-0.5">Unavailable</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Verdict Accuracy Engine — Backtesting Results */}
      {backtestSummary && backtestSummary.status === 'completed' && (
        <div className="border border-brand-border bg-brand-surface p-5 sm:p-6 animate-fade-in-up" style={{ animationDelay: '200ms' }}>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-brand-primary" />
              <h2 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider">Verdict Accuracy Engine v3</h2>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-[9px] text-brand-textMuted bg-brand-bg border border-brand-border px-2 py-0.5">
                BENCHMARK: NIFTY 50 · 12% p.a.
              </span>
              <span className="font-mono text-[10px] font-bold text-brand-primary">
                {backtestSummary.overall_win_rate_365d != null ? `${backtestSummary.overall_win_rate_365d}% Win Rate` : ''}
              </span>
            </div>
          </div>
          {/* Independence disclaimer — the BUY/HOLD/AVOID buckets below are
              labeled by a separate price-momentum-only backtest model (see
              services/backtesting.py), not by the Alpha Score model or the
              AI briefing rubric that drive the live verdicts shown on stock
              pages. Accuracy % here should not be read as "the platform's
              live verdicts are right X% of the time". */}
          <div
            className="flex items-start gap-1.5 mb-5 text-[9px] font-mono text-brand-warning/90 uppercase tracking-wider"
            title="These accuracy numbers come from a separate historical backtest model (price momentum, CAGR, drawdown against past price data only) — not from the Alpha Score model or the live AI briefing rubric used elsewhere on this platform. They measure how a differently-weighted, price-only model would have performed, not how today's actual AI/Alpha Score verdicts have performed."
          >
            <Info className="h-3 w-3 mt-[1px] flex-shrink-0" />
            <span>Independent Technical Backtest — does not evaluate today's AI or Alpha Score verdicts</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* BUY / STRONG BUY */}
            {backtestSummary.verdict_accuracy?.BUY_STRONG_BUY && (
              <div className="border border-brand-success/30 bg-brand-success/5 p-4 rounded">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-[9px] uppercase font-bold text-brand-success tracking-wider">BUY Verdicts</span>
                  <span className="font-mono text-[9px] text-brand-textMuted">{backtestSummary.verdict_accuracy.BUY_STRONG_BUY.count} trades</span>
                </div>
                <div className="text-2xl font-bold font-mono text-brand-success">
                  {backtestSummary.verdict_accuracy.BUY_STRONG_BUY.accuracy_365d != null
                    ? `${backtestSummary.verdict_accuracy.BUY_STRONG_BUY.accuracy_365d}%`
                    : '—'}
                </div>
                <div className="text-[10px] text-brand-textMuted mt-1">
                  Outperformed Nifty 50 at 1Y horizon
                </div>
                {backtestSummary.verdict_accuracy.BUY_STRONG_BUY.avg_return_365d != null && (
                  <div className="font-mono text-[10px] text-brand-success mt-1">
                    Avg return: +{backtestSummary.verdict_accuracy.BUY_STRONG_BUY.avg_return_365d.toFixed(1)}%
                  </div>
                )}
              </div>
            )}

            {/* HOLD */}
            {backtestSummary.verdict_accuracy?.HOLD && (
              <div className="border border-brand-warning/30 bg-brand-warning/5 p-4 rounded">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-[9px] uppercase font-bold text-brand-warning tracking-wider">HOLD Verdicts</span>
                  <span className="font-mono text-[9px] text-brand-textMuted">{backtestSummary.verdict_accuracy.HOLD.count} trades</span>
                </div>
                <div className="text-2xl font-bold font-mono text-brand-warning">
                  {backtestSummary.verdict_accuracy.HOLD.accuracy_365d != null
                    ? `${backtestSummary.verdict_accuracy.HOLD.accuracy_365d}%`
                    : '—'}
                </div>
                <div className="text-[10px] text-brand-textMuted mt-1">
                  Within ±5% of benchmark at 1Y
                </div>
                {backtestSummary.verdict_accuracy.HOLD.avg_return_365d != null && (
                  <div className="font-mono text-[10px] text-brand-warning mt-1">
                    Avg return: {backtestSummary.verdict_accuracy.HOLD.avg_return_365d.toFixed(1)}%
                  </div>
                )}
              </div>
            )}

            {/* AVOID / REDUCE */}
            {backtestSummary.verdict_accuracy?.AVOID_REDUCE && (
              <div className="border border-brand-danger/30 bg-brand-danger/5 p-4 rounded">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-[9px] uppercase font-bold text-brand-danger tracking-wider">AVOID Verdicts</span>
                  <span className="font-mono text-[9px] text-brand-textMuted">{backtestSummary.verdict_accuracy.AVOID_REDUCE.count} trades</span>
                </div>
                <div className="text-2xl font-bold font-mono text-brand-danger">
                  {backtestSummary.verdict_accuracy.AVOID_REDUCE.accuracy_365d != null
                    ? `${backtestSummary.verdict_accuracy.AVOID_REDUCE.accuracy_365d}%`
                    : '—'}
                </div>
                <div className="text-[10px] text-brand-textMuted mt-1">
                  Correctly avoided underperformers
                </div>
                {backtestSummary.verdict_accuracy.AVOID_REDUCE.avg_return_365d != null && (
                  <div className="font-mono text-[10px] text-brand-danger mt-1">
                    Avg return: {backtestSummary.verdict_accuracy.AVOID_REDUCE.avg_return_365d.toFixed(1)}%
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer stats */}
          <div className="flex flex-wrap gap-6 mt-4 pt-4 border-t border-brand-border/40 font-mono text-[10px] text-brand-textMuted">
            <span>Evaluated: <strong className="text-black dark:text-white">{backtestSummary.evaluated_stocks}</strong> stocks</span>
            <span>90d Win Rate: <strong className="text-black dark:text-white">{backtestSummary.t90_win_rate}%</strong></span>
            {backtestSummary.avg_max_drawdown_pct != null && (
              <span>Avg Max DD: <strong className="text-brand-danger">{backtestSummary.avg_max_drawdown_pct}%</strong></span>
            )}
          </div>
        </div>
      )}

      {/* Middle Grid: Sector Matrix cards and Scatterplot */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Sectors list */}
        <div className="lg:col-span-5 space-y-4 animate-fade-in-up" style={{ animationDelay: '250ms' }}>
          <div className="flex items-center justify-between border-b border-brand-border pb-2">
            <h2 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider">Sector Intelligence Matrix</h2>
            <span className="font-mono text-[10px] text-brand-textMuted">[SECTORS: 6]</span>
          </div>
          
          <div className="grid grid-cols-1 gap-3">
            {sectors.map((sec) => (
              <button
                key={sec.key}
                onClick={() => handleSectorClick(sec.key)}
                className="w-full text-left p-4 border border-brand-border hover:border-brand-primary text-brand-primary bg-brand-primary/5 hover:shadow-[0_0_15px_rgba(197,168,128,0.15)] transition-all duration-200 hover:-translate-x-1 flex justify-between items-center group"
              >
                <div className="space-y-1 min-w-0 pr-3">
                  <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wide flex items-center gap-1.5">
                    {sec.name} <ArrowUpRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </h3>
                  <p className="text-[10px] text-brand-textMuted truncate font-sans">{sec.desc}</p>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-[8px] font-mono bg-brand-bg px-2 py-1 border border-brand-border text-black dark:text-white">
                    {sec.codeCount}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Scatterplot */}
        <div className="lg:col-span-7 min-h-[420px] sm:min-h-[480px] animate-fade-in-up" style={{ animationDelay: '300ms' }}>
          <StockRiskScatterplot stocks={stocks} isLoading={stocksLoading} />
        </div>
      </div>

      <FloatingChatAssistant
        title="EQUITY_ANALYST.EXE"
        emptyStateText="Equity intelligence terminal online. Ask about PE ratios, Beta metrics, or request stock diagnostics."
        placeholder="Ask about TCS vs Infosys, etc..."
        chatOpen={chatOpen}
        setChatOpen={setChatOpen}
        messages={messages}
        chatLoading={chatLoading}
        chatMessage={chatMessage}
        setChatMessage={setChatMessage}
        onSubmit={handleSendChat}
      />
    </div>
  );
}
