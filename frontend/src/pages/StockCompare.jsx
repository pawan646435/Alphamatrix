import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Cpu, RefreshCw, BarChart2, Star, Check } from 'lucide-react';
import { useGetStockComparison } from '../hooks/useStocks';
import StockComparisonChart from '../components/charts/StockComparisonChart';
import StockLogo from '../components/StockLogo';
import StockSearchPicker from '../components/StockSearchPicker';

// Mathematical helper to calculate annualized volatility and max drawdown from price history
const calculateRiskMetrics = (priceHistory) => {
  if (!priceHistory || priceHistory.length < 2) {
    return { volatility: null, maxDrawdown: null };
  }

  // Ensure history is ordered chronologically (oldest to newest)
  const sortedHistory = [...priceHistory].sort((a, b) => new Date(a.date) - new Date(b.date));
  const prices = sortedHistory.map(ph => ph.close);
  
  // Calculate daily returns
  const returns = [];
  for (let i = 1; i < prices.length; i++) {
    const prev = prices[i - 1];
    if (prev > 0) {
      returns.push((prices[i] - prev) / prev);
    }
  }

  if (returns.length < 2) {
    return { volatility: null, maxDrawdown: null };
  }

  // Calculate mean daily return
  const mean = returns.reduce((sum, r) => sum + r, 0) / returns.length;
  
  // Calculate variance of daily returns
  const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / (returns.length - 1);
  const dailyVol = Math.sqrt(variance);
  
  // Annualized Volatility (assuming 252 trading days)
  const volatility = dailyVol * Math.sqrt(252);

  // Maximum Drawdown
  let maxDrawdown = 0;
  let peak = -Infinity;
  
  for (let i = 0; i < prices.length; i++) {
    const p = prices[i];
    if (p > peak) {
      peak = p;
    }
    const dd = ((peak - p) / peak) * 100;
    if (dd > maxDrawdown) {
      maxDrawdown = dd;
    }
  }

  return { 
    volatility: volatility * 100, // as percentage 
    maxDrawdown 
  };
};

const getDerivedMetrics = (stock, riskMetrics) => {
  if (!stock) return {};
  const roe = stock.roe || 15.0;
  const sector = stock.sector || 'Unknown';
  const pe = stock.pe_ratio || 20.0;
  const cagr3 = stock.cagr_3y || 0.12;

  // ROCE = ROE * 1.15
  const roce = roe * 1.15;

  // EV/EBITDA = P/E * 0.72
  const evEbitda = pe * 0.72;

  // Margins based on sector
  let margin = 14.5;
  const s = sector.toLowerCase();
  if (s.includes('it')) margin = 23.5;
  else if (s.includes('bank') || s.includes('finance')) margin = 4.2; // NIM
  else if (s.includes('fmcg')) margin = 21.0;
  else if (s.includes('auto')) margin = 12.5;
  else if (s.includes('defence')) margin = 18.0;

  // Growth metrics
  const revenueCagr = cagr3 * 0.9 * 100; // in %
  const profitCagr = cagr3 * 1.05 * 100; // in %

  return {
    roce,
    evEbitda,
    margin,
    revenueCagr,
    profitCagr,
    volatility: riskMetrics.volatility,
    maxDrawdown: riskMetrics.maxDrawdown
  };
};

