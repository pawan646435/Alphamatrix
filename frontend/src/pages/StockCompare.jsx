import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Cpu, RefreshCw, BarChart2, Star, Check } from 'lucide-react';
import { useGetStocks, useGetStockComparison } from '../hooks/useStocks';
import StockComparisonChart from '../components/charts/StockComparisonChart';
import StockLogo from '../components/StockLogo';

export default function StockCompare() {
  const navigate = useNavigate();
  const { stocks, loading: loadingStocks, fetchStocks } = useGetStocks();
  const { comparison, loading: loadingComparison, error, fetchComparison } = useGetStockComparison();

  const [symbol1, setSymbol1] = useState('');
  const [symbol2, setSymbol2] = useState('');

  useEffect(() => {
    fetchStocks();
  }, [fetchStocks]);

  // Set default stocks when list is loaded
  useEffect(() => {
    if (stocks.length >= 2 && !symbol1 && !symbol2) {
      // Look for TCS and INFY or just pick first two
      const tcs = stocks.find(s => s.symbol === 'TCS');
      const infy = stocks.find(s => s.symbol === 'INFY');
      
      setSymbol1(tcs ? 'TCS' : stocks[0].symbol);
      setSymbol2(infy ? 'INFY' : stocks[1].symbol);
    }
  }, [stocks]);

  // Trigger comparison when symbols change
  useEffect(() => {
    if (symbol1 && symbol2 && symbol1 !== symbol2) {
      fetchComparison(symbol1, symbol2);
    }
  }, [symbol1, symbol2, fetchComparison]);

  const handleSwap = () => {
    const temp = symbol1;
    setSymbol1(symbol2);
    setSymbol2(temp);
  };

  // Format helpers
  const pct = (val) => (val !== null && val !== undefined ? `${(val * 100).toFixed(2)}%` : '—');
  const num = (val, dec = 2) => (val !== null && val !== undefined ? val.toFixed(dec) : '—');

  // Simple Markdown Parser for comparison verdict
  const parseVerdict = (text) => {
    if (!text) return null;
    
    // Split by Markdown headers (### or ##)
    const sections = text.split(/(?=###\s+)/);
    
    return sections.map((sec, idx) => {
      const match = sec.match(/^###\s+(.*)\n([\s\S]*)$/);
      if (match) {
        const title = match[1].trim();
        const content = match[2].trim();
        
        const html = content
          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
          .replace(/^-\s*(.*)$/gm, '• $1<br/>')
          .split('\n')
          .filter(line => line.trim())
          .join('<br/>');

        return (
          <div key={idx} className="space-y-2 border-b border-brand-border/40 pb-4 last:border-none">
            <h4 className="text-[10px] font-bold text-brand-primary uppercase tracking-wider font-display">{title}</h4>
            <p className="text-xs leading-relaxed font-sans text-brand-textMuted" dangerouslySetInnerHTML={{ __html: html }} />
          </div>
        );
      }
      
      const cleanText = sec
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/^-\s*(.*)$/gm, '• $1<br/>')
        .split('\n')
        .filter(line => line.trim())
        .join('<br/>');
      return (
        <p key={idx} className="text-xs leading-relaxed font-sans text-brand-textMuted" dangerouslySetInnerHTML={{ __html: cleanText }} />
      );
    });
  };

  const getMetricClass = (val1, val2, lowIsBetter = false) => {
    if (val1 === null || val1 === undefined || val2 === null || val2 === undefined) return ['', ''];
    if (val1 === val2) return ['', ''];
    const v1 = parseFloat(val1);
    const v2 = parseFloat(val2);
    if (isNaN(v1) || isNaN(v2)) return ['', ''];

    const betterClass = 'text-brand-success font-bold';
    const worseClass = 'text-brand-textMuted';

    if (lowIsBetter) {
      return v1 < v2 ? [betterClass, worseClass] : [worseClass, betterClass];
    } else {
      return v1 > v2 ? [betterClass, worseClass] : [worseClass, betterClass];
    }
  };

  return (
    <div className="space-y-8 pb-16">
      {/* Back Navigation */}
      <div className="flex justify-between items-center animate-fade-in-up">
        <button
          onClick={() => navigate('/stocks')}
          className="flex items-center gap-2 text-brand-textMuted hover:text-brand-primary transition-colors text-xs font-bold font-mono uppercase"
        >
          <ArrowLeft className="h-4 w-4" /> [Back to Equities Hub]
        </button>
        <span className="font-mono text-[9px] text-brand-textMuted uppercase">[SECURE_SESSION: active]</span>
      </div>

      {/* Header Selector Box */}
      <div className="relative border border-brand-border p-6 shadow-xl animate-fade-in-up bg-brand-surface">
        <div className="absolute top-2 left-2 text-brand-textMuted font-mono text-[9px]">+ [COMPARATIVE_ENGINE]</div>
        <div className="absolute top-2 right-2 text-brand-textMuted font-mono text-[9px]">[STABLE] +</div>

        <div className="flex flex-col md:flex-row items-center justify-between gap-6 pt-2">
          {/* Stock 1 Select */}
          <div className="w-full md:w-5/12 space-y-1">
            <label className="block text-[9px] font-bold text-brand-primary uppercase tracking-wider font-mono">PRIMARY EQUITY (s1)</label>
            <select
              value={symbol1}
              onChange={(e) => {
                if (e.target.value !== symbol2) setSymbol1(e.target.value);
              }}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border text-xs text-black dark:text-white focus:outline-none focus:border-brand-primary font-mono"
            >
              {stocks.map(s => (
                <option key={s.symbol} value={s.symbol} disabled={s.symbol === symbol2}>
                  {s.symbol} — {s.company_name}
                </option>
              ))}
            </select>
          </div>

          {/* Swap button */}
          <button
            onClick={handleSwap}
            disabled={!symbol1 || !symbol2}
            className="px-4 py-2 border border-brand-border hover:border-brand-primary bg-brand-bg text-[10px] font-bold font-mono transition-colors text-brand-primary self-end md:self-center"
          >
            ↔ SWAP
          </button>

          {/* Stock 2 Select */}
          <div className="w-full md:w-5/12 space-y-1">
            <label className="block text-[9px] font-bold text-brand-primary uppercase tracking-wider font-mono">COMPARISON TARGET (s2)</label>
            <select
              value={symbol2}
              onChange={(e) => {
                if (e.target.value !== symbol1) setSymbol2(e.target.value);
              }}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border text-xs text-black dark:text-white focus:outline-none focus:border-brand-primary font-mono"
            >
              {stocks.map(s => (
                <option key={s.symbol} value={s.symbol} disabled={s.symbol === symbol1}>
                  {s.symbol} — {s.company_name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {loadingComparison && !comparison ? (
        <div className="h-[40vh] flex flex-col items-center justify-center text-brand-textMuted font-mono">
          <RefreshCw className="h-6 w-6 animate-spin text-brand-primary mb-3" />
          <p className="text-[10px] tracking-wider uppercase">Aligning balance sheets and RAG comparative telemetry...</p>
        </div>
      ) : error ? (
        <div className="p-6 bg-brand-surface border border-brand-border text-center text-brand-danger font-mono text-xs uppercase tracking-wider">
          Error aligning comparison telemetry: {error}
        </div>
      ) : comparison ? (
        <div className="space-y-8 animate-fade-in">
          {/* Main Side-by-Side Comparison Panels */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            
            {/* Left: Metrics & Factors (Column Span 7) */}
            <div className="lg:col-span-7 space-y-8">
              
              {/* Metrics Table */}
              <div className="border border-brand-border bg-brand-surface shadow-xl p-6 space-y-4">
                <div className="flex justify-between items-center border-b border-brand-border pb-3">
                  <div className="flex items-center gap-2 text-brand-primary">
                    <BarChart2 className="h-4 w-4" />
                    <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">SIDE-BY-SIDE METRICS MATRIX</h3>
                  </div>
                  <span className="font-mono text-[9px] text-brand-textMuted">[METRIC_COMP_STABLE]</span>
                </div>

                <div className="overflow-x-auto scrollbar">
                  <table className="w-full font-mono text-xs text-left">
                    <thead>
                      <tr className="border-b border-brand-border/40 text-[9px] text-brand-textMuted uppercase tracking-wider">
                        <th className="py-2.5">Key Performance Indicator</th>
                        <th className="py-2.5 text-right font-bold text-brand-primary">{comparison.stock1.symbol}</th>
                        <th className="py-2.5 text-right font-bold text-orange-400">{comparison.stock2.symbol}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-brand-border/20">
                      <tr>
                        <td className="py-3 text-brand-textMuted">Company Name</td>
                        <td className="py-3 text-right font-bold text-black dark:text-white truncate max-w-[150px]">{comparison.stock1.company_name}</td>
                        <td className="py-3 text-right font-bold text-black dark:text-white truncate max-w-[150px]">{comparison.stock2.company_name}</td>
                      </tr>
                      <tr>
                        <td className="py-3 text-brand-textMuted">Sector</td>
                        <td className="py-3 text-right text-black dark:text-white">{comparison.stock1.sector}</td>
                        <td className="py-3 text-right text-black dark:text-white">{comparison.stock2.sector}</td>
                      </tr>
                      <tr>
                        <td className="py-3 text-brand-textMuted">Market Capitalization</td>
                        <td className="py-3 text-right text-black dark:text-white">₹{comparison.stock1.market_cap ? comparison.stock1.market_cap.toLocaleString('en-IN') : '—'} Cr</td>
                        <td className="py-3 text-right text-black dark:text-white">₹{comparison.stock2.market_cap ? comparison.stock2.market_cap.toLocaleString('en-IN') : '—'} Cr</td>
                      </tr>
                      {(() => {
                        const peC = getMetricClass(comparison.stock1.pe_ratio, comparison.stock2.pe_ratio, true);
                        const pbC = getMetricClass(comparison.stock1.pb_ratio, comparison.stock2.pb_ratio, true);
                        const roeC = getMetricClass(comparison.stock1.roe, comparison.stock2.roe, false);
                        const deC = getMetricClass(comparison.stock1.debt_equity, comparison.stock2.debt_equity, true);
                        const betaC = getMetricClass(comparison.stock1.beta, comparison.stock2.beta, true);
                        const alphaC = getMetricClass(comparison.stock1.alpha_score, comparison.stock2.alpha_score, false);
                        const cagr1yC = getMetricClass(comparison.stock1.cagr_1y, comparison.stock2.cagr_1y, false);
                        const cagr3yC = getMetricClass(comparison.stock1.cagr_3y, comparison.stock2.cagr_3y, false);

                        return (
                          <>
                            <tr>
                              <td className="py-3 text-brand-textMuted">P/E Ratio</td>
                              <td className={`py-3 text-right ${peC[0]}`}>{num(comparison.stock1.pe_ratio, 1)}</td>
                              <td className={`py-3 text-right ${peC[1]}`}>{num(comparison.stock2.pe_ratio, 1)}</td>
                            </tr>
                            <tr>
                              <td className="py-3 text-brand-textMuted">P/B Ratio</td>
                              <td className={`py-3 text-right ${pbC[0]}`}>{num(comparison.stock1.pb_ratio, 1)}</td>
                              <td className={`py-3 text-right ${pbC[1]}`}>{num(comparison.stock2.pb_ratio, 1)}</td>
                            </tr>
                            <tr>
                              <td className="py-3 text-brand-textMuted font-bold">Return on Equity (ROE)</td>
                              <td className={`py-3 text-right ${roeC[0]}`}>{comparison.stock1.roe ? `${comparison.stock1.roe.toFixed(1)}%` : '—'}</td>
                              <td className={`py-3 text-right ${roeC[1]}`}>{comparison.stock2.roe ? `${comparison.stock2.roe.toFixed(1)}%` : '—'}</td>
                            </tr>
                            <tr>
                              <td className="py-3 text-brand-textMuted">Debt/Equity Ratio</td>
                              <td className={`py-3 text-right ${deC[0]}`}>{num(comparison.stock1.debt_equity)}</td>
                              <td className={`py-3 text-right ${deC[1]}`}>{num(comparison.stock2.debt_equity)}</td>
                            </tr>
                            <tr>
                              <td className="py-3 text-brand-textMuted">Systematic Risk (Beta)</td>
                              <td className={`py-3 text-right ${betaC[0]}`}>{num(comparison.stock1.beta)}</td>
                              <td className={`py-3 text-right ${betaC[1]}`}>{num(comparison.stock2.beta)}</td>
                            </tr>
                            <tr>
                              <td className="py-3 text-brand-textMuted font-bold">1Y Trailing Return</td>
                              <td className={`py-3 text-right ${cagr1yC[0]}`}>{pct(comparison.stock1.cagr_1y)}</td>
                              <td className={`py-3 text-right ${cagr1yC[1]}`}>{pct(comparison.stock2.cagr_1y)}</td>
                            </tr>
                            <tr>
                              <td className="py-3 text-brand-textMuted font-bold">3Y Compounded CAGR</td>
                              <td className={`py-3 text-right ${cagr3yC[0]}`}>{pct(comparison.stock1.cagr_3y)}</td>
                              <td className={`py-3 text-right ${cagr3yC[1]}`}>{pct(comparison.stock2.cagr_3y)}</td>
                            </tr>
                            <tr className="bg-brand-primary/5 border-t border-brand-primary/20">
                              <td className="py-3 text-brand-primary font-bold">Overall Alpha Score</td>
                              <td className={`py-3 text-right ${alphaC[0]}`}>{comparison.stock1.alpha_score ? Math.round(comparison.stock1.alpha_score) : '—'} / 100</td>
                              <td className={`py-3 text-right ${alphaC[1]}`}>{comparison.stock2.alpha_score ? Math.round(comparison.stock2.alpha_score) : '—'} / 100</td>
                            </tr>
                          </>
                        );
                      })()}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* 6-Factor Comparison Bars */}
              <div className="border border-brand-border bg-brand-surface shadow-xl p-6 space-y-4">
                <div className="flex justify-between items-center border-b border-brand-border pb-3">
                  <div className="flex items-center gap-2 text-brand-primary">
                    <Star className="h-4 w-4" />
                    <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">6-FACTOR ALPHA BREAKDOWN COMPARISON</h3>
                  </div>
                  <span className="font-mono text-[9px] text-brand-textMuted">[FACTOR_POLAR_STABLE]</span>
                </div>

                <div className="space-y-4 font-mono text-xs pt-2">
                  {['fundamentals', 'valuation', 'momentum', 'risk', 'sentiment', 'macro'].map(factor => {
                    const score1 = comparison.alpha_score_breakdown1?.[factor] ?? 50;
                    const score2 = comparison.alpha_score_breakdown2?.[factor] ?? 50;

                    return (
                      <div key={factor} className="space-y-1.5">
                        <div className="flex justify-between items-center text-[9px]">
                          <span className="text-brand-primary font-semibold text-right w-12">{score1}</span>
                          <span className="text-brand-textMuted uppercase font-bold tracking-wider">{factor}</span>
                          <span className="text-orange-400 font-semibold text-left w-12">{score2}</span>
                        </div>
                        
                        {/* Dual matching progress bars */}
                        <div className="grid grid-cols-2 gap-2">
                          {/* Stock 1 Progress (Renders Right to Left) */}
                          <div className="w-full h-1.5 bg-brand-bg border border-brand-border/60 overflow-hidden flex justify-end">
                            <div 
                              className="h-full bg-brand-primary transition-all duration-1000 ease-out" 
                              style={{ width: `${score1}%` }}
                            />
                          </div>
                          {/* Stock 2 Progress (Renders Left to Right) */}
                          <div className="w-full h-1.5 bg-brand-bg border border-brand-border/60 overflow-hidden">
                            <div 
                              className="h-full bg-orange-400 transition-all duration-1000 ease-out" 
                              style={{ width: `${score2}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

            </div>

            {/* Right: AI Comparative Verdict (Column Span 5) */}
            <div className="lg:col-span-5 border border-brand-border bg-brand-surface shadow-xl p-6 min-h-[480px] space-y-6 flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-center border-b border-brand-border pb-3">
                  <div className="flex items-center gap-2 text-brand-primary">
                    <Cpu className="h-4 w-4 animate-pulse-subtle" />
                    <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">AI COMPARATIVE VERDICT REPORT</h3>
                  </div>
                  <span className="font-mono text-[9px] text-brand-textMuted uppercase">[RAG_TELEMETRY: aligned]</span>
                </div>

                <div className="space-y-6 pt-4 max-h-[640px] overflow-y-auto scrollbar pr-1">
                  {parseVerdict(comparison.comparison_verdict)}
                </div>
              </div>
              
              <div className="border-t border-brand-border/40 pt-3 text-[8px] font-mono text-brand-textMuted">
                * WARNING: RAG SYNTHESIZED VERDICTS ARE STATISTICAL OPINIONS; VERIFY IN MANAGEMENT CALLS.
              </div>
            </div>

          </div>

          {/* Interactive Chart Comparison */}
          <div className="w-full">
            <StockComparisonChart 
              priceHistory1={comparison.price_history1} 
              priceHistory2={comparison.price_history2} 
              symbol1={comparison.stock1.symbol} 
              symbol2={comparison.stock2.symbol} 
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
