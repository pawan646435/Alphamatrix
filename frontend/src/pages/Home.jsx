import React from 'react';
import { useNavigate } from 'react-router-dom';
import { TrendingUp, Layers, Star, Cpu } from 'lucide-react';
import { useFundList } from '../hooks/useQueries';
import RiskScatterplot from '../components/charts/RiskScatterplot';
import GlobalSearch from '../components/GlobalSearch';
import { CardSkeleton } from '../components/skeletons/Skeletons';

export default function Home() {
  const navigate = useNavigate();
  const { data: funds = [], isLoading: fundsLoading } = useFundList();

  const handleCategoryClick = (category) => {
    navigate(`/explorer?category=${encodeURIComponent(category)}`);
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
        className="relative border border-brand-border p-5 sm:p-10 md:p-14 overflow-hidden flex flex-col items-center text-center animate-fade-in-up bg-brand-surface"
      >
        {/* Subtle corner markers — one on mobile, full pair on desktop */}
        <div className="absolute top-3 left-3 text-brand-textMuted/40 select-none font-mono text-[8px] sm:text-[9px] tracking-widest">ALPHAMATRIX</div>
        <div className="hidden sm:block absolute top-3 right-3 text-brand-textMuted/40 select-none font-mono text-[9px] tracking-widest">RESEARCH PLATFORM</div>

        {/* Subtle gradient accent */}
        <div className="absolute inset-0 bg-gradient-to-b from-brand-primary/4 via-transparent to-brand-primary/4 opacity-40 pointer-events-none" />

        {/* Platform badge */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-brand-primary/8 border border-brand-primary/30 text-brand-primary text-[9px] sm:text-[10px] font-mono tracking-widest mb-4 sm:mb-7">
          <Cpu className="h-3 w-3" />
          <span>Quantitative Intelligence Engine · v2.0</span>
        </div>

        {/* Clean Institutional Headline */}
        <h1 className="font-display text-[1.6rem] sm:text-[2.1rem] md:text-[3rem] font-bold text-black dark:text-white leading-[1.15] sm:leading-[1.12] tracking-[-0.03em] max-w-3xl">
          Navigate Mutual Funds with{' '}
          <span className="text-brand-primary">Quantitative Rigor</span>
        </h1>

        {/* Subtitle — lighter weight, relaxed line height */}
        <p className="text-brand-textMuted text-[0.8rem] sm:text-[0.9rem] md:text-[1rem] max-w-xl mt-3 sm:mt-5 leading-[1.6] sm:leading-[1.7] font-normal">
          Rolling Sharpe, Sortino, CAGR, and CAPM Beta — computed across 10,000+&nbsp;Indian mutual funds.
          Institutional-grade ratings. AI&nbsp;explanations. Zero&nbsp;guesswork.
        </p>

        {/* Master Search Input */}
        <div className="mt-5 sm:mt-9 w-full flex justify-center">
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
          className="lg:col-span-7 min-h-[420px] sm:min-h-[480px] animate-fade-in-up"
          style={{ animationDelay: '300ms' }}
        >
          <RiskScatterplot funds={funds} />
        </div>
      </div>
    </div>
  );
}
