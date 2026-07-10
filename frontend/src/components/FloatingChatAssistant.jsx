import React, { useEffect, useState, useMemo } from 'react';
import { useMatch, useLocation } from 'react-router-dom';
import { MessageSquare, Cpu } from 'lucide-react';
import { useStockAIChat } from '../hooks/useStocks';
import { useAIChat } from '../hooks/useFunds';
import { useStockMetrics, useStockMeta } from '../hooks/useQueries';
import AnalystResponseCard from './AnalystResponseCard';

const PILLAR_LABELS = {
  fundamental_score: 'Fundamental',
  valuation_score: 'Valuation',
  technical_score: 'Technical',
  risk_score: 'Risk',
  sector_relative_score: 'Sector Relative',
};

/** Picks the weakest/strongest scored pillar for a loaded stock so suggested
 * chips ask about *this* stock's actual profile instead of generic questions. */
function pillarExtremes(metrics) {
  if (!metrics) return null;
  const entries = Object.keys(PILLAR_LABELS)
    .map((key) => ({ key, label: PILLAR_LABELS[key], value: metrics[key] }))
    .filter((e) => typeof e.value === 'number');
  if (entries.length === 0) return null;
  const weakest = entries.reduce((a, b) => (b.value < a.value ? b : a));
  const strongest = entries.reduce((a, b) => (b.value > a.value ? b : a));
  return { weakest, strongest };
}

function buildSuggestedChips({ symbol, metrics }) {
  if (symbol) {
    if (metrics && metrics.alpha_score != null) {
      const extremes = pillarExtremes(metrics);
      const chips = [];
      if (extremes) {
        chips.push(`Why is ${extremes.weakest.label} scored ${Math.round(extremes.weakest.value)}?`);
        chips.push(`What's driving the ${extremes.strongest.label} score?`);
      }
      chips.push(`Is ${symbol} a buy right now?`);
      chips.push(`What is the future outlook for ${symbol}?`);
      return chips.slice(0, 4);
    }
    return [`Is ${symbol} a buy?`, `Explain the Alpha Score for ${symbol}.`];
  }
  return [
    "What's the current market regime?",
    'Explain the Sharpe ratio.',
    'Compare large-cap vs mid-cap funds.',
    'How is the Alpha Score calculated?',
  ];
}

