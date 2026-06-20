import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Star, Cpu, MessageSquare, Plus, Check, Zap, Activity } from 'lucide-react';
import { useGetStockDetail, useStockAIChat, useWatchlist } from '../hooks/useStocks';
import InteractiveChart from '../components/charts/InteractiveChart';
import StockLogo from '../components/StockLogo';

export default function StockDetail() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  
  const { stockDetail, loading, error, fetchDetail, discovering, discoveringMessage, checkStatus } = useGetStockDetail();
  const { watchlist, addToWatchlist, removeFromWatchlist, fetchWatchlist } = useWatchlist();
  
  const [chatMessage, setChatMessage] = useState('');
  const { messages, loading: chatLoading, sendMessage } = useStockAIChat();
  const [discoverStep, setDiscoverStep] = useState(0);

  useEffect(() => {
    fetchDetail(symbol);
    fetchWatchlist();
  }, [symbol, fetchDetail, fetchWatchlist]);

  // Discovering state: poll /status every 5s until stock is ready, then load full detail
  useEffect(() => {
    if (!discovering) return;
    const DISCOVERY_STEPS = [
      'Connecting to NSE live data feed...',
      'Fetching 6Y price history from Yahoo Finance...',
      'Computing CAGR (1Y / 3Y / 5Y) metrics...',
      'Calculating Beta against NIFTY benchmark...',
      'Running multi-factor Alpha Score model...',
      'Persisting to AlphaMatrix intelligence database...',
      'Running AI equity briefing synthesis...',
    ];
    // Cycle through step labels every 4s
    const stepInterval = setInterval(() => {
      setDiscoverStep((prev) => (prev + 1) % DISCOVERY_STEPS.length);
    }, 4000);
    // Poll status every 6s
    const pollInterval = setInterval(async () => {
      const statusData = await checkStatus(symbol);
      if (statusData?.status === 'ready') {
        clearInterval(stepInterval);
        clearInterval(pollInterval);
        // Re-fetch full detail now that ingestion is complete
        fetchDetail(symbol);
      }
    }, 6000);
    return () => {
      clearInterval(stepInterval);
      clearInterval(pollInterval);
    };
  }, [discovering, symbol, checkStatus, fetchDetail]);

  // Polling to reload details when background AI summary is ready
  useEffect(() => {
    if (stockDetail && stockDetail.stock && stockDetail.stock.ai_summary === "Generating Equity Intelligence Briefing in the background...") {
      const pollTimer = setTimeout(() => {
        fetchDetail(symbol);
      }, 4000);
      return () => clearTimeout(pollTimer);
    }
  }, [stockDetail, symbol, fetchDetail]);


  const handleSendChat = (e) => {
    e.preventDefault();
    if (!chatMessage.trim()) return;
    sendMessage(chatMessage, symbol, messages);
    setChatMessage('');
  };

  const isSaved = React.useMemo(() => {
    return watchlist.some(item => item.symbol === symbol.toUpperCase());
  }, [watchlist, symbol]);

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

  if (loading && !stockDetail && !discovering) {
    return (
      <div className="h-[60vh] flex flex-col items-center justify-center text-brand-textMuted font-mono">
        <RefreshCw className="h-6 w-6 animate-spin text-brand-primary mb-3" />
        <p className="text-[10px] tracking-wider">RESOLVING STOCK PERFORMANCE PARAMETERS...</p>
      </div>
    );
  }

  // Discovering: new stock being auto-ingested from Yahoo Finance
  const DISCOVERY_STEPS = [
    'Connecting to NSE live data feed...',
    'Fetching 6Y price history from Yahoo Finance...',
    'Computing CAGR (1Y / 3Y / 5Y) metrics...',
    'Calculating Beta against NIFTY benchmark...',
    'Running multi-factor Alpha Score model...',
    'Persisting to AlphaMatrix intelligence database...',
    'Running AI equity briefing synthesis...',
  ];

  if (discovering) {
    return (
      <div className="max-w-2xl mx-auto mt-16 px-4 font-mono">
        <div className="bg-brand-surface border border-brand-border/60 p-8 space-y-6">
          {/* Header */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <Activity className="h-8 w-8 text-brand-primary" />
              <span className="absolute -top-1 -right-1 h-2.5 w-2.5 bg-brand-primary rounded-full animate-ping" />
            </div>
            <div>
              <p className="text-[9px] text-brand-textMuted tracking-widest uppercase">AlphaMatrix Discovery Engine</p>
              <h2 className="text-lg font-bold text-white tracking-wide">{symbol}</h2>
            </div>
          </div>

          {/* Terminal log */}
          <div className="bg-black border border-brand-border/30 p-4 space-y-2 text-[10px] font-mono">
            <p className="text-green-400 text-[9px] tracking-widest mb-3">[ALPHA_MATRIX_DISCOVERY v2.0] INITIATING LIVE STOCK INGESTION</p>
            {DISCOVERY_STEPS.map((step, i) => (
              <div key={i} className={`flex items-center gap-2 transition-opacity duration-500 ${
                i < discoverStep ? 'text-green-400' :
                i === discoverStep ? 'text-brand-primary' :
                'text-brand-textMuted/40'
              }`}>
                {i < discoverStep ? (
                  <span className="text-green-500">✓</span>
                ) : i === discoverStep ? (
                  <RefreshCw className="h-2.5 w-2.5 animate-spin" />
                ) : (
                  <span className="w-2.5">·</span>
                )}
                <span>{step}</span>
              </div>
            ))}
            <p className="text-brand-textMuted text-[9px] mt-3 animate-pulse">█ Polling every 6s...</p>
          </div>

          {/* ETA note */}
          <div className="border-t border-brand-border/30 pt-4 flex items-center gap-2 text-brand-textMuted text-[10px]">
            <Zap className="h-3 w-3 text-brand-primary" />
            <p>This stock is being auto-discovered from live exchanges. Estimated time: <span className="text-white font-bold">15–45 seconds</span>. Page will auto-reload when ready.</p>
          </div>

          <button
            onClick={() => navigate('/stocks/explorer')}
            className="text-[9px] text-brand-textMuted hover:text-brand-primary transition-colors tracking-wider"
          >
            ← Return to Stock Explorer
          </button>
        </div>
      </div>
    );
  }

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

  if (!stockDetail) return null;

  const { stock, price_history, alpha_score_breakdown } = stockDetail;

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

  const isBriefingLoading = stock.ai_summary === "Generating Equity Intelligence Briefing in the background...";

  return (
    <div className="space-y-8 pb-16">
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
        className="relative border border-brand-border p-6 md:p-8 shadow-xl animate-fade-in-up bg-brand-surface"
        style={{ animationDelay: '50ms' }}
      >
        <div className="absolute top-2 left-2 text-brand-textMuted font-mono text-[9px]">+ [STOCK_META]</div>
        <div className="absolute top-2 right-2 text-brand-textMuted font-mono text-[9px]">[ACTIVE] +</div>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-center">
          <div className="lg:col-span-2 space-y-4">
            <div className="flex flex-wrap items-center gap-2 font-mono">
              <span className="text-[9px] font-bold bg-brand-primary/10 border border-brand-primary/40 text-brand-primary px-2.5 py-0.5 uppercase">
                [{stock.sector.toUpperCase()}]
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
                  {stock.isin && <p>ISIN: <span className="text-black dark:text-white font-bold">{stock.isin}</span></p>}
                  {stock.market_cap && <p>MARKET_CAP: <span className="text-black dark:text-white font-bold">₹{stock.market_cap.toLocaleString('en-IN')} Cr</span></p>}
                  <p>LAST_SYNC: <span className="text-black dark:text-white">{new Date(stock.last_updated).toLocaleString('en-IN')}</span></p>
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
                      <span>{factor}</span>
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
        className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-9 gap-4 animate-fade-in-up"
        style={{ animationDelay: '100ms' }}
      >
        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">1Y return</p>
          <p className="text-lg font-bold text-brand-success mt-1 font-mono">{pct(stock.cagr_1y)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">3Y CAGR</p>
          <p className="text-lg font-bold text-black dark:text-white mt-1 font-mono">{pct(stock.cagr_3y)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">5Y CAGR</p>
          <p className="text-lg font-bold text-black dark:text-white mt-1 font-mono">{pct(stock.cagr_5y)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">P/E Ratio</p>
          <p className="text-lg font-bold text-brand-primary mt-1 font-mono">{num(stock.pe_ratio, 1)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">P/B Ratio</p>
          <p className="text-lg font-bold text-brand-primary mt-1 font-mono">{num(stock.pb_ratio, 1)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">ROE (%)</p>
          <p className="text-lg font-bold text-brand-success mt-1 font-mono">{stock.roe ? `${stock.roe.toFixed(1)}%` : '—'}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Debt/Equity</p>
          <p className="text-lg font-bold text-brand-warning mt-1 font-mono">{num(stock.debt_equity)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Beta</p>
          <p className="text-lg font-bold text-brand-warning mt-1 font-mono">{num(stock.beta)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Alpha Score</p>
          <p className="text-lg font-bold text-brand-primary mt-1 font-mono">{stock.alpha_score ? Math.round(stock.alpha_score) : '—'}</p>
        </div>
      </div>

      {/* Historical Price Chart */}
      <div 
        className="w-full animate-fade-in-up shadow-xl"
        style={{ animationDelay: '150ms' }}
      >
        <InteractiveChart navHistory={mappedChartHistory} />
      </div>

      {/* Research Timeline (vertical chronological timeline below chart) */}
      {!isBriefingLoading && stock.ai_summary && stock.ai_summary.includes('### Research Timeline') && (
        <div className="animate-fade-in-up" style={{ animationDelay: '180ms' }}>
          {renderResearchTimeline()}
        </div>
      )}

      {/* Bottom Layout: AI Briefing and Equities Chat */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Llama 3.3 AI Briefing Panel */}
        <div 
          className="lg:col-span-7 border border-brand-border bg-brand-surface shadow-xl p-6 min-h-[480px] animate-fade-in-up space-y-6 flex flex-col justify-between"
          style={{ animationDelay: '200ms' }}
        >
          <div>
            <div className="flex justify-between items-center border-b border-brand-border pb-3">
              <div className="flex items-center gap-2 text-brand-primary">
                <Cpu className="h-4 w-4 animate-pulse-subtle" />
                <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">AI EQUITY BRIEFING REPORT</h3>
              </div>
              <span className="font-mono text-[9px] text-brand-textMuted uppercase">[RAG_TELEMETRY: aligned]</span>
            </div>

            {isBriefingLoading ? (
              <div className="py-20 text-center space-y-3 font-mono text-brand-textMuted">
                <RefreshCw className="h-6 w-6 mx-auto animate-spin text-brand-primary" />
                <p className="text-[9px] uppercase tracking-wider animate-pulse">Running cognitive analytics models on stock multiples...</p>
              </div>
            ) : (
              <div className="space-y-6 pt-4 max-h-[520px] overflow-y-auto scrollbar">
                {renderBriefingSection('Executive Summary')}

                {/* Investment Thesis Section - Styled as a dedicated premium card block */}
                {stock.ai_summary && stock.ai_summary.includes('### Investment Thesis') && (
                  <div className="p-4 border border-brand-primary/20 bg-brand-primary/5 space-y-2">
                    <div className="flex items-center gap-1.5 text-brand-primary">
                      <Star className="h-3.5 w-3.5 fill-current" />
                      <h4 className="text-[10px] font-bold uppercase tracking-wider font-display">Core Investment Thesis</h4>
                    </div>
                    {renderBriefingSectionContentOnly('Investment Thesis')}
                  </div>
                )}

                {renderBriefingSection('Performance Analysis')}
                {renderBriefingSection('Fundamental Analysis')}
                {renderBriefingSection('Sector Analysis')}
                {renderBriefingSection('Macro Analysis')}
                {renderBriefingSection('Geopolitical Analysis')}
                
                <div className="grid grid-cols-3 gap-4 border-t border-brand-border/40 pt-4">
                  {renderBriefingSection('Bull Case')}
                  {renderBriefingSection('Base Case')}
                  {renderBriefingSection('Bear Case')}
                </div>
                
                {/* Risk Factors rendered next to the Final Verdict at the bottom */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 border-t border-brand-border/40 pt-4 font-mono text-[11px]">
                  <div className="md:col-span-1 border-r border-brand-border/20 pr-4 space-y-4">
                    {renderBriefingSection('Final Verdict')}
                    <div>
                      {renderBriefingSection('Confidence Score & Risk Rating')}
                    </div>
                  </div>
                  <div className="md:col-span-2">
                    <div className="space-y-1">
                      <h4 className="text-[10px] font-bold text-brand-warning uppercase tracking-wider font-display flex items-center gap-1.5">
                        ⚠️ Key Risk Factors
                      </h4>
                      {renderBriefingSectionContentOnly('Risk Factors')}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
          
          <div className="border-t border-brand-border/40 pt-3 flex items-center justify-between text-[8px] font-mono text-brand-textMuted">
            <p>* WARNING: STATISTICAL VALUATIONS REPRESENT PROBABILISTIC FORECASTS, NOT GUARANTEES.</p>
          </div>
        </div>

        {/* Equities Chat Panel */}
        <div 
          className="lg:col-span-5 border border-brand-border bg-brand-surface shadow-xl p-6 min-h-[480px] animate-fade-in-up flex flex-col justify-between"
          style={{ animationDelay: '250ms' }}
        >
          <div>
            <div className="flex items-center gap-2 border-b border-brand-border pb-3">
              <MessageSquare className="h-4 w-4 text-brand-primary" />
              <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">COGNITIVE EQUITY RESEARCH CHAT</h3>
            </div>
            
            <div className="h-[280px] overflow-y-auto space-y-4 scrollbar pr-1 text-[11px] leading-relaxed pt-4 font-mono">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center text-brand-textMuted px-4 space-y-2">
                  <Cpu className="h-6 w-6 opacity-30 text-brand-primary" />
                  <p className="text-[10px]">Ready to process equities queries. Ask things like: "Is {stock.symbol} a buy?" or "Explain its high P/E ratio."</p>
                </div>
              ) : (
                messages.map((m, idx) => (
                  <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] border px-3 py-2 ${
                      m.role === 'user'
                        ? 'bg-brand-primary/10 border-brand-primary text-black dark:text-white'
                        : 'bg-brand-bg border-brand-border text-black dark:text-white'
                    }`}>
                      {m.content}
                    </div>
                  </div>
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
          </div>

          <form onSubmit={handleSendChat} className="mt-4 pt-3 border-t border-brand-border/40 flex gap-2 font-mono">
            <input
              type="text"
              placeholder={`Query analyst about ${stock.symbol}...`}
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              className="flex-1 bg-brand-bg border border-brand-border px-3 py-2 text-xs text-black dark:text-white focus:outline-none focus:border-brand-primary"
            />
            <button
              type="submit"
              disabled={chatLoading}
              className="bg-brand-primary hover:bg-brand-primaryHover disabled:opacity-50 text-black font-extrabold text-[10px] px-4 py-2 transition-colors border border-brand-primary"
            >
              EXEC
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
