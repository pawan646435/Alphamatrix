import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Star, Cpu, MessageSquare, Plus, Check, Zap, Activity, ShieldCheck, ShieldAlert, AlertTriangle, Target } from 'lucide-react';
import { useStockAIChat, useWatchlist } from '../hooks/useStocks';
import { useStockDetail, useWatchlistQuery, getStandardizedSector, useStockBacktest, useStockMeta, useStockMetrics, useStockChart, useStockBriefing, useStockNews } from '../hooks/useQueries';
import { useQueryClient } from '@tanstack/react-query';
import InteractiveChart from '../components/charts/InteractiveChart';
import StockLogo from '../components/StockLogo';
import AnalystResponseCard from '../components/AnalystResponseCard';

export default function StockDetail() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  
  const queryClient = useQueryClient();
  const cachedStock = queryClient.getQueryData(['stocks', 'detail', symbol, 'meta']);
  
  const isDiscovering = !cachedStock || cachedStock?.status === 'discovering';
  
  // 1. Fetch metadata first (fast)
  const { data: metaData, isLoading: metaLoading, error: metaError } = useStockMeta(symbol, {
    staleTime: isDiscovering ? 0 : 86400000,
    refetchInterval: (query) => {
      const data = query?.state?.data;
      return (data?.status === 'discovering' || !data) ? 3000 : false;
    }
  });
  
  const currentIsDiscovering = metaLoading || !metaData || metaData?.status === 'discovering';
  
  // 2. Fetch metrics in parallel
  const { data: metricsData, isLoading: metricsLoading } = useStockMetrics(symbol, {
    enabled: !currentIsDiscovering && !!symbol,
    staleTime: 86400000
  });
  
  const [chartRange, setChartRange] = useState('3Y');
  const chartPeriod = (chartRange === '5Y' ? '5y' : chartRange === 'MAX' ? 'max' : '3y');
  
  // 3. Fetch chart in parallel
  const { data: chartData, isLoading: chartLoading } = useStockChart(symbol, chartPeriod, {
    enabled: !currentIsDiscovering && !!symbol,
    staleTime: 3600000
  });
  
  // 4. Fetch briefing in parallel
  const { data: briefingData, isLoading: briefingFetchLoading } = useStockBriefing(symbol, {
    enabled: !currentIsDiscovering && !!symbol,
    staleTime: 86400000,
    refetchInterval: (query) => {
      const data = query?.state?.data;
      return (data?.status === 'generating' || !data?.ai_summary) ? 3000 : false;
    }
  });
  
  // 5. Fetch yfinance news in parallel
  const { data: newsData } = useStockNews(symbol, {
    enabled: !currentIsDiscovering && !!symbol,
    staleTime: 900000
  });
  
  const loading = metaLoading;
  const stockError = metaError;
  
  const { data: watchlist = [] } = useWatchlistQuery();
  const { addToWatchlist, removeFromWatchlist } = useWatchlist();
  
  const [chatMessage, setChatMessage] = useState('');
  const { messages, loading: chatLoading, sendMessage } = useStockAIChat();

  const [timings, setTimings] = useState({
    start: null,
    resolution: null,
    metadata: null,
    historical: null,
    fundamentals: null,
    alphaScore: null,
    aiReport: null,
    news: null,
    total: null
  });
  const [showPerfPanel, setShowPerfPanel] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    setTimings({
      start: performance.now(),
      resolution: null,
      metadata: null,
      historical: null,
      fundamentals: null,
      alphaScore: null,
      aiReport: null,
      news: null,
      total: null
    });
  }, [symbol]);

  useEffect(() => {
    if (metaData && timings.start && !timings.metadata) {
      const elapsed = performance.now() - timings.start;
      setTimings(prev => ({
        ...prev,
        metadata: elapsed,
        resolution: elapsed
      }));
    }
  }, [metaData, timings.start]);

  useEffect(() => {
    if (metricsData && timings.start && !timings.fundamentals) {
      const elapsed = performance.now() - timings.start;
      setTimings(prev => ({
        ...prev,
        fundamentals: elapsed,
        alphaScore: elapsed
      }));
    }
  }, [metricsData, timings.start]);

  useEffect(() => {
    if (chartData && timings.start && !timings.historical) {
      const elapsed = performance.now() - timings.start;
      setTimings(prev => ({
        ...prev,
        historical: elapsed
      }));
    }
  }, [chartData, timings.start]);

  useEffect(() => {
    if (briefingData && timings.start && !timings.aiReport) {
      const elapsed = performance.now() - timings.start;
      setTimings(prev => ({
        ...prev,
        aiReport: elapsed
      }));
    }
  }, [briefingData, timings.start]);

  useEffect(() => {
    if (newsData && timings.start && !timings.news) {
      const elapsed = performance.now() - timings.start;
      setTimings(prev => ({
        ...prev,
        news: elapsed
      }));
    }
  }, [newsData, timings.start]);

  useEffect(() => {
    const { start, metadata, fundamentals, historical, aiReport, news, total } = timings;
    if (start && metadata && fundamentals && historical && aiReport && news && !total) {
      const elapsed_total = performance.now() - start;
      setTimings(prev => ({ ...prev, total: elapsed_total }));
      
      console.log(
        `%c[PERF]\n` +
        `Symbol Resolution: ${metadata.toFixed(1)} ms\n` +
        `Metadata Fetch: ${metadata.toFixed(1)} ms\n` +
        `Historical Data: ${historical.toFixed(1)} ms\n` +
        `Fundamentals: ${fundamentals.toFixed(1)} ms\n` +
        `Alpha Score: ${fundamentals.toFixed(1)} ms\n` +
        `AI Report: ${aiReport.toFixed(1)} ms\n` +
        `Total: ${elapsed_total.toFixed(1)} ms`,
        "color: #c9a56b; font-weight: bold; font-family: monospace;"
      );
    }
  }, [timings]);

  const error = stockError ? (stockError.detail || stockError.response?.data?.detail || stockError.message || 'Failed to fetch stock details.') : null;

  const isSaved = watchlist.some((item) => item.symbol === symbol);

  const handleWatchlistToggle = async () => {
    try {
      if (isSaved) {
        await removeFromWatchlist(symbol);
      } else {
        await addToWatchlist(symbol);
      }
    } catch (err) {
      console.error("Watchlist modification failed", err);
    }
  };

  const handleSendChat = (e) => {
    e.preventDefault();
    if (!chatMessage.trim()) return;
    sendMessage(chatMessage, symbol, messages);
    setChatMessage('');
  };

  // Safe fallback placeholders for progressive loading
  const stock = {
    symbol: symbol,
    company_name: metaData?.company_name || `Discovering ${symbol}...`,
    sector: metaData?.sector || 'Ingesting...',
    industry: metaData?.industry || 'Resolving parameters...',
    market_cap: metaData?.market_cap || null,
    status: metaData?.status || 'discovering',
    
    // Metrics
    pe_ratio: metricsData?.pe_ratio ?? null,
    pb_ratio: metricsData?.pb_ratio ?? null,
    roe: metricsData?.roe ?? null,
    debt_equity: metricsData?.debt_equity ?? null,
    dividend_yield: metricsData?.dividend_yield ?? null,
    beta: metricsData?.beta ?? null,
    cagr_1y: metricsData?.cagr_1y ?? null,
    cagr_3y: metricsData?.cagr_3y ?? null,
    cagr_5y: metricsData?.cagr_5y ?? null,
    alpha_score: metricsData?.alpha_score ?? null,
    fundamental_score: metricsData?.fundamental_score ?? null,
    valuation_score: metricsData?.valuation_score ?? null,
    technical_score: metricsData?.technical_score ?? null,
    risk_score: metricsData?.risk_score ?? null,
    sector_relative_score: metricsData?.sector_relative_score ?? null,
    confidence_score: metricsData?.confidence_score ?? null,
    investor_verdict: metricsData?.investor_verdict ?? null,
    trader_verdict: metricsData?.trader_verdict ?? null,
    last_updated: metricsData?.last_updated ?? null,
    
    // Briefing
    ai_summary: briefingData?.ai_summary ?? null,
    bull_case: briefingData?.bull_case ?? null,
    bear_case: briefingData?.bear_case ?? null,
    verdict_rationale: briefingData?.verdict_rationale ?? null
  };
  
  const price_history = chartData || [];
  const alpha_score_breakdown = metricsData?.alpha_score_breakdown || {
    fundamental_score: 0,
    valuation_score: 0,
    momentum_score: 0,
    risk_score: 0
  };

  if (error) {
    return (
      <div className="max-w-2xl mx-auto mt-10 p-6 bg-brand-surface border border-brand-border text-center space-y-4 font-mono">
        <Cpu className="h-10 w-10 text-brand-danger mx-auto" />
        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Ingestion Pipeline Failure</h3>
        <p className="text-brand-textMuted text-xs leading-relaxed">{error}</p>
        <button
          onClick={() => navigate('/stocks/explorer')}
          className="bg-brand-primary hover:bg-[#cc4400] text-black text-[10px] font-bold px-4 py-2 border border-brand-primary transition-colors"
        >
          Return to Matrix
        </button>
      </div>
    );
  }

  if (!loading && !currentIsDiscovering && (!metaData || metaData.detail || metaError)) {
    return (
      <div className="max-w-2xl mx-auto mt-10 p-6 bg-brand-surface border border-brand-border text-center space-y-4 font-mono">
        <Cpu className="h-10 w-10 text-brand-warning mx-auto" />
        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Equity Not Found</h3>
        <p className="text-brand-textMuted text-xs leading-relaxed">{metaData?.detail || metaError?.message || 'Stock data is unavailable.'}</p>
        <button
          onClick={() => navigate('/stocks/explorer')}
          className="bg-brand-primary hover:bg-[#cc4400] text-black text-[10px] font-bold px-4 py-2 border border-brand-primary transition-colors"
        >
          Return to Stock Explorer
        </button>
      </div>
    );
  }

  // Map prices for standard InteractiveChart: maps 'close' to 'nav'
  const mappedChartHistory = price_history.map(p => ({
    date: p.date,
    nav: p.close
  }));

  // Format helpers
  const pct = (val) => (val !== null && val !== undefined ? `${(val * 100).toFixed(2)}%` : '—');
  const num = (val, dec = 2) => (val !== null && val !== undefined ? val.toFixed(dec) : '—');

  // Simple Markdown Parser for Stock Briefing report
  const renderBriefingSection = (sectionTitle) => {
    if (!stock.ai_summary) return null;
    const parts = stock.ai_summary.split(`### ${sectionTitle}`);
    if (parts.length < 2) return null;
    const sectionContent = parts[1].split('###')[0].trim();
    
    // Clean formatting and strong elements
    let html = sectionContent
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/^-\s*(.*)$/gm, '• $1<br/>')
      .split('\n')
      .filter(line => line.trim())
      .join('<br/>');

    return (
      <div className="space-y-1">
        <h4 className="text-[10px] font-bold text-brand-primary uppercase tracking-wider font-display">{sectionTitle}</h4>
        <p className="text-xs leading-relaxed font-sans text-brand-textMuted" dangerouslySetInnerHTML={{ __html: html }} />
      </div>
    );
  };

  const renderBriefingSectionContentOnly = (sectionTitle) => {
    if (!stock.ai_summary) return null;
    const parts = stock.ai_summary.split(`### ${sectionTitle}`);
    if (parts.length < 2) return null;
    const sectionContent = parts[1].split('###')[0].trim();
    
    let html = sectionContent
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/^-\s*(.*)$/gm, '• $1<br/>')
      .split('\n')
      .filter(line => line.trim())
      .join('<br/>');

    return (
      <p className="text-xs leading-relaxed font-sans text-brand-textMuted" dangerouslySetInnerHTML={{ __html: html }} />
    );
  };

  const renderResearchTimeline = () => {
    if (!stock.ai_summary) return null;
    const parts = stock.ai_summary.split('### Research Timeline');
    if (parts.length < 2) return null;
    const sectionContent = parts[1].split('###')[0].trim();
    
    const lines = sectionContent.split('\n').map(l => l.trim()).filter(Boolean);
    const entries = [];
    
    lines.forEach(line => {
      const match = line.match(/^-\s*\*\*(.*?)\*\*:\s*(.*)$/);
      if (match) {
        entries.push({
          date: match[1],
          desc: match[2]
        });
      } else {
        const simpleMatch = line.match(/^-\s*(.*)$/);
        if (simpleMatch) {
          const splitIdx = simpleMatch[1].indexOf(':');
          if (splitIdx > -1) {
            entries.push({
              date: simpleMatch[1].substring(0, splitIdx).replace(/\*\*/g, '').trim(),
              desc: simpleMatch[1].substring(splitIdx + 1).trim()
            });
          } else {
            entries.push({
              date: 'Event',
              desc: simpleMatch[1]
            });
          }
        }
      }
    });

    if (entries.length === 0) return null;

    return (
      <div className="border border-brand-border bg-brand-surface shadow-xl p-6 space-y-6">
        <div className="flex justify-between items-center border-b border-brand-border pb-3">
          <div className="flex items-center gap-2 text-brand-primary">
            <Cpu className="h-4 w-4" />
            <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">RESEARCH TIMELINE</h3>
          </div>
          <span className="font-mono text-[9px] text-brand-textMuted uppercase">[CHRONO_TRACKER]</span>
        </div>
        
        <div className="relative pl-6 border-l border-brand-primary/30 space-y-6 ml-3 py-2">
          {entries.map((item, idx) => (
            <div key={idx} className="relative group">
              <div className="absolute -left-[31px] top-1.5 w-2 h-2 bg-brand-primary border border-brand-primary rounded-full group-hover:shadow-[0_0_8px_#c5a880] transition-all" />
              <div className="space-y-1">
                <span className="text-[9px] font-mono font-bold text-brand-primary bg-brand-primary/10 border border-brand-primary/30 px-2 py-0.5 uppercase">
                  {item.date}
                </span>
                <p className="text-xs text-brand-textMuted leading-relaxed font-sans pt-1">
                  {item.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const isBriefingLoading = currentIsDiscovering || briefingFetchLoading || !stock.ai_summary || stock.ai_summary === "Generating Equity Intelligence Briefing in the background...";

  // ── Verdict parsing (mirrors Detail.jsx pattern) ──────────────────────────
  let investorVerdict = stock.investor_verdict || 'HOLD';
  let traderVerdict = stock.trader_verdict || 'HOLD';
  let stockConfidence = stock.confidence_score ? `${Math.round(stock.confidence_score)}%` : '';
  let stockStanceType = investorVerdict;
  let stockStanceText = '';

  if (!isBriefingLoading && stock.ai_summary) {
    // Parse Final Verdict section
    const verdictParts = stock.ai_summary.split('### Final Verdict');
    if (verdictParts.length >= 2) {
      const verdictContent = verdictParts[1].split('###')[0].trim();
      stockStanceText = verdictContent
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/^-\s*(.*)$/gm, '• $1<br/>')
        .split('\n').filter(l => l.trim()).join('<br/>');
        
      const lower = verdictContent.toLowerCase();
      if (!stock.investor_verdict || !stock.trader_verdict) {
        let parsedStance = 'HOLD';
        if (/\bstrong buy\b|\baccumulate\b|\boutperform\b|\bbuy\b/.test(lower)) parsedStance = 'BUY';
        else if (/\bavoid\b|\bsell\b|\bunderperform\b|\bhigh risk\b|\breduce\b/.test(lower)) parsedStance = 'AVOID';
        investorVerdict = parsedStance;
        traderVerdict = parsedStance;
      }
    }
    // Parse Confidence Score fallback
    if (!stockConfidence) {
      const confParts = stock.ai_summary.split('### Confidence Score');
      if (confParts.length >= 2) {
        const confContent = confParts[1].split('###')[0];
        const confMatch = confContent.match(/(\d{1,3})%/);
        if (confMatch) stockConfidence = confMatch[1] + '%';
      }
    }
  }

  if (investorVerdict.includes('BUY') || traderVerdict.includes('BUY')) {
    stockStanceType = 'BUY';
  } else if (investorVerdict.includes('AVOID') || traderVerdict.includes('AVOID') || investorVerdict.includes('REDUCE') || traderVerdict.includes('REDUCE')) {
    stockStanceType = 'AVOID';
  } else {
    stockStanceType = 'HOLD';
  }

  const renderMetricVal = (val, formatter, colorClass = "text-white") => {
    if (currentIsDiscovering || metricsLoading || val === null || val === undefined) {
      return (
        <div className="h-5 w-16 bg-brand-border/40 animate-pulse rounded mx-auto mt-2" />
      );
    }
    return (
      <p className={`text-lg font-bold mt-1 font-mono ${colorClass}`}>
        {formatter(val)}
      </p>
    );
  };

  return (
    <div className="space-y-6 sm:space-y-8 pb-20">
      {/* Back navigation & Watchlist Trigger */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 animate-fade-in-up">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-brand-textMuted hover:text-brand-primary transition-colors text-xs font-bold font-mono uppercase"
        >
          <ArrowLeft className="h-4 w-4" /> [Back to Matrix]
        </button>

        <button
          onClick={handleWatchlistToggle}
          className={`flex items-center gap-2 border text-[10px] font-bold font-mono px-4 py-2.5 transition-all ${
            isSaved 
              ? 'bg-brand-primary/10 border-brand-primary text-brand-primary' 
              : 'bg-brand-surface border-brand-border hover:border-brand-primary text-black dark:text-white'
          }`}
        >
          {isSaved ? (
            <>
              <Check className="h-3.5 w-3.5" /> SAVED IN WATCHLIST
            </>
          ) : (
            <>
              <Plus className="h-3.5 w-3.5" /> ADD TO WATCHLIST
            </>
          )}
        </button>
      </div>

      {/* Stock Metadata Header */}
      <div 
        className="relative border border-brand-border p-4 sm:p-6 md:p-8 shadow-xl animate-fade-in-up bg-brand-surface"
        style={{ animationDelay: '50ms' }}
      >
        <div className="absolute top-2 left-2 text-brand-textMuted font-mono text-[9px]">+ [STOCK_META]</div>
        <div className="absolute top-2 right-2 text-brand-textMuted font-mono text-[9px]">[ACTIVE] +</div>
        
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-center">
          <div className="lg:col-span-2 space-y-4">
            <div className="flex flex-wrap items-center gap-2 font-mono">
              <span className="text-[9px] font-bold bg-brand-primary/10 border border-brand-primary/40 text-brand-primary px-2.5 py-0.5 uppercase">
                [{getStandardizedSector(stock.sector).label.toUpperCase()}]
              </span>
              {stock.industry && (
                <span className="text-[9px] font-bold bg-brand-border/45 text-brand-textMuted px-2.5 py-0.5 border border-brand-border">
                  {stock.industry.toUpperCase()}
                </span>
              )}
            </div>
            
            <div className="flex flex-col md:flex-row md:items-center gap-4">
              <StockLogo symbol={stock.symbol} size="lg" />
              <div className="space-y-1.5 flex-1 min-w-0">
                <h1 className="text-2xl md:text-3xl font-extrabold text-black dark:text-white tracking-wide font-display uppercase truncate">
                  {stock.company_name}
                </h1>
                <div className="flex flex-wrap gap-x-6 gap-y-1.5 text-[10px] text-brand-textMuted font-mono pt-1">
                  <p>SYMBOL: <span className="text-black dark:text-white font-bold">{stock.symbol}</span></p>
                  {price_history.length > 0 ? (
                    <p>PRICE: <span className="text-brand-success font-bold">₹{price_history[0].close.toFixed(2)}</span></p>
                  ) : (
                    <p>PRICE: <span className="text-brand-textMuted animate-pulse">[INGESTING...]</span></p>
                  )}
                  {stock.isin && <p>ISIN: <span className="text-black dark:text-white font-bold">{stock.isin}</span></p>}
                  {stock.market_cap && <p>MARKET_CAP: <span className="text-black dark:text-white font-bold">₹{stock.market_cap.toLocaleString('en-IN')} Cr</span></p>}
                  <p>LAST_SYNC: <span className="text-black dark:text-white">{stock.last_updated ? new Date(stock.last_updated).toLocaleString('en-IN') : 'Ingesting...'}</span></p>
                  {stock.trend_structure && (
                    <p>TREND: <span className={`font-bold ${
                      stock.trend_structure === 'BULLISH' ? 'text-brand-success' :
                      stock.trend_structure === 'BEARISH' ? 'text-brand-danger' : 'text-brand-warning'
                    }`}>{stock.trend_structure}</span></p>
                  )}
                  {stock.event_score !== undefined && stock.event_score !== null && (
                    <p>EVENT_SCORE: <span className={`font-bold ${
                      stock.event_score >= 80 ? 'text-brand-success' :
                      stock.event_score <= 50 ? 'text-brand-danger' : 'text-brand-warning'
                    }`}>{Math.round(stock.event_score)}/100</span></p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Alpha Score factor grid */}
          <div className="border-t lg:border-t-0 lg:border-l border-brand-border pt-4 lg:pt-0 lg:pl-6 space-y-3 font-mono text-[10px]">
            <div className="flex justify-between items-center text-brand-primary font-bold tracking-wider mb-1">
              <span>ALPHA SCORE BREAKDOWN</span>
              <span className="text-black dark:text-white">{stock.alpha_score ? Math.round(stock.alpha_score) : '—'}/100</span>
            </div>
            {alpha_score_breakdown ? (
              <div className="space-y-2">
                {Object.entries(alpha_score_breakdown).map(([factor, score]) => (
                  <div key={factor} className="space-y-0.5">
                    <div className="flex justify-between items-center text-brand-textMuted uppercase text-[8px]">
                      <span>{factor.replace('_score', '').replace('_', ' ')}</span>
                      <span className="text-black dark:text-white font-bold">{score}</span>
                    </div>
                    <div className="w-full h-1 bg-brand-bg border border-brand-border/60 overflow-hidden">
                      <div 
                        className="h-full bg-brand-primary transition-all duration-1000 ease-out" 
                        style={{ width: `${score}%` }} 
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-brand-textMuted text-[9px] py-2 text-center">
                Factor breakdown loading...
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Numerical Metrics Grid */}
      <div 
        className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-9 gap-3 sm:gap-4 animate-fade-in-up"
        style={{ animationDelay: '100ms' }}
      >
        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">1Y return</p>
          {renderMetricVal(stock.cagr_1y, pct, "text-brand-success")}
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">3Y CAGR</p>
          {renderMetricVal(stock.cagr_3y, pct, "text-black dark:text-white")}
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">5Y CAGR</p>
          {renderMetricVal(stock.cagr_5y, pct, "text-black dark:text-white")}
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">P/E Ratio</p>
          {renderMetricVal(stock.pe_ratio, (v) => num(v, 1), "text-brand-primary")}
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">P/B Ratio</p>
          {renderMetricVal(stock.pb_ratio, (v) => num(v, 1), "text-brand-primary")}
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">ROE (%)</p>
          {renderMetricVal(stock.roe, (v) => `${v.toFixed(1)}%`, "text-brand-success")}
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Debt/Equity</p>
          {renderMetricVal(stock.debt_equity, num, "text-brand-warning")}
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Beta</p>
          {renderMetricVal(stock.beta, num, "text-brand-warning")}
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Alpha Score</p>
          {renderMetricVal(stock.alpha_score, (v) => Math.round(v), "text-brand-primary")}
        </div>
      </div>

      {/* Historical Price Chart */}
      <div 
        className="w-full animate-fade-in-up shadow-xl"
        style={{ animationDelay: '150ms' }}
      >
        {chartLoading || price_history.length === 0 ? (
          <div className="h-64 w-full bg-brand-surface border border-brand-border/40 animate-pulse flex flex-col items-center justify-center text-[10px] text-brand-textMuted tracking-wider font-mono gap-3">
            <RefreshCw className="h-5 w-5 animate-spin text-brand-primary/60" />
            <span>RESOLVING HISTORICAL PRICE SERIES...</span>
          </div>
        ) : (
          <InteractiveChart navHistory={mappedChartHistory} range={chartRange} onRangeChange={setChartRange} />
        )}
      </div>

      {/* Research Timeline (vertical chronological timeline below chart) */}
      {isBriefingLoading ? (
        <div className="w-full border border-brand-border bg-brand-surface shadow-xl p-6 md:p-8 space-y-4 animate-pulse">
          <div className="h-4 w-1/4 bg-brand-border/40 rounded mb-6" />
          <div className="relative pl-6 border-l border-brand-primary/30 space-y-6 ml-3 py-2">
            <div className="relative">
              <div className="absolute -left-[31px] top-1.5 w-2 h-2 bg-brand-primary/45 rounded-full" />
              <div className="space-y-2">
                <div className="h-3 w-20 bg-brand-border/45 rounded" />
                <div className="h-2.5 w-full bg-brand-border/30 rounded" />
              </div>
            </div>
            <div className="relative">
              <div className="absolute -left-[31px] top-1.5 w-2 h-2 bg-brand-primary/45 rounded-full" />
              <div className="space-y-2">
                <div className="h-3 w-24 bg-brand-border/45 rounded" />
                <div className="h-2.5 w-5/6 bg-brand-border/30 rounded" />
              </div>
            </div>
          </div>
        </div>
      ) : (
        stock.ai_summary && stock.ai_summary.includes('### Research Timeline') && (
          <div className="animate-fade-in-up" style={{ animationDelay: '180ms' }}>
            {renderResearchTimeline()}
          </div>
        )
      )}

      {/* Bottom Layout: AI Briefing → Verdict Card → Chat (all full-width stacked) */}
      <div className="flex flex-col gap-8">

        {/* AI Equity Briefing Panel — full width */}
        <div
          className="w-full border border-brand-border bg-brand-surface shadow-xl flex flex-col justify-between animate-fade-in-up"
          style={{ animationDelay: '200ms' }}
        >
          {/* Panel header */}
          <div className="bg-brand-bg border-b border-brand-border px-5 py-4 flex justify-between items-center text-xs">
            <div className="flex items-center gap-2 text-brand-primary">
              <Cpu className="h-4 w-4 animate-pulse-subtle" />
              <h3 className="font-bold text-black dark:text-white uppercase tracking-wider font-display">AI EQUITY BRIEFING REPORT</h3>
            </div>
            <span className="font-mono text-[9px] text-brand-textMuted uppercase">[RAG_TELEMETRY: aligned]</span>
          </div>

          <div className="p-6 md:p-8">
            {isBriefingLoading ? (
              <div className="space-y-6 py-4 animate-pulse">
                <div className="space-y-2">
                  <div className="h-3 w-1/4 bg-brand-border/40 rounded" />
                  <div className="h-2 w-full bg-brand-border/30 rounded" />
                  <div className="h-2 w-full bg-brand-border/30 rounded" />
                  <div className="h-2 w-5/6 bg-brand-border/30 rounded" />
                </div>
                <div className="space-y-2 pt-4 border-t border-brand-border/20">
                  <div className="h-3 w-1/4 bg-brand-border/40 rounded" />
                  <div className="h-2 w-full bg-brand-border/30 rounded" />
                  <div className="h-2 w-full bg-brand-border/30 rounded" />
                </div>
                <div className="space-y-2 pt-4 border-t border-brand-border/20">
                  <div className="h-3 w-1/5 bg-brand-border/40 rounded" />
                  <div className="h-2 w-full bg-brand-border/30 rounded" />
                  <div className="h-2 w-4/5 bg-brand-border/30 rounded" />
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {renderBriefingSection('Executive Summary')}

                {/* Investment Thesis — dedicated premium card */}
                {stock.bull_case ? (
                  <div className="p-4 border border-brand-primary/20 bg-brand-primary/5 space-y-2">
                    <div className="flex items-center gap-1.5 text-brand-primary">
                      <Star className="h-3.5 w-3.5 fill-current" />
                      <h4 className="text-[10px] font-bold uppercase tracking-wider font-display">Core Investment Thesis</h4>
                    </div>
                    <p className="text-xs leading-relaxed font-sans text-brand-textMuted" dangerouslySetInnerHTML={{ __html: stock.bull_case.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/^-\s*(.*)$/gm, '• $1<br/>').split('\n').filter(Boolean).join('<br/>') }} />
                  </div>
                ) : (stock.ai_summary && stock.ai_summary.includes('### Investment Thesis') && (
                  <div className="p-4 border border-brand-primary/20 bg-brand-primary/5 space-y-2">
                    <div className="flex items-center gap-1.5 text-brand-primary">
                      <Star className="h-3.5 w-3.5 fill-current" />
                      <h4 className="text-[10px] font-bold uppercase tracking-wider font-display">Core Investment Thesis</h4>
                    </div>
                    {renderBriefingSectionContentOnly('Investment Thesis')}
                  </div>
                ))}

                {renderBriefingSection('Performance Analysis')}
                {renderBriefingSection('Fundamental Analysis')}
                {renderBriefingSection('Sector Analysis')}
                {renderBriefingSection('Macro Analysis')}
                {renderBriefingSection('Geopolitical Analysis')}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-t border-brand-border/40 pt-4">
                  {renderBriefingSection('Bull Case')}
                  {renderBriefingSection('Base Case')}
                  {renderBriefingSection('Bear Case')}
                </div>

                {/* Risk Factors */}
                {stock.bear_case ? (
                  <div className="border-t border-brand-border/40 pt-4 space-y-1">
                    <h4 className="text-[10px] font-bold text-brand-warning uppercase tracking-wider font-display flex items-center gap-1.5">
                      ⚠️ Key Risk Factors
                    </h4>
                    <p className="text-xs leading-relaxed font-sans text-brand-textMuted" dangerouslySetInnerHTML={{ __html: stock.bear_case.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/^-\s*(.*)$/gm, '• $1<br/>').split('\n').filter(Boolean).join('<br/>') }} />
                  </div>
                ) : (stock.ai_summary && stock.ai_summary.includes('### Risk Factors') && (
                  <div className="border-t border-brand-border/40 pt-4 space-y-1">
                    <h4 className="text-[10px] font-bold text-brand-warning uppercase tracking-wider font-display flex items-center gap-1.5">
                      ⚠️ Key Risk Factors
                    </h4>
                    {renderBriefingSectionContentOnly('Risk Factors')}
                  </div>
                ))}

                {/* ── Professional Investment Verdict Card ──────────────────── */}
                {stockStanceText && (
                  <div className={`mt-2 border p-5 relative overflow-hidden transition-all duration-300 ${
                    stockStanceType === 'BUY'
                      ? 'bg-green-500/5 border-brand-success/40 shadow-[0_0_18px_rgba(34,197,94,0.06)] animate-fade-in'
                      : stockStanceType === 'AVOID'
                      ? 'bg-red-500/5 border-brand-danger/40 shadow-[0_0_18px_rgba(239,68,68,0.06)] animate-fade-in'
                      : 'bg-yellow-500/5 border-brand-warning/40 shadow-[0_0_18px_rgba(234,179,8,0.06)] animate-fade-in'
                  }`}>
                    {/* Left accent bar */}
                    <div className={`absolute top-0 bottom-0 left-0 w-1 ${
                      stockStanceType === 'BUY' ? 'bg-brand-success' :
                      stockStanceType === 'AVOID' ? 'bg-brand-danger' : 'bg-brand-warning'
                    }`} />

                    <div className="space-y-3 pl-3">
                      {/* Header row */}
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-2">
                          {stockStanceType === 'BUY'
                            ? <ShieldCheck className="h-5 w-5 text-brand-success" />
                            : stockStanceType === 'AVOID'
                            ? <ShieldAlert className="h-5 w-5 text-brand-danger" />
                            : <AlertTriangle className="h-5 w-5 text-brand-warning" />}
                          <span className={`font-mono text-xs uppercase font-extrabold tracking-wider ${
                            stockStanceType === 'BUY' ? 'text-brand-success' :
                            stockStanceType === 'AVOID' ? 'text-brand-danger' : 'text-brand-warning'
                          }`}>
                            System Investment Verdict: {stockStanceType}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {stockConfidence && (
                            <span className={`text-[9px] font-mono px-2 py-0.5 border ${
                              stockStanceType === 'BUY' ? 'text-brand-success border-brand-success/30 bg-brand-success/10' :
                              stockStanceType === 'AVOID' ? 'text-brand-danger border-brand-danger/30 bg-brand-danger/10' :
                              'text-brand-warning border-brand-warning/30 bg-brand-warning/10'
                            }`}>
                              CONFIDENCE: {stockConfidence}
                            </span>
                          )}
                          <span className={`text-[9px] font-mono px-2 py-0.5 border font-bold ${
                            stockStanceType === 'BUY' ? 'text-brand-success border-brand-success/30 bg-brand-success/10' :
                            stockStanceType === 'AVOID' ? 'text-brand-danger border-brand-danger/30 bg-brand-danger/10' :
                            'text-brand-warning border-brand-warning/30 bg-brand-warning/10'
                          }`}>
                            {stockStanceType}
                          </span>
                        </div>
                      </div>

                      {/* Dual verdicts grid */}
                      <div className="grid grid-cols-2 gap-4 border-b border-brand-border/30 pb-3 mt-1 mb-2 font-mono text-[10px]">
                        <div className="space-y-0.5">
                          <span className="text-brand-textMuted uppercase font-bold text-[8px] block">Investor Verdict (Long-Term)</span>
                          <span className={`text-xs font-extrabold ${
                            investorVerdict.includes('BUY') ? 'text-brand-success' :
                            investorVerdict.includes('AVOID') || investorVerdict.includes('REDUCE') ? 'text-brand-danger' : 'text-brand-warning'
                          }`}>
                            {investorVerdict}
                          </span>
                        </div>
                        <div className="space-y-0.5">
                          <span className="text-brand-textMuted uppercase font-bold text-[8px] block">Trader Verdict (Short-Term)</span>
                          <span className={`text-xs font-extrabold ${
                            traderVerdict.includes('BUY') ? 'text-brand-success' :
                            traderVerdict.includes('AVOID') || traderVerdict.includes('REDUCE') ? 'text-brand-danger' : 'text-brand-warning'
                          }`}>
                            {traderVerdict}
                          </span>
                        </div>
                      </div>

                      {/* Verdict body */}
                      <p
                        className="text-xs text-black dark:text-white leading-relaxed font-sans"
                        dangerouslySetInnerHTML={{ __html: stockStanceText }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer disclaimer */}
          <div className="bg-brand-bg border-t border-brand-border px-5 py-3.5 flex items-center gap-3 font-mono text-[9px] text-brand-textMuted leading-relaxed">
            <ShieldCheck className="h-4 w-4 text-brand-primary shrink-0" />
            <p>* WARNING: STATISTICAL VALUATIONS REPRESENT PROBABILISTIC FORECASTS, NOT GUARANTEES. NOT FINANCIAL ADVICE.</p>
          </div>
        </div>

        {/* Interactive Analyst Terminal — full width, below research */}
        <div
          className="w-full border border-brand-border bg-brand-surface shadow-xl flex flex-col font-mono animate-fade-in-up"
          style={{ animationDelay: '250ms', minHeight: '480px', maxHeight: '640px' }}
        >
          {/* Panel header */}
          <div className="bg-brand-bg border-b border-brand-border px-5 py-4 flex items-center gap-2 text-xs">
            <MessageSquare className="h-4 w-4 text-brand-primary" />
            <div>
              <h3 className="font-bold text-black dark:text-white uppercase font-display">Interactive Analyst Terminal</h3>
              <p className="text-[9px] text-brand-textMuted mt-0.5 font-mono">Pre-contextualized session for {stock.symbol}</p>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 p-3 sm:p-4 overflow-y-auto space-y-4 scrollbar text-[11px] leading-relaxed" style={{ minHeight: '200px' }}>
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center text-brand-textMuted space-y-2">
                <Cpu className="h-6 w-6 opacity-30 text-brand-primary" />
                <p className="text-[9px]">Ready to process equities queries. Ask things like: "Is {stock.symbol} a buy?" or "Explain its high P/E ratio."</p>
              </div>
            ) : (
              messages.map((m, idx) => (
                <AnalystResponseCard key={idx} message={m} />
              ))
            )}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-brand-bg border border-brand-border px-3 py-2 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-brand-primary rounded-full animate-bounce" />
                  <span className="w-1.5 h-1.5 bg-brand-primary rounded-full animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 bg-brand-primary rounded-full animate-bounce [animation-delay:0.4s]" />
                </div>
              </div>
            )}
          </div>

          {/* Input form */}
          <form onSubmit={handleSendChat} className="p-3 bg-brand-bg border-t border-brand-border flex gap-2">
            <input
              type="text"
              inputMode="text"
              placeholder={`Query analyst about ${stock.symbol}...`}
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              className="flex-1 bg-brand-surface border border-brand-border px-3.5 py-2 min-h-[44px] text-xs text-black dark:text-white focus:outline-none focus:border-brand-primary"
            />
            <button
              type="submit"
              disabled={chatLoading}
              className="bg-brand-primary hover:bg-brand-primaryHover disabled:opacity-50 text-black font-extrabold text-[9px] px-4 min-h-[44px] transition-colors border border-brand-primary"
            >
              EXEC
            </button>
          </form>
        </div>

        {/* Live Ticker Stream */}
        {newsData && newsData.length > 0 && (
          <div className="border border-brand-border bg-brand-surface p-5 sm:p-6 space-y-4 animate-fade-in-up" style={{ animationDelay: '250ms' }}>
            <div className="flex items-center gap-2 border-b border-brand-border pb-3">
              <Activity className="h-4 w-4 text-brand-primary animate-pulse" />
              <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">Live Ticker Stream</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {newsData.slice(0, 4).map((item, idx) => (
                <div key={idx} className="border border-brand-border/40 p-4 rounded hover:border-brand-primary/55 transition-all">
                  <div className="flex justify-between items-center gap-2 mb-1.5">
                    <span className="font-mono text-[9px] text-brand-textMuted uppercase">{item.provider}</span>
                    <span className="font-mono text-[8px] text-brand-textMuted/60">{item.pubDate}</span>
                  </div>
                  <h4 className="text-xs font-bold text-black dark:text-white line-clamp-2">{item.title}</h4>
                  <p className="text-[11px] text-brand-textMuted/80 line-clamp-2 mt-1.5 font-sans leading-relaxed">{item.summary}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Verdict Backtest Panel */}
        <StockBacktestPanel symbol={symbol} />

        {/* Developer Performance Panel */}
        <div className="fixed bottom-4 left-4 z-50 font-mono text-[9px]">
          <button
            onClick={() => setShowPerfPanel(!showPerfPanel)}
            className="bg-black/90 border border-brand-primary text-brand-primary px-3 py-1.5 hover:bg-brand-primary/10 transition-colors uppercase font-bold"
          >
            {showPerfPanel ? '[- Close Perf Panel]' : '[+ Dev Perf Panel]'}
          </button>
          {showPerfPanel && (
            <div className="mt-2 bg-black/95 border border-brand-border p-4 w-64 space-y-2 text-brand-textMuted shadow-2xl">
              <p className="text-white font-bold border-b border-brand-border pb-1">PERFORMANCE METRICS</p>
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span>Symbol Resolution:</span>
                  <span className="text-white font-bold">{timings.resolution ? `${timings.resolution.toFixed(1)}ms` : 'loading...'}</span>
                </div>
                <div className="flex justify-between">
                  <span>Metadata Fetch:</span>
                  <span className="text-white font-bold">{timings.metadata ? `${timings.metadata.toFixed(1)}ms` : 'loading...'}</span>
                </div>
                <div className="flex justify-between">
                  <span>Historical Data:</span>
                  <span className="text-white font-bold">{timings.historical ? `${timings.historical.toFixed(1)}ms` : 'loading...'}</span>
                </div>
                <div className="flex justify-between">
                  <span>Fundamentals:</span>
                  <span className="text-white font-bold">{timings.fundamentals ? `${timings.fundamentals.toFixed(1)}ms` : 'loading...'}</span>
                </div>
                <div className="flex justify-between">
                  <span>Alpha Score:</span>
                  <span className="text-white font-bold">{timings.alphaScore ? `${timings.alphaScore.toFixed(1)}ms` : 'loading...'}</span>
                </div>
                <div className="flex justify-between">
                  <span>AI Report:</span>
                  <span className="text-white font-bold">{timings.aiReport ? `${timings.aiReport.toFixed(1)}ms` : 'loading...'}</span>
                </div>
                <div className="flex justify-between border-t border-brand-border/40 pt-1 text-brand-primary font-bold">
                  <span>Total Load:</span>
                  <span>{timings.total ? `${timings.total.toFixed(1)}ms` : 'loading...'}</span>
                </div>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

// ─── Stock Backtest Panel ─────────────────────────────────────────────────────
function StockBacktestPanel({ symbol }) {
  const { data, isLoading, isError } = useStockBacktest(symbol);

  if (isLoading) {
    return (
      <div className="border border-brand-border bg-brand-surface p-5 animate-pulse">
        <div className="h-4 w-1/3 bg-brand-border/40 rounded mb-4" />
        <div className="grid grid-cols-4 gap-3">
          {[1,2,3,4].map(i => <div key={i} className="h-16 bg-brand-border/20 rounded" />)}
        </div>
      </div>
    );
  }

  if (isError || !data || data.status !== 'completed') return null;

  const horizons = [
    { key: 't30_days',  label: '30d',  hd: data.returns.t30_days },
    { key: 't90_days',  label: '90d',  hd: data.returns.t90_days },
    { key: 't180_days', label: '180d', hd: data.returns.t180_days },
    { key: 't365_days', label: '1Y',   hd: data.returns.t365_days },
  ];

  const verdictColor = (v) => {
    if (!v) return 'text-brand-textMuted';
    if (v.includes('BUY')) return 'text-brand-success';
    if (v === 'AVOID' || v === 'REDUCE') return 'text-brand-danger';
    return 'text-brand-warning';
  };

  return (
    <div className="border border-brand-border bg-brand-surface p-5 sm:p-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-brand-primary" />
          <h3 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider">Verdict Backtest</h3>
        </div>
        <div className="flex flex-wrap items-center gap-3 font-mono text-[9px] text-brand-textMuted">
          <span>Historical Verdict: <strong className={`${verdictColor(data.historical_verdict)} font-bold`}>{data.historical_verdict}</strong></span>
          <span className="text-brand-border">|</span>
          <span>Score: <strong className="text-black dark:text-white">{data.historical_score}</strong></span>
          <span className="text-brand-border">|</span>
          <span>From: <strong className="text-black dark:text-white">{data.eval_start_date}</strong></span>
        </div>
      </div>

      {/* Horizon returns grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {horizons.map(({ key, label, hd }) => {
          const ret = hd?.return_pct;
          const bench = hd?.benchmark_pct;
          const beat = hd?.outperformed;
          const noData = ret == null;
          return (
            <div key={key} className={`border p-3 rounded ${
              noData ? 'border-brand-border/40 bg-brand-surface'
                : beat ? 'border-brand-success/30 bg-brand-success/5'
                : 'border-brand-danger/30 bg-brand-danger/5'
            }`}>
              <div className="font-mono text-[9px] text-brand-textMuted uppercase tracking-wider mb-2">{label} Return</div>
              {noData ? (
                <div className="text-brand-textMuted font-mono text-lg font-bold">—</div>
              ) : (
                <>
                  <div className={`font-mono text-xl font-bold ${ ret >= 0 ? 'text-brand-success' : 'text-brand-danger' }`}>
                    {ret >= 0 ? '+' : ''}{ret.toFixed(1)}%
                  </div>
                  <div className="font-mono text-[9px] text-brand-textMuted mt-1">
                    Nifty: +{bench?.toFixed(1)}%
                  </div>
                  <div className={`font-mono text-[8px] mt-1 font-bold ${ beat ? 'text-brand-success' : 'text-brand-danger' }`}>
                    {beat ? '▲ Beat' : '▼ Miss'}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Verdict accuracy callout */}
      {data.verdict_success_365d !== null && data.verdict_success_365d !== undefined && (
        <div className={`mt-4 px-4 py-3 border rounded font-mono text-[10px] ${
          data.verdict_success_365d
            ? 'border-brand-success/30 bg-brand-success/5 text-brand-success'
            : 'border-brand-danger/30 bg-brand-danger/5 text-brand-danger'
        }`}>
          {data.verdict_success_365d
            ? `✓ Verdict "${data.historical_verdict}" was CORRECT at 1Y horizon.`
            : `✗ Verdict "${data.historical_verdict}" was INCORRECT at 1Y horizon.`}
        </div>
      )}
    </div>
  );
}