// Single unified floating AI chat panel, mounted once at the app root so it's
// visible on every route. Context-aware: on a stock detail page it binds to
// the grounded /stocks/chat tool-calling agent with that page's symbol
// auto-injected (see ai_agent.run_stock_chat); on a fund detail page it binds
// scheme_code the same way; elsewhere it's the general-purpose stock/market
// analyst. Replaces the old per-page FloatingChatAssistant usages and the
// inline "Interactive Analyst Terminal" block on StockDetail.jsx — one
// grounding implementation, one place to look for AI chat across the app.
export default function FloatingChatAssistant() {
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessage, setChatMessage] = useState('');
  const location = useLocation();

  const stockMatch = useMatch('/stocks/detail/:symbol');
  const fundMatch1 = useMatch('/detail/:schemeCode');
  const fundMatch2 = useMatch('/funds/detail/:schemeCode');

  const symbol = stockMatch?.params?.symbol || null;
  const schemeCode = fundMatch1?.params?.schemeCode || fundMatch2?.params?.schemeCode || null;

  // Route domain: fund pages use the funds analyst (/ai/chat); everything
  // else (stocks pages, dashboard, news, etc.) uses the equity analyst
  // (/stocks/chat), which is general-purpose without a symbol.
  const isFundDomain = location.pathname === '/'
    || location.pathname.startsWith('/funds')
    || location.pathname.startsWith('/detail')
    || location.pathname.startsWith('/explorer');

  const stockChat = useStockAIChat();
  const fundChat = useAIChat();
  const active = isFundDomain ? fundChat : stockChat;
  const { messages, loading: chatLoading, sendMessage } = active;

  // Loaded (cached by react-query) so this costs nothing extra on the stock
  // detail page itself, where the same queries are already in flight — this
  // is what powers both the pillar-aware suggested chips and the grounded
  // footer. `sector` lives on the /meta endpoint, not /metrics.
  const { data: metrics } = useStockMetrics(symbol, { enabled: !!symbol });
  const { data: meta } = useStockMeta(symbol, { enabled: !!symbol });

  useEffect(() => {
    if (!chatOpen) return;
    const isMobile = window.matchMedia('(max-width: 639px)').matches;
    if (!isMobile) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prevOverflow; };
  }, [chatOpen]);

  const title = symbol ? `ANALYST.EXE — ${symbol}` : isFundDomain ? 'COGNITIVE_ANALYST.EXE' : 'EQUITY_ANALYST.EXE';
  const subtitle = symbol
    ? `Pre-contextualized session for ${symbol}`
    : isFundDomain
    ? 'General fund & portfolio analyst'
    : 'General market & equity analyst';
  const placeholder = symbol
    ? `Query analyst about ${symbol}...`
    : isFundDomain
    ? 'Query system database...'
    : 'Ask about PE ratios, Beta, or request diagnostics...';
  const emptyStateText = symbol
    ? `Ready to process equities queries. Ask things like: "Is ${symbol} a buy?" or "Explain its high P/E ratio."`
    : isFundDomain
    ? 'Ready to process queries. Ask about metrics, CAPM calculations, or portfolio risk parameters.'
    : 'Equity intelligence terminal online. Ask about PE ratios, Beta metrics, or request stock diagnostics.';

  const suggestedChips = useMemo(
    () => buildSuggestedChips({ symbol, metrics }),
    [symbol, metrics]
  );

  const groundedContext = symbol && metrics && metrics.alpha_score != null
    ? { alpha_score: metrics.alpha_score, sector: meta?.sector, verdict: metrics.investor_verdict }
    : null;

  const submit = (text) => {
    const trimmed = (text ?? chatMessage).trim();
    if (!trimmed) return;
    if (isFundDomain) {
      sendMessage(trimmed, schemeCode, messages);
    } else {
      sendMessage(trimmed, symbol, messages, groundedContext);
    }
    setChatMessage('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    submit();
  };

  return (
    <>
      {chatOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 sm:hidden"
          onClick={() => setChatOpen(false)}
          aria-hidden="true"
        />
      )}
      <div className={`fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-50 transition-all duration-300 ${chatOpen ? 'w-[calc(100vw-32px)] sm:w-[380px] h-[75vh] sm:h-[560px]' : 'w-12 h-12'}`}>
        {chatOpen ? (
          <div className="w-full h-full bg-brand-surface border border-brand-border shadow-2xl flex flex-col overflow-hidden font-mono">
            <div className="bg-brand-bg border-b border-brand-border px-4 py-3 flex justify-between items-center text-xs">
              <div className="flex items-center gap-1.5 font-display min-w-0">
                <span className="w-2 h-2 rounded-full bg-brand-primary animate-pulse shrink-0" />
                <div className="min-w-0">
                  <span className="font-bold text-black dark:text-white block truncate">{title}</span>
                  <span className="text-[8px] text-brand-textMuted block truncate normal-case">{subtitle}</span>
                </div>
              </div>
              <button
                onClick={() => setChatOpen(false)}
                className="text-brand-textMuted hover:text-brand-primary font-bold shrink-0 ml-2"
              >
                [MIN]
              </button>
            </div>

            <div className="flex-1 p-3 overflow-y-auto space-y-3 scrollbar text-[11px] leading-relaxed">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center text-brand-textMuted px-2 space-y-3">
                  <Cpu className="h-6 w-6 opacity-30 text-brand-primary" />
                  <p className="text-[10px]">{emptyStateText}</p>
                  {suggestedChips.length > 0 && (
                    <div className="flex flex-wrap justify-center gap-1.5 pt-1">
                      {suggestedChips.map((chip, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => submit(chip)}
                          className="text-[9px] font-mono px-2 py-1 border border-brand-border hover:border-brand-primary hover:text-brand-primary text-brand-textMuted transition-colors"
                        >
                          {chip}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                messages.map((m, idx) => <AnalystResponseCard key={idx} message={m} />)
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

            <form onSubmit={handleSubmit} className="p-3 bg-brand-bg border-t border-brand-border flex gap-2">
              <input
                type="text"
                inputMode="text"
                placeholder={placeholder}
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
            title="AI Analyst"
          >
            <MessageSquare className="h-5 w-5" />
          </button>
        )}
      </div>
    </>
  );
}
