import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Cpu, BookOpen, AlertTriangle } from 'lucide-react';
import { useGetSectorDetails } from '../hooks/useStocks';
import StockLogo from '../components/StockLogo';

export default function StockSector() {
  const { sectorName } = useParams();
  const navigate = useNavigate();
  const { sectorDetails, loading, error, fetchSectorDetails } = useGetSectorDetails();

  useEffect(() => {
    fetchSectorDetails(sectorName);
  }, [sectorName, fetchSectorDetails]);

  const handleStockClick = (symbol) => {
    navigate(`/stocks/detail/${symbol}`);
  };

  if (loading && !sectorDetails) {
    return (
      <div className="h-[60vh] flex flex-col items-center justify-center text-brand-textMuted font-mono">
        <RefreshCw className="h-6 w-6 animate-spin text-brand-primary mb-3" />
        <p className="text-[10px] tracking-wider">COMPILING SECTOR INTELLIGENCE TELEMETRY...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto mt-10 p-6 bg-brand-surface border border-brand-border text-center space-y-4 font-mono">
        <AlertTriangle className="h-10 w-10 text-brand-danger mx-auto" />
        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Sector Query Failure</h3>
        <p className="text-brand-textMuted text-xs leading-relaxed">{error}</p>
        <button
          onClick={() => navigate('/stocks')}
          className="bg-brand-primary hover:bg-[#cc4400] text-black text-[10px] font-bold px-4 py-2 border border-brand-primary transition-colors"
        >
          Return to Dashboard
        </button>
      </div>
    );
  }

  if (!sectorDetails) return null;

  const { sector, sector_score, growth_drivers, major_risks, top_stocks, ai_outlook } = sectorDetails;

  return (
    <div className="space-y-6 sm:space-y-8 pb-20">
      {/* Back Header */}
      <div className="animate-fade-in-up">
        <button
          onClick={() => navigate('/stocks')}
          className="flex items-center gap-2 text-brand-textMuted hover:text-brand-primary transition-colors text-xs font-bold font-mono uppercase min-h-[44px]"
        >
          <ArrowLeft className="h-4 w-4" /> [Back to Dashboard]
        </button>
      </div>

      {/* Sector Title Header */}
      <div 
        className="relative border border-brand-border p-6 md:p-8 shadow-xl animate-fade-in-up bg-brand-surface"
        style={{ animationDelay: '50ms' }}
      >
        <div className="absolute top-2 left-2 text-brand-textMuted font-mono text-[9px]">+ [SECTOR_LAB_SYSTEM]</div>
        <div className="absolute top-2 right-2 text-brand-textMuted font-mono text-[9px]">[ACTIVE] +</div>
        
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="space-y-1.5 min-w-0 pr-4">
            <span className="text-[9px] font-bold bg-brand-primary/10 border border-brand-primary/40 text-brand-primary px-2.5 py-0.5 uppercase font-mono">
              [SECTOR_PROFILE]
            </span>
            <h1 className="text-2xl md:text-3xl font-extrabold text-black dark:text-white tracking-wide font-display uppercase">
              {sector} Sector Lab
            </h1>
            <p className="text-[10px] text-brand-textMuted font-mono pt-0.5">
              SECTOR_OUTLOOK_INDEX: <span className="text-black dark:text-white font-bold">{sector.toUpperCase()}_INDEX</span>
            </p>
          </div>
          
          <div className="terminal-card bg-brand-bg/50 text-center px-6 py-3 border-brand-primary hover:shadow-[0_0_15px_rgba(197,168,128,0.15)] shrink-0 self-stretch md:self-auto flex flex-col justify-center">
            <span className="text-[9px] text-brand-textMuted uppercase font-bold tracking-wider font-display">Sector Score</span>
            <span className="text-2xl font-bold text-brand-primary font-mono mt-0.5">{sector_score}/100</span>
          </div>
        </div>
      </div>

      {/* Drivers and Risks Matrices */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
        {/* Growth Drivers */}
        <div className="terminal-card space-y-4">
          <div className="flex items-center gap-2 border-b border-brand-border pb-2">
            <BookOpen className="h-4 w-4 text-brand-success" />
            <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">Key Growth Drivers</h3>
          </div>
          <ul className="space-y-3 text-[11px] font-mono leading-relaxed text-brand-textMuted">
            {growth_drivers.map((driver, idx) => (
              <li key={idx} className="flex gap-2">
                <span className="text-brand-success font-bold shrink-0">[+]</span>
                <span>{driver}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Major Risks */}
        <div className="terminal-card space-y-4">
          <div className="flex items-center gap-2 border-b border-brand-border pb-2">
            <AlertTriangle className="h-4 w-4 text-brand-danger" />
            <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">Sector Risks & Headwinds</h3>
          </div>
          <ul className="space-y-3 text-[11px] font-mono leading-relaxed text-brand-textMuted">
            {major_risks.map((risk, idx) => (
              <li key={idx} className="flex gap-2">
                <span className="text-brand-danger font-bold shrink-0">[-]</span>
                <span>{risk}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* AI Outlook and Top Stocks Stack */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Outlook */}
        <div className="lg:col-span-5 border border-brand-border bg-brand-surface p-6 shadow-xl space-y-4 animate-fade-in-up h-full flex flex-col justify-between" style={{ animationDelay: '150ms' }}>
          <div>
            <div className="flex items-center gap-2 border-b border-brand-border pb-3 text-brand-primary">
              <Cpu className="h-4 w-4 animate-pulse-subtle" />
              <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider font-display">AI Sector Outlook</h3>
            </div>
            <p className="text-xs leading-relaxed text-brand-textMuted font-sans pt-4">
              {ai_outlook}
            </p>
          </div>
          <div className="text-[8px] font-mono text-brand-textMuted pt-4 border-t border-brand-border/40">
            [GENERATOR: Llama-3.3-70b-versatile // COMPILED: on-demand]
          </div>
        </div>

        {/* Top Stocks */}
        <div className="lg:col-span-7 space-y-4 animate-fade-in-up" style={{ animationDelay: '200ms' }}>
          <div className="flex justify-between items-center border-b border-brand-border pb-2">
            <h3 className="text-xs font-bold text-black dark:text-white uppercase tracking-wider">Top Seeded Stocks</h3>
            <span className="font-mono text-[9px] text-brand-textMuted">SORTED: Alpha Score</span>
          </div>

          <div className="bg-brand-surface border border-brand-border shadow-xl divide-y divide-brand-border">
            {top_stocks.map((s) => (
              <button
                key={s.symbol}
                onClick={() => handleStockClick(s.symbol)}
                className="w-full text-left p-4 hover:bg-brand-border/20 transition-colors flex items-center justify-between gap-4 group"
              >
                <div className="flex items-center gap-3 min-w-0 pr-3">
                  <StockLogo symbol={s.symbol} size="sm" />
                  <div className="truncate">
                    <span className="font-bold text-xs text-brand-primary block group-hover:underline">{s.symbol}</span>
                    <span className="text-[10px] text-brand-textMuted truncate block font-sans">{s.company_name}</span>
                  </div>
                </div>

                <div className="flex gap-3 sm:gap-6 font-mono text-[10px] shrink-0 text-right">
                  <div>
                    <span className="text-brand-textMuted block text-[8px] uppercase font-bold">3Y CAGR</span>
                    <span className="text-black dark:text-white font-bold">{s.cagr_3y ? `${(s.cagr_3y * 100).toFixed(1)}%` : '—'}</span>
                  </div>
                  <div className="hidden sm:block">
                    <span className="text-brand-textMuted block text-[8px] uppercase font-bold">PE</span>
                    <span className="text-black dark:text-white font-bold">{s.pe_ratio ? s.pe_ratio.toFixed(1) : '—'}</span>
                  </div>
                  <div className="bg-brand-bg px-2.5 py-1 border border-brand-border/60 rounded flex flex-col items-center min-w-[42px]">
                    <span className="text-[7px] text-brand-textMuted uppercase font-bold">ALPHA</span>
                    <span className="text-brand-primary font-bold text-xs">{s.alpha_score ? Math.round(s.alpha_score) : '—'}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