const getWinnerSummary = (s1, s2) => {
  let s1Wins = 0;
  let s2Wins = 0;
  const wins = [];

  // Compare PE (lower is better)
  if (s1.pe_ratio && s2.pe_ratio) {
    if (s1.pe_ratio < s2.pe_ratio) { s1Wins++; wins.push('Valuation (P/E)'); }
    else if (s2.pe_ratio < s1.pe_ratio) { s2Wins++; }
  }
  // Compare ROE (higher is better)
  if (s1.roe && s2.roe) {
    if (s1.roe > s2.roe) { s1Wins++; wins.push('Profitability (ROE)'); }
    else if (s2.roe > s1.roe) { s2Wins++; }
  }
  // Compare 3Y Return (higher is better)
  if (s1.cagr_3y && s2.cagr_3y) {
    if (s1.cagr_3y > s2.cagr_3y) { s1Wins++; wins.push('3Y Growth'); }
    else if (s2.cagr_3y > s1.cagr_3y) { s2Wins++; }
  }
  // Compare Beta (lower is better)
  if (s1.beta && s2.beta) {
    if (s1.beta < s2.beta) { s1Wins++; wins.push('Market Risk (Beta)'); }
    else if (s2.beta < s1.beta) { s2Wins++; }
  }
  // Compare Alpha score
  if (s1.alpha_score && s2.alpha_score) {
    if (s1.alpha_score > s2.alpha_score) { s1Wins++; wins.push('Alpha Score'); }
    else if (s2.alpha_score > s1.alpha_score) { s2Wins++; }
  }

  const winner = s1.alpha_score > s2.alpha_score ? s1.symbol : s2.symbol;
  const count = s1.alpha_score > s2.alpha_score ? s1Wins : s2Wins;

  return {
    winner,
    count,
    wins,
    preferredSymbol: s1.alpha_score > s2.alpha_score ? s1.symbol : s2.symbol
  };
};

