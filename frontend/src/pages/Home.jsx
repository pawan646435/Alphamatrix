import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TrendingUp, Layers, MessageSquare, Star, Cpu } from 'lucide-react';
import { useAIChat } from '../hooks/useFunds';
import { useFundList } from '../hooks/useQueries';
import RiskScatterplot from '../components/charts/RiskScatterplot';
import GlobalSearch from '../components/GlobalSearch';
import { CardSkeleton } from '../components/skeletons/Skeletons';

export default function Home() {
  const navigate = useNavigate();
  const { data: funds = [], isLoading: fundsLoading } = useFundList();
  
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessage, setChatMessage] = useState('');
  
  const { messages, loading: chatLoading, sendMessage } = useAIChat();

  const handleCategoryClick = (category) => {
    navigate(`/explorer?category=${encodeURIComponent(category)}`);
  };

  const handleSendChat = (e) => {
    e.preventDefault();
    if (!chatMessage.trim()) return;
    sendMessage(chatMessage, null, messages);
    setChatMessage('');
  };

  // High-level cards details
  const segments = [
    { name: 'Large Cap', desc: 'Stable, blue-chip investments targeting long-term growth.', count: '100+ Funds', color: 'border-brand-border hover:border-brand-primary text-brand-primary bg-brand-primary/5 hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]' },
    { name: 'Mid Cap', desc: 'Compounding growth engine balancing volatility and high yield.', count: '80+ Funds', color: 'border-brand-border hover:border-brand-primary text-brand-primary bg-brand-primary/5 hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]' },
    { name: 'Small Cap', desc: 'Aggressive wealth creators tapping high-potential businesses.', count: '60+ Funds', color: 'border-brand-border hover:border-brand-primary text-brand-primary bg-brand-primary/5 hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]' },
    { name: 'Index', desc: 'Low-cost passive investing copying benchmark market indices.', count: '50+ Funds', color: 'border-brand-border hover:border-brand-primary text-brand-primary bg-brand-primary/5 hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]' },
    { name: 'Sectoral', desc: 'Tactical sector-specific thematic funds.', count: '90+ Funds', color: 'border-brand-border hover:border-brand-primary text-brand-primary bg-brand-primary/5 hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]' },
  ];

  // Calculate statistics
  const stats = React.useMemo(() => {
    if (!funds.length) return { avgCagr: '0.00%', maxSharpe: '0.00', activeCount: 0 };
    const validCagrs = funds.filter(f => f.cagr_3y !== null).map(f => f.cagr_3y);
    const avgCagr = validCagrs.length ? (validCagrs.reduce((a, b) => a + b, 0) / validCagrs.length) * 100 : 0;
    const sharpes = funds.filter(f => f.sharpe_ratio !== null).map(f => f.sharpe_ratio);
    const maxSharpe = sharpes.length ? Math.max(...sharpes) : 0;
    
    return {
      avgCagr: `${avgCagr.toFixed(2)}%`,
      maxSharpe: maxSharpe.toFixed(2),
      activeCount: funds.length
    };
  }, [funds]);

  return (
    <div className="space-y-8 sm:space-y-12 pb-20">
      {/* Hero Display Panel */}
      <div 
        className="relative border border-brand-border p-6 sm:p-8 md:p-12 overflow-hidden flex flex-col items-center text-center animate-fade-in-up bg-brand-surface"
      >
        {/* Terminal Corner Crosshairs decoration */}
        <div className="absolute top-2 left-2 text-brand-textMuted select-none font-mono text-xs">+ [MATRIX_SYS]</div>
        <div className="absolute top-2 right-2 text-brand-textMuted select-none font-mono text-xs">[ONLINE] +</div>
        <div className="absolute bottom-2 left-2 text-brand-textMuted select-none font-mono text-xs">+ [LOC_IN]</div>
        <div className="absolute bottom-2 right-2 text-brand-textMuted select-none font-mono text-xs">[SECURE] +</div>
        
        {/* Subtle grid accent inside hero */}
        <div className="absolute inset-0 bg-gradient-to-b from-brand-primary/5 via-transparent to-brand-primary/5 opacity-40 pointer-events-none" />

        <div className="flex items-center gap-1.5 px-3 py-1 bg-brand-primary/10 border border-brand-primary/40 text-brand-primary text-[10px] font-mono uppercase tracking-wider mb-5 animate-pulse-subtle">
          <Cpu className="h-3 w-3" /> COGNITIVE COMPILATION LAYER ACTIVE [v1.5_FLASH]
        </div>
        
        <h1 className="text-4xl md:text-5xl font-extrabold text-black dark:text-white tracking-tight leading-none max-w-4xl font-display uppercase">
          NAVIGATE MUTUAL FUNDS WITH <span className="text-brand-primary">QUANTITATIVE RIGOR</span>
        </h1>
        
        <p className="text-brand-textMuted text-sm md:text-base max-w-2xl mt-4 leading-relaxed font-sans">
          Compute Rolling Sharpe, Sortino, CAGR, and CAPM Beta across 10,000+ Indian mutual funds. Powered by strict RAG models.
        </p>

        {/* Master Search Input */}
        <div className="mt-8 w-full flex justify-center">
          <GlobalSearch />
        </div>
      </div>

      {/* Analytics Overview Cards - show skeletons until data is ready */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {fundsLoading ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : (
          <>
            <div 
              className="terminal-card flex items-center gap-4 animate-fade-in-up"
              style={{ animationDelay: '100ms' }}
            >
              <div className="w-10 h-10 border border-brand-border bg-brand-surface flex items-center justify-center text-brand-primary">
                <Layers className="h-4 w-4" />
              </div>
              <div>
                <p className="text-[10px] text-brand-textMuted uppercase font-bold tracking-wider font-display">OPERATIONAL DATABASE</p>
                <h3 className="text-xl font-bold text-black dark:text-white mt-0.5 font-mono">{stats.activeCount} seeded</h3>
              </div>
            </div>

            <div 
              className="terminal-card flex items-center gap-4 animate-fade-in-up hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]"
              style={{ animationDelay: '150ms' }}
            >
              <div className="w-10 h-10 border border-brand-primary bg-brand-surface flex items-center justify-center text-brand-primary">
                <TrendingUp className="h-4 w-4" />
              </div>
              <div>
                <p className="text-[10px] text-brand-textMuted uppercase font-bold tracking-wider font-display">AVG 3-YEAR YIELD</p>
                <h3 className="text-xl font-bold text-black dark:text-white mt-0.5 font-mono">{stats.avgCagr}</h3>
              </div>
            </div>

            <div 
              className="terminal-card flex items-center gap-4 animate-fade-in-up hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]"
              style={{ animationDelay: '200ms' }}
            >
              <div className="w-10 h-10 border border-brand-primary bg-brand-surface flex items-center justify-center text-brand-primary">
                <Star className="h-4 w-4" />
              </div>
              <div>
                <p className="text-[10px] text-brand-textMuted uppercase font-bold tracking-wider font-display">PEAK SHARPE RATIO</p>
                <h3 className="text-xl font-bold text-black dark:text-white mt-0.5 font-mono">{stats.maxSharpe}</h3>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Middle Grid: Segment Matrix cards and Scatterplot */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Segments Cards */}
        <div 
          className="lg:col-span-5 space-y-4 animate-fade-in-up"
          style={{ animationDelay: '250ms' }}
        >
          <div className="flex items-center justify-between border-b border-brand-border pb-2">
            <h2 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider">Asset Classes Matrix</h2>
            <span className="font-mono text-[10px] text-brand-textMuted">[SEC_COUNT: 5]</span>
          </div>
          
          <div className="grid grid-cols-1 gap-3">
            {segments.map((seg) => (
              <button
                key={seg.name}
                onClick={() => handleCategoryClick(seg.name)}
                className={`w-full text-left p-4 border transition-all duration-200 hover:-translate-x-1 flex justify-between items-center group ${seg.color}`}
              >
                <div className="space-y-1">
                  <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wide">{seg.name} Funds</h3>
                  <p className="text-[10px] text-brand-textMuted max-w-sm line-clamp-1 font-sans">{seg.desc}</p>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-[9px] font-mono bg-brand-bg px-2 py-1 border border-brand-border text-black dark:text-white">
                    {seg.count}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Scatterplot */}
        <div 
          className="lg:col-span-7 h-[300px] sm:h-[420px] animate-fade-in-up"
          style={{ animationDelay: '300ms' }}
        >
          <RiskScatterplot funds={funds} />
        </div>
      </div>

      {/* Floating AI Chat Assistant Drawer */}
      <div className={`fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-50 transition-all duration-300 ${chatOpen ? 'w-[calc(100vw-32px)] sm:w-[360px] h-[480px]' : 'w-12 h-12'}`}>
        {chatOpen ? (
          <div className="w-full h-full bg-brand-surface border border-brand-border shadow-2xl flex flex-col overflow-hidden font-mono">
            {/* Header */}
            <div className="bg-brand-bg border-b border-brand-border px-4 py-3 flex justify-between items-center text-xs">
              <div className="flex items-center gap-1.5 font-display">
                <span className="w-2 h-2 rounded-full bg-brand-primary animate-pulse" />
                <span className="font-bold text-black dark:text-white">COGNITIVE_ANALYST.EXE</span>
              </div>
              <button
                onClick={() => setChatOpen(false)}
                className="text-brand-textMuted hover:text-brand-primary font-bold"
              >
                [MIN]
              </button>
            </div>
            
            {/* Messages */}
            <div className="flex-1 p-4 overflow-y-auto space-y-4 scrollbar text-[11px] leading-relaxed">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center text-brand-textMuted px-2 space-y-2">
                  <MessageSquare className="h-6 w-6 opacity-30 text-brand-primary" />
                  <p className="text-[10px]">Ready to process queries. Ask about metrics, CAPM calculations, or portfolio risk parameters.</p>
                </div>
              ) : (
                messages.map((m, idx) => (
                  <div
                    key={idx}
                    className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] border px-3 py-2 ${
                        m.role === 'user'
                          ? 'bg-brand-primary/10 border-brand-primary text-black dark:text-white'
                          : 'bg-brand-bg border-brand-border text-black dark:text-white'
                      }`}
                    >
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

            {/* Input form */}
            <form onSubmit={handleSendChat} className="p-3 bg-brand-bg border-t border-brand-border flex gap-2">
              <input
                type="text"
                inputMode="text"
                placeholder="Query system database..."
                value={chatMessage}
                onChange={(e) => setChatMessage(e.target.value)}
                className="flex-1 bg-brand-surface border border-brand-border px-3 py-2 min-h-[44px] text-xs text-black dark:text-white focus:outline-none focus:border-brand-primary"
              />
              <button
                type="submit"
                disabled={chatLoading}
                className="bg-brand-primary hover:bg-brand-primaryHover disabled:opacity-50 text-black font-extrabold text-[10px] px-3 min-h-[44px] transition-colors border border-brand-primary"
              >
                EXEC
              </button>
            </form>
          </div>
        ) : (
          <button
            onClick={() => setChatOpen(true)}
            className="w-full h-full bg-brand-primary hover:bg-brand-primaryHover text-black flex items-center justify-center shadow-2xl transition-all border border-brand-primary hover:scale-105"
          >
            <MessageSquare className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  );
}
