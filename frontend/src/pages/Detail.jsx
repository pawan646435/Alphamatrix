import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Sparkles, MessageSquare, TrendingUp, AlertTriangle, ShieldCheck, Globe, ExternalLink, ShieldAlert } from 'lucide-react';
import { useSyncFund, useAIChat } from '../hooks/useFunds';
import { useFundDetail } from '../hooks/useQueries';
import InteractiveChart from '../components/charts/InteractiveChart';
import FundLogo from '../components/FundLogo';
import AnalystResponseCard from '../components/AnalystResponseCard';

export default function Detail() {
  const { schemeCode } = useParams();
  const navigate = useNavigate();
  const { data: fundDetail, isLoading: loading, error: fundError, refetch } = useFundDetail(schemeCode);
  const { sync, loading: syncing } = useSyncFund();
  
  const [chatMessage, setChatMessage] = useState('');
  const { messages, loading: chatLoading, sendMessage } = useAIChat();

  const error = fundError ? (fundError.response?.data?.detail || fundError.message || 'Failed to fetch fund details.') : null;

  // Handle manual data refresh
  const handleSync = async () => {
    try {
      await sync(schemeCode);
      refetch();
    } catch (err) {
      console.error("Manual sync failed", err);
    }
  };

  const handleSendChat = (e) => {
    e.preventDefault();
    if (!chatMessage.trim()) return;
    sendMessage(chatMessage, schemeCode, messages);
    setChatMessage('');
  };

  if (loading && !fundDetail) {
    return (
      <div className="h-[60vh] flex flex-col items-center justify-center text-brand-textMuted font-mono">
        <RefreshCw className="h-6 w-6 animate-spin text-brand-primary mb-3" />
        <p className="text-[10px] tracking-wider">RESOLVING FUND PERFORMANCE PARAMETERS...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto mt-10 p-6 bg-brand-surface border border-brand-border text-center space-y-4 font-mono">
        <AlertTriangle className="h-10 w-10 text-brand-danger mx-auto" />
        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Ingestion Pipeline Failure</h3>
        <p className="text-brand-textMuted text-xs leading-relaxed">{error}</p>
        <button
          onClick={() => navigate('/explorer')}
          className="bg-brand-primary hover:bg-[#cc4400] text-white text-[10px] font-bold px-4 py-2 border border-brand-primary transition-colors"
        >
          Return to Matrix
        </button>
      </div>
    );
  }

  if (!fundDetail) return null;

  const { fund, nav_history } = fundDetail;

  // Format helper
  const pct = (val) => (val !== null && val !== undefined ? `${(val * 100).toFixed(2)}%` : '—');
  const num = (val, dec = 2) => (val !== null && val !== undefined ? val.toFixed(dec) : '—');

  // Parse bullets from ai_summary
  const aiBullets = fund.ai_summary
    ? fund.ai_summary.split('\n').filter(line => line.trim().startsWith('-'))
    : [];

  const cleanBulletText = (text) => {
    let cleaned = text.replace(/^-\s*/, '');
    cleaned = cleaned.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    return cleaned;
  };

  let trajectoryText = '';
  let geopoliticalText = '';
  let stanceText = '';
  let stanceType = 'HOLD';

  aiBullets.forEach(bullet => {
    const cleaned = cleanBulletText(bullet);
    const lower = bullet.toLowerCase();
    
    if (lower.includes('1-year') || lower.includes('trajectory') || lower.includes('trend')) {
      trajectoryText = cleaned;
    } else if (lower.includes('geopolitical') || lower.includes('macro') || lower.includes('overlay')) {
      geopoliticalText = cleaned;
    } else if (lower.includes('stance') || lower.includes('recommendation') || lower.includes('buy') || lower.includes('hold') || lower.includes('avoid')) {
      stanceText = cleaned;
      if (lower.includes('buy')) stanceType = 'BUY';
      else if (lower.includes('avoid')) stanceType = 'AVOID';
      else if (lower.includes('hold')) stanceType = 'HOLD';
    }
  });

  // Fallbacks if classification fails
  if (!trajectoryText && aiBullets[0]) trajectoryText = cleanBulletText(aiBullets[0]);
  if (!geopoliticalText && aiBullets[1]) geopoliticalText = cleanBulletText(aiBullets[1]);
  if (!stanceText && aiBullets[2]) {
    stanceText = cleanBulletText(aiBullets[2]);
    const lowerStance = aiBullets[2].toLowerCase();
    if (lowerStance.includes('buy')) stanceType = 'BUY';
    else if (lowerStance.includes('avoid')) stanceType = 'AVOID';
    else if (lowerStance.includes('hold')) stanceType = 'HOLD';
  }

  return (
    <div className="space-y-6 sm:space-y-8 pb-20">
      {/* Back navigation & Refresh Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 animate-fade-in-up">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-brand-textMuted hover:text-brand-primary transition-colors text-xs font-bold font-mono uppercase"
        >
          <ArrowLeft className="h-4 w-4" /> [Back to Matrix]
        </button>

        <div className="flex items-center gap-2 self-stretch sm:self-auto font-mono">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-brand-surface border border-brand-border hover:border-brand-primary disabled:opacity-50 text-black dark:text-white text-[10px] font-bold px-4 py-2.5 transition-all"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin text-brand-primary' : ''}`} />
            {syncing ? 'RE-INGESTING TIME-SERIES...' : 'SYNC LIVE NAV FEED'}
          </button>
        </div>
      </div>

      {/* Fund Metadata Header */}
      <div 
        className="relative border border-brand-border p-6 md:p-8 shadow-xl animate-fade-in-up bg-brand-surface"
        style={{ animationDelay: '50ms' }}
      >
        <div className="absolute top-2 left-2 text-brand-textMuted font-mono text-[9px]">+ [SCHEME_META]</div>
        <div className="absolute top-2 right-2 text-brand-textMuted font-mono text-[9px]">[ACTIVE] +</div>
        
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 font-mono">
            <span className="text-[9px] font-bold bg-brand-primary/10 border border-brand-primary/40 text-brand-primary px-2.5 py-0.5 uppercase">
              [{fund.category.toUpperCase().replace(' ', '_')}]
            </span>
            {fund.sub_category && (
              <span className="text-[9px] font-bold bg-brand-border/45 text-brand-textMuted px-2.5 py-0.5 border border-brand-border">
                {fund.sub_category.toUpperCase()}
              </span>
            )}
          </div>
          
          <div className="flex flex-col md:flex-row md:items-center gap-4">
            <FundLogo fundName={fund.fund_name} size="lg" />
            <div className="space-y-1.5 flex-1 min-w-0">
              <h1 className="text-2xl md:text-3xl font-extrabold text-black dark:text-white tracking-wide font-display uppercase truncate">
                {fund.fund_name}
              </h1>
              <div className="flex flex-wrap gap-x-6 gap-y-1.5 text-[10px] text-brand-textMuted font-mono pt-1">
                <p>SCHEME_CODE: <span className="text-black dark:text-white font-bold">{fund.scheme_code}</span></p>
                {fund.isin && <p>ISIN: <span className="text-black dark:text-white font-bold">{fund.isin}</span></p>}
                <p>LAST_SYNC: <span className="text-black dark:text-white">{new Date(fund.last_updated).toLocaleString('en-IN')}</span></p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Numerical Metrics Grid */}
      <div 
        className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-9 gap-3 sm:gap-4 animate-fade-in-up"
        style={{ animationDelay: '100ms' }}
      >
        {/* Return cards */}
        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">1Y CAGR</p>
          <p className="text-lg font-bold text-brand-success mt-1 font-mono">{pct(fund.cagr_1y)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">3Y CAGR</p>
          <p className="text-lg font-bold text-black dark:text-white mt-1 font-mono">{pct(fund.cagr_3y)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">5Y CAGR</p>
          <p className="text-lg font-bold text-black dark:text-white mt-1 font-mono">{pct(fund.cagr_5y)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Sharpe Ratio</p>
          <p className="text-lg font-bold text-brand-primary mt-1 font-mono">{num(fund.sharpe_ratio)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Sortino Ratio</p>
          <p className="text-lg font-bold text-brand-primary mt-1 font-mono">{num(fund.sortino_ratio)}</p>
        </div>

        {/* Risk CAPM cards */}
        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Beta (Nifty50)</p>
          <p className="text-lg font-bold text-brand-warning mt-1 font-mono">{num(fund.beta)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Alpha (Nifty50)</p>
          <p className="text-lg font-bold text-brand-warning mt-1 font-mono">{pct(fund.alpha)}</p>
        </div>

        {/* Cost and valuation cards */}
        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">P/E Ratio</p>
          <p className="text-lg font-bold text-black dark:text-white mt-1 font-mono">{num(fund.pe_ratio, 1)}</p>
        </div>

        <div className="terminal-card text-center hover:shadow-[0_0_15px_rgba(197,168,128,0.15)]">
          <p className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Expense Ratio</p>
          <p className="text-lg font-bold text-brand-textMuted mt-1 font-mono">{fund.expense_ratio ? `${fund.expense_ratio.toFixed(2)}%` : '—'}</p>
        </div>
      </div>

      {/* Recharts interactive timeline */}
      <div 
        className="w-full animate-fade-in-up shadow-xl"
        style={{ animationDelay: '150ms' }}
      >
        <InteractiveChart navHistory={nav_history} />
      </div>

      {/* Bottom Layout: AI Synthesis and Contextual Chat stacked vertically */}
      <div className="flex flex-col gap-8">
        {/* Llama 3.3 RAG Bullet summary */}
        <div 
          className="w-full border border-brand-border bg-brand-surface shadow-xl flex flex-col justify-between min-h-[420px] animate-fade-in-up"
          style={{ animationDelay: '200ms' }}
        >
          {/* Header */}
          <div className="bg-brand-bg border-b border-brand-border px-5 py-4 flex justify-between items-center text-xs">
            <div className="flex items-center gap-2 text-brand-primary">
              <Sparkles className="h-4 w-4" />
              <h2 className="font-bold text-black dark:text-white uppercase tracking-wider font-display">Quantitative Intelligence Briefing</h2>
            </div>
            <span className="text-[9px] font-mono text-brand-textMuted bg-brand-bg border border-brand-border px-2 py-0.5 uppercase">
              MODEL: LLAMA_3.3_70B_VERSATILE
            </span>
          </div>

          <div className="p-6 md:p-8 flex-1 flex flex-col justify-between">
            {aiBullets.length > 0 ? (
              <div className="space-y-6">
                {/* Data Sources and Links */}
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-[10px] font-mono border-b border-brand-border/40 pb-4 mb-4">
                  <span className="text-brand-textMuted uppercase">[SOURCES_LINKS]:</span>
                  <a 
                    href={`https://api.mfapi.in/mf/${fund.scheme_code}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 px-2.5 py-1 bg-brand-bg border border-brand-border text-brand-primary hover:border-brand-primary hover:text-black dark:hover:text-white transition-colors"
                  >
                    RAW_NAV_API_FEED <ExternalLink className="h-3 w-3" />
                  </a>
                  <a 
                    href={`https://www.google.com/search?q=${encodeURIComponent(fund.fund_name + ' mutual fund')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 px-2.5 py-1 bg-brand-bg border border-brand-border text-brand-primary hover:border-brand-primary hover:text-black dark:hover:text-white transition-colors"
                  >
                    GOOGLE_FINANCE <ExternalLink className="h-3 w-3" />
                  </a>
                  <a 
                    href="https://www.amfiindia.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 px-2.5 py-1 bg-brand-bg border border-brand-border text-brand-primary hover:border-brand-primary hover:text-black dark:hover:text-white transition-colors"
                  >
                    AMFI_OFFICIAL <ExternalLink className="h-3 w-3" />
                  </a>
                </div>

                {/* Bullet 1: 1-Year Trend */}
                {trajectoryText && (
                  <div className="space-y-2 border-l-2 border-brand-primary/40 pl-4 py-1">
                    <div className="flex items-center gap-2 text-brand-primary font-mono text-[10px] uppercase font-bold tracking-wider">
                      <TrendingUp className="h-3.5 w-3.5" />
                      1-Year Trajectory & Trend
                    </div>
                    <p className="text-xs text-black dark:text-white leading-relaxed font-sans" dangerouslySetInnerHTML={{ __html: trajectoryText }} />
                  </div>
                )}

                {/* Bullet 2: Geopolitical & Macro Overlay */}
                {geopoliticalText && (
                  <div className="space-y-2 border-l-2 border-brand-primary/40 pl-4 py-1">
                    <div className="flex items-center gap-2 text-brand-primary font-mono text-[10px] uppercase font-bold tracking-wider">
                      <Globe className="h-3.5 w-3.5" />
                      Geopolitical & Macro Overlay
                    </div>
                    <p className="text-xs text-black dark:text-white leading-relaxed font-sans" dangerouslySetInnerHTML={{ __html: geopoliticalText }} />
                  </div>
                )}

                {/* Bullet 3: Definitive recommendation callout */}
                {stanceText && (
                  <div className={`mt-6 border p-4 relative overflow-hidden transition-all duration-300 ${
                    stanceType === 'BUY' ? 'bg-green-500/5 border-brand-success/40 shadow-[0_0_15px_rgba(34,197,94,0.05)] animate-fade-in' :
                    stanceType === 'AVOID' ? 'bg-red-500/5 border-brand-danger/40 shadow-[0_0_15px_rgba(239,68,68,0.05)] animate-fade-in' :
                    'bg-yellow-500/5 border-brand-warning/40 shadow-[0_0_15px_rgba(234,179,8,0.05)] animate-fade-in'
                  }`}>
                    {/* Glowing side accent line */}
                    <div className={`absolute top-0 bottom-0 left-0 w-1 ${
                      stanceType === 'BUY' ? 'bg-brand-success' :
                      stanceType === 'AVOID' ? 'bg-brand-danger' :
                      'bg-brand-warning'
                    }`} />
                    
                    <div className="space-y-2 pl-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {stanceType === 'BUY' ? <ShieldCheck className="h-4.5 w-4.5 text-brand-success" /> :
                           stanceType === 'AVOID' ? <ShieldAlert className="h-4.5 w-4.5 text-brand-danger" /> :
                           <AlertTriangle className="h-4.5 w-4.5 text-brand-warning" />}
                          <span className={`font-mono text-xs uppercase font-extrabold tracking-wider ${
                            stanceType === 'BUY' ? 'text-brand-success' :
                            stanceType === 'AVOID' ? 'text-brand-danger' :
                            'text-brand-warning'
                          }`}>
                            System Investment Verdict: {stanceType}
                          </span>
                        </div>
                        <span className={`text-[9px] font-mono px-2 py-0.5 border ${
                          stanceType === 'BUY' ? 'text-brand-success border-brand-success/30 bg-brand-success/10' :
                          stanceType === 'AVOID' ? 'text-brand-danger border-brand-danger/30 bg-brand-danger/10' :
                          'text-brand-warning border-brand-warning/30 bg-brand-warning/10'
                        }`}>
                          {stanceType}
                        </span>
                      </div>
                      
                      <p className="text-xs text-black dark:text-white leading-relaxed font-sans mt-2" dangerouslySetInnerHTML={{ __html: stanceText }} />
                    </div>
                  </div>
                )}
              </div>
            ) : fund.ai_summary === "Generating AI Analysis in the background..." ? (
              <div className="py-16 text-center text-brand-textMuted text-[10px] font-mono flex flex-col items-center justify-center gap-3 flex-grow">
                <RefreshCw className="h-7 w-7 text-brand-primary animate-spin" />
                <p className="tracking-wider text-black dark:text-white uppercase">Synthesizing macroeconomic & geopolitical parameters...</p>
                <p className="text-[9px] text-brand-textMuted">Connecting Llama 3.3 RAG Pipeline. Estimated wait: 3-5 seconds.</p>
              </div>
            ) : (
              <div className="py-16 text-center text-brand-textMuted text-[10px] font-mono flex flex-col items-center justify-center gap-2 flex-grow">
                <Sparkles className="h-7 w-7 opacity-25 text-brand-primary animate-pulse" />
                <p>MOCK_RAG_PIPELINE: AWAITING SYNTHESIS INGESTION...</p>
                <button 
                  onClick={handleSync}
                  className="mt-2 text-brand-primary hover:underline font-bold"
                >
                  Force calculation sync
                </button>
              </div>
            )}
          </div>
          
          <div className="bg-brand-bg border-t border-brand-border px-5 py-3.5 flex items-center gap-3 font-mono text-[9px] text-brand-textMuted leading-relaxed">
            <ShieldCheck className="h-4 w-4 text-brand-primary shrink-0" />
            <p>
              RAG CONSTRAINT ACTIVE: Calculations and reports are bound strictly to verified database numerical schemas to protect against language model hallucinations.
            </p>
          </div>
        </div>

        {/* Contextual chat panel - moved below and expanded */}
        <div 
          className="w-full border border-brand-border bg-brand-surface shadow-xl flex flex-col font-mono animate-fade-in-up"
          style={{ animationDelay: '250ms', minHeight: '480px', maxHeight: '640px' }}
        >
          <div className="bg-brand-bg border-b border-brand-border px-5 py-4 flex items-center gap-2 text-xs">
            <MessageSquare className="h-4 w-4 text-brand-primary" />
            <div>
              <h3 className="font-bold text-black dark:text-white uppercase font-display">Interactive Analyst Terminal</h3>
              <p className="text-[9px] text-brand-textMuted mt-0.5 font-mono">Pre-contextualized session for ID:{fund.scheme_code}</p>
            </div>
          </div>
          
          {/* Chat Messages */}
          <div className="flex-1 p-3 sm:p-4 overflow-y-auto space-y-4 scrollbar text-[11px] leading-relaxed" style={{ minHeight: '200px' }}>
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center text-brand-textMuted space-y-2">
                <MessageSquare className="h-6 w-6 opacity-35 text-brand-primary" />
                <p className="text-[9px]">Awaiting query. Ask about this fund's rolling performance, beta volatility, or expense ratios.</p>
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

          {/* Form */}
          <form onSubmit={handleSendChat} className="p-3 bg-brand-bg border-t border-brand-border flex gap-2">
            <input
              type="text"
              inputMode="text"
              placeholder="Query fund parameters..."
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              className="flex-1 bg-brand-surface border border-brand-border px-3.5 py-2 min-h-[44px] text-xs text-black dark:text-white focus:outline-none focus:border-brand-primary"
            />
            <button
              type="submit"
              disabled={chatLoading}
              className="bg-brand-primary hover:bg-brand-primaryHover disabled:opacity-50 text-black font-extrabold text-[9px] px-3 min-h-[44px] transition-colors border border-brand-primary"
            >
              EXEC
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