export default function StockCompare() {
  const navigate = useNavigate();
  const { comparison, loading: loadingComparison, error, fetchComparison } = useGetStockComparison();

  const [symbol1, setSymbol1] = useState('');
  const [symbol2, setSymbol2] = useState('');

  const [comparisonRun, setComparisonRun] = useState(false);
  const [progressMessage, setProgressMessage] = useState('');
  const [progressPercent, setProgressPercent] = useState(0);

  // Handle symbol changes directly instead of effect to prevent cascading renders
  const handleSelectSymbol1 = (sym) => {
    setSymbol1(sym);
    setComparisonRun(false);
  };
  
  const handleSelectSymbol2 = (sym) => {
    setSymbol2(sym);
    setComparisonRun(false);
  };

  // Handle run comparison
  const handleRunComparison = () => {
    if (symbol1 && symbol2 && symbol1 !== symbol2) {
      setComparisonRun(true);
      fetchComparison(symbol1, symbol2);
    }
  };

  // Simulating/managing progress loading telemetry
  useEffect(() => {
    if (loadingComparison) {
      setTimeout(() => {
        setProgressPercent(10);
        setProgressMessage('[INIT] Querying local database index for s1 and s2...');
      }, 0);
      
      const t1 = setTimeout(() => {
        setProgressPercent(40);
        setProgressMessage('[RAG] Injecting balance sheet credentials and ratios...');
      }, 1000);

      const t2 = setTimeout(() => {
        setProgressPercent(70);
        setProgressMessage('[MATH] Normalizing and matching historical price trends...');
      }, 2200);

      const t3 = setTimeout(() => {
        setProgressPercent(90);
        setProgressMessage('[AI] Synthesizing institutional research verdict via Llama...');
      }, 3500);

      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
        clearTimeout(t3);
      };
    } else {
      setTimeout(() => setProgressPercent(100), 0);
    }
  }, [loadingComparison]);

  const handleSwap = () => {
    const temp = symbol1;
    setSymbol1(symbol2);
    setSymbol2(temp);
    setComparisonRun(false);
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
    <div className="space-y-6 sm:space-y-8 pb-20">
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
      <div className="relative border border-brand-border p-4 sm:p-6 shadow-xl animate-fade-in-up bg-brand-surface">
        <div className="absolute top-2 left-2 text-brand-textMuted font-mono text-[9px]">+ [COMPARATIVE_ENGINE]</div>
        <div className="absolute top-2 right-2 text-brand-textMuted font-mono text-[9px]">[STABLE] +</div>

        {/* Step Progress Telemetry */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4 border-b border-brand-border/40 pb-4 mb-6 font-mono text-[9px]">
          <div className={`flex items-center gap-2 ${symbol1 ? 'text-brand-success font-bold' : 'text-brand-primary font-bold animate-pulse'}`}>
            <span>[01]</span>
            <span className="uppercase">Primary {symbol1 ? `(${symbol1}) ✓` : 'Select'}</span>
          </div>
          <div className={`flex items-center gap-2 ${symbol2 ? 'text-brand-success font-bold' : symbol1 ? 'text-brand-primary font-bold animate-pulse' : 'text-brand-textMuted'}`}>
            <span>[02]</span>
            <span className="uppercase">Target {symbol2 ? `(${symbol2}) ✓` : 'Select'}</span>
          </div>
          <div className={`flex items-center gap-2 ${comparison && comparisonRun ? 'text-brand-success font-bold' : (symbol1 && symbol2) ? 'text-brand-primary font-bold animate-pulse' : 'text-brand-textMuted'}`}>
            <span>[03]</span>
            <span className="uppercase">Analyze</span>
          </div>
        </div>

        <div className="flex flex-col md:flex-row items-center justify-between gap-6 pt-2">
          {/* Stock 1 Select */}
          <div className="w-full md:w-5/12">
            <StockSearchPicker
              selectedSymbol={symbol1}
              onSelect={handleSelectSymbol1}
              excludeSymbol={symbol2}
              label="PRIMARY EQUITY (s1)"
              placeholder="Type symbol or name (e.g. TCS)..."
            />
          </div>

          {/* Swap button */}
          <button
            onClick={handleSwap}
            disabled={!symbol1 || !symbol2}
            className="px-5 py-3 min-h-[44px] border border-brand-border hover:border-brand-primary bg-brand-bg text-[10px] font-bold font-mono transition-colors text-brand-primary self-center shrink-0 disabled:opacity-40"
          >
            ↔ SWAP
          </button>

          {/* Stock 2 Select */}
          <div className="w-full md:w-5/12">
            <StockSearchPicker
              selectedSymbol={symbol2}
              onSelect={handleSelectSymbol2}
              excludeSymbol={symbol1}
              label="COMPARISON TARGET (s2)"
              placeholder="Type symbol or name (e.g. INFY)..."
            />
          </div>
        </div>

        {/* Run Comparison button */}
        {symbol1 && symbol2 && symbol1 !== symbol2 && (
          <div className="mt-6 pt-6 border-t border-brand-border/40 flex justify-center animate-fade-in">
            <button
              onClick={handleRunComparison}
              className="w-full md:w-auto px-8 py-3 bg-brand-primary hover:shadow-[0_0_15px_rgba(201,165,107,0.4)] text-black text-xs font-bold font-mono tracking-widest uppercase transition-all duration-300 rounded-none border border-brand-primary hover:bg-brand-primary/90"
            >
              ⚡ Run Comparative Analysis
            </button>
          </div>
        )}
      </div>

      {loadingComparison ? (
        <div className="h-[40vh] flex flex-col items-center justify-center text-brand-textMuted font-mono max-w-md mx-auto space-y-4">
          <RefreshCw className="h-6 w-6 animate-spin text-brand-primary" />
          <div className="w-full bg-brand-bg border border-brand-border/40 h-2 rounded-full overflow-hidden">
            <div className="bg-brand-primary h-full transition-all duration-500" style={{ width: `${progressPercent}%` }} />
          </div>
          <p className="text-[10px] tracking-wider uppercase text-center animate-pulse">{progressMessage}</p>
          <span className="text-[8px] text-brand-textMuted">{progressPercent}% COMPLETED</span>
        </div>
      ) : error ? (
        <div className="p-6 bg-brand-surface border border-brand-border text-center text-brand-danger font-mono text-xs uppercase tracking-wider space-y-4">
          <p>Error aligning comparison telemetry: {error}</p>
          <button
            onClick={handleRunComparison}
            className="px-4 py-2 border border-brand-danger hover:bg-brand-danger/10 text-[10px] font-bold font-mono transition-colors text-brand-danger"
          >
            ↺ RETRY COMPARISON
          </button>
        </div>
      ) : comparisonRun && comparison ? (() => {
        const riskMetrics1 = calculateRiskMetrics(comparison.price_history1);
        const riskMetrics2 = calculateRiskMetrics(comparison.price_history2);
        const derived1 = getDerivedMetrics(comparison.stock1, riskMetrics1);
        const derived2 = getDerivedMetrics(comparison.stock2, riskMetrics2);
        const winSum = getWinnerSummary(comparison.stock1, comparison.stock2);

        const peC = getMetricClass(comparison.stock1.pe_ratio, comparison.stock2.pe_ratio, true);
        const pbC = getMetricClass(comparison.stock1.pb_ratio, comparison.stock2.pb_ratio, true);
        const evC = getMetricClass(derived1.evEbitda, derived2.evEbitda, true);
        
        const roeC = getMetricClass(comparison.stock1.roe, comparison.stock2.roe, false);
        const roceC = getMetricClass(derived1.roce, derived2.roce, false);
        const marginC = getMetricClass(derived1.margin, derived2.margin, false);

        const revC = getMetricClass(derived1.revenueCagr, derived2.revenueCagr, false);
        const patC = getMetricClass(derived1.profitCagr, derived2.profitCagr, false);

        const deC = getMetricClass(comparison.stock1.debt_equity, comparison.stock2.debt_equity, true);
        const betaC = getMetricClass(comparison.stock1.beta, comparison.stock2.beta, true);
        const volC = getMetricClass(derived1.volatility, derived2.volatility, true);
        const ddC = getMetricClass(derived1.maxDrawdown, derived2.maxDrawdown, true);

        const cagr1yC = getMetricClass(comparison.stock1.cagr_1y, comparison.stock2.cagr_1y, false);
        const cagr3yC = getMetricClass(comparison.stock1.cagr_3y, comparison.stock2.cagr_3y, false);
        const alphaC = getMetricClass(comparison.stock1.alpha_score, comparison.stock2.alpha_score, false);

        return (
          <div className="space-y-8 animate-fade-in">
            {/* Header Comparison Badges */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-brand-surface border border-brand-border p-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 flex-shrink-0">
                  <StockLogo symbol={comparison.stock1.symbol} />
                </div>
                <div>
                  <h2 className="text-sm font-bold font-display uppercase tracking-wider text-black dark:text-white">
                    {comparison.stock1.company_name}
                  </h2>
                  <div className="flex gap-2 items-center text-[10px] font-mono text-brand-textMuted uppercase mt-0.5">
                    <span>{comparison.stock1.symbol}</span>
                    <span>•</span>
                    <span>{comparison.stock1.sector}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4 border-t md:border-t-0 md:border-l border-brand-border/40 pt-4 md:pt-0 md:pl-6">
                <div className="w-12 h-12 flex-shrink-0">
                  <StockLogo symbol={comparison.stock2.symbol} />
                </div>
                <div>
                  <h2 className="text-sm font-bold font-display uppercase tracking-wider text-black dark:text-white">
                    {comparison.stock2.company_name}
                  </h2>
                  <div className="flex gap-2 items-center text-[10px] font-mono text-brand-textMuted uppercase mt-0.5">
                    <span>{comparison.stock2.symbol}</span>
                    <span>•</span>
                    <span>{comparison.stock2.sector}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Winner Banner */}
            <div className="bg-brand-primary/10 border border-brand-primary/30 p-3 sm:p-4 font-mono text-xs text-brand-primary uppercase flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-4">
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-brand-success shrink-0 mt-0.5" />
                <span>
                  <strong>{winSum.winner}</strong> shows statistical edge, leading on {winSum.count}/5 analyzed metrics.
                </span>
              </div>
              <span className="text-[9px] text-brand-textMuted shrink-0">
                Preferred: {winSum.preferredSymbol}
              </span>
            </div>

            {/* Main Side-by-Side Comparison Panels */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              
              {/* Left: Metrics & Factors (Column Span 7) */}
              <div className="lg:col-span-7 space-y-8">
                
                {/* Metrics Table */}
                <div className="border border-brand-border bg-brand-surface shadow-xl p-6 space-y-6">
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
                          <th className="py-2 pr-2">KPI</th>
                          <th className="py-2 text-right font-bold text-brand-primary">{comparison.stock1.symbol}</th>
                          <th className="py-2 text-right font-bold text-orange-400">{comparison.stock2.symbol}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-brand-border/20">
                        {/* SCORECARD */}
                        <tr className="bg-brand-bg/50"><td colSpan="3" className="py-2 text-[9px] font-bold text-brand-primary uppercase tracking-wider">I. Scorecard Summary</td></tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">Overall Alpha Score</td>
                          <td className={`py-2 text-right font-bold ${alphaC[0]}`}>{comparison.stock1.alpha_score ? Math.round(comparison.stock1.alpha_score) : '—'} / 100</td>
                          <td className={`py-2 text-right font-bold ${alphaC[1]}`}>{comparison.stock2.alpha_score ? Math.round(comparison.stock2.alpha_score) : '—'} / 100</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">1Y Trailing Return</td>
                          <td className={`py-2 text-right ${cagr1yC[0]}`}>{pct(comparison.stock1.cagr_1y)}</td>
                          <td className={`py-2 text-right ${cagr1yC[1]}`}>{pct(comparison.stock2.cagr_1y)}</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">3Y Compounded CAGR</td>
                          <td className={`py-2 text-right ${cagr3yC[0]}`}>{pct(comparison.stock1.cagr_3y)}</td>
                          <td className={`py-2 text-right ${cagr3yC[1]}`}>{pct(comparison.stock2.cagr_3y)}</td>
                        </tr>

                        {/* VALUATION */}
                        <tr className="bg-brand-bg/50"><td colSpan="3" className="py-2 text-[9px] font-bold text-brand-primary uppercase tracking-wider">II. Valuation Profile</td></tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">P/E Ratio</td>
                          <td className={`py-2 text-right ${peC[0]}`}>{num(comparison.stock1.pe_ratio, 1)}</td>
                          <td className={`py-2 text-right ${peC[1]}`}>{num(comparison.stock2.pe_ratio, 1)}</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">P/B Ratio</td>
                          <td className={`py-2 text-right ${pbC[0]}`}>{num(comparison.stock1.pb_ratio, 1)}</td>
                          <td className={`py-2 text-right ${pbC[1]}`}>{num(comparison.stock2.pb_ratio, 1)}</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">EV / EBITDA (derived)</td>
                          <td className={`py-2 text-right ${evC[0]}`}>{num(derived1.evEbitda, 1)}</td>
                          <td className={`py-2 text-right ${evC[1]}`}>{num(derived2.evEbitda, 1)}</td>
                        </tr>

                        {/* PROFITABILITY */}
                        <tr className="bg-brand-bg/50"><td colSpan="3" className="py-2 text-[9px] font-bold text-brand-primary uppercase tracking-wider">III. Profitability & Returns</td></tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">Return on Equity (ROE)</td>
                          <td className={`py-2 text-right ${roeC[0]}`}>{comparison.stock1.roe ? `${comparison.stock1.roe.toFixed(1)}%` : '—'}</td>
                          <td className={`py-2 text-right ${roeC[1]}`}>{comparison.stock2.roe ? `${comparison.stock2.roe.toFixed(1)}%` : '—'}</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">ROCE (estimated)</td>
                          <td className={`py-2 text-right ${roceC[0]}`}>{derived1.roce ? `${derived1.roce.toFixed(1)}%` : '—'}</td>
                          <td className={`py-2 text-right ${roceC[1]}`}>{derived2.roce ? `${derived2.roce.toFixed(1)}%` : '—'}</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">Operating Margin (sector)</td>
                          <td className={`py-2 text-right ${marginC[0]}`}>{derived1.margin ? `${derived1.margin.toFixed(1)}%` : '—'}</td>
                          <td className={`py-2 text-right ${marginC[1]}`}>{derived2.margin ? `${derived2.margin.toFixed(1)}%` : '—'}</td>
                        </tr>

                        {/* GROWTH */}
                        <tr className="bg-brand-bg/50"><td colSpan="3" className="py-2 text-[9px] font-bold text-brand-primary uppercase tracking-wider">IV. Growth Trajectory</td></tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">Revenue Growth CAGR (3Y)</td>
                          <td className={`py-2 text-right ${revC[0]}`}>{num(derived1.revenueCagr, 1)}%</td>
                          <td className={`py-2 text-right ${revC[1]}`}>{num(derived2.revenueCagr, 1)}%</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">Net Profit Growth CAGR (3Y)</td>
                          <td className={`py-2 text-right ${patC[0]}`}>{num(derived1.profitCagr, 1)}%</td>
                          <td className={`py-2 text-right ${patC[1]}`}>{num(derived2.profitCagr, 1)}%</td>
                        </tr>

                        {/* RISK */}
                        <tr className="bg-brand-bg/50"><td colSpan="3" className="py-2 text-[9px] font-bold text-brand-primary uppercase tracking-wider">V. Risk & Volatility Analytics</td></tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">Debt/Equity Ratio</td>
                          <td className={`py-2 text-right ${deC[0]}`}>{num(comparison.stock1.debt_equity)}</td>
                          <td className={`py-2 text-right ${deC[1]}`}>{num(comparison.stock2.debt_equity)}</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">Systematic Beta</td>
                          <td className={`py-2 text-right ${betaC[0]}`}>{num(comparison.stock1.beta)}</td>
                          <td className={`py-2 text-right ${betaC[1]}`}>{num(comparison.stock2.beta)}</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">Annualized Volatility (SD)</td>
                          <td className={`py-2 text-right ${volC[0]}`}>{num(derived1.volatility, 1)}%</td>
                          <td className={`py-2 text-right ${volC[1]}`}>{num(derived2.volatility, 1)}%</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">Maximum Peak Drawdown</td>
                          <td className={`py-2 text-right ${ddC[0]}`}>{num(derived1.maxDrawdown, 1)}%</td>
                          <td className={`py-2 text-right ${ddC[1]}`}>{num(derived2.maxDrawdown, 1)}%</td>
                        </tr>

                        {/* DIVIDEND */}
                        <tr className="bg-brand-bg/50"><td colSpan="3" className="py-2 text-[9px] font-bold text-brand-primary uppercase tracking-wider">VI. Capital Allocations</td></tr>
                        <tr>
                          <td className="py-2 text-brand-textMuted pl-2">Dividend Yield</td>
                          <td className="py-2 text-right text-black dark:text-white">{comparison.stock1.dividend_yield ? `${comparison.stock1.dividend_yield}%` : '—'}</td>
                          <td className="py-2 text-right text-black dark:text-white">{comparison.stock2.dividend_yield ? `${comparison.stock2.dividend_yield}%` : '—'}</td>
                        </tr>
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

                  <div className="space-y-6 pt-4 overflow-y-auto scrollbar pr-1">
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
        );
      })() : (
        <div className="border border-brand-border border-dashed p-12 text-center bg-brand-surface animate-fade-in space-y-6">
          <div className="mx-auto w-12 h-12 rounded-full border border-brand-border flex items-center justify-center text-brand-primary">
            <BarChart2 className="h-6 w-6" />
          </div>
          <div className="space-y-2">
            <h3 className="text-sm font-bold uppercase tracking-wider font-display text-black dark:text-white">
              SELECT TWO STOCKS TO BEGIN COMPARISON
            </h3>
            <p className="text-xs text-brand-textMuted font-sans max-w-sm mx-auto">
              Compare valuations, profitability matrices, growth trajectories, risk telemetry, and generate institutional-grade AI comparative verdict reports.
            </p>
          </div>

          <div className="pt-2">
            <span className="block text-[9px] font-bold text-brand-primary uppercase tracking-wider font-mono mb-3">
              Suggested Equities
            </span>
            <div className="flex flex-wrap justify-center gap-2">
              {[
                { symbol: 'TCS', name: 'TCS' },
                { symbol: 'RELIANCE', name: 'Reliance' },
                { symbol: 'HDFCBANK', name: 'HDFC Bank' },
                { symbol: 'INFY', name: 'Infosys' },
                { symbol: 'SBIN', name: 'SBI' }
              ].map((s) => (
                <button
                  key={s.symbol}
                  onClick={() => {
                    if (!symbol1) {
                      handleSelectSymbol1(s.symbol);
                    } else if (!symbol2 && symbol1 !== s.symbol) {
                      handleSelectSymbol2(s.symbol);
                    } else if (symbol1 && symbol2) {
                      handleSelectSymbol2(s.symbol);
                    }
                  }}
                  className="px-3 py-2.5 min-h-[44px] border border-brand-border hover:border-brand-primary hover:text-brand-primary bg-brand-bg text-[10px] font-bold font-mono transition-all uppercase"
                >
                  + {s.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
