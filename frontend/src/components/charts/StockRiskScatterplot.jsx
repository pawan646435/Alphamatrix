import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis, Label } from 'recharts';

export default function StockRiskScatterplot({ stocks = [] }) {
  const navigate = useNavigate();

  // Pre-process data
  const data = React.useMemo(() => {
    return stocks
      .filter(s => s.beta !== null && s.cagr_3y !== null)
      .map(s => ({
        symbol: s.symbol,
        name: s.company_name,
        sector: s.sector,
        x: s.beta,                                    // Beta on X
        y: Math.round((s.cagr_3y || 0) * 1000) / 10,  // CAGR % on Y
        z: Math.max(10, s.alpha_score || 50),        // Alpha Score for size
        alpha_score: s.alpha_score,
        cagr_1y: s.cagr_1y ? Math.round(s.cagr_1y * 1000) / 10 : 0
      }));
  }, [stocks]);

  // Color mapping based on Sector
  const getSectorColor = (sector) => {
    switch (sector) {
      case 'IT': return '#6366f1';        // Indigo
      case 'Banking': return '#06b6d4';   // Cyan
      case 'Auto': return '#f43f5e';      // Rose
      case 'Defence': return '#10b981';   // Emerald
      case 'Energy': return '#a855f7';    // Purple
      case 'FMCG': return '#f59e0b';      // Amber
      default: return '#9ca3af';          // Gray
    }
  };

  const sectorsList = ['IT', 'Banking', 'Auto', 'Defence', 'Energy', 'FMCG'];

  // Group by sector for chart legend
  const groupedData = React.useMemo(() => {
    const groups = {};
    data.forEach(item => {
      if (!groups[item.sector]) {
        groups[item.sector] = [];
      }
      groups[item.sector].push(item);
    });
    return Object.entries(groups).map(([sector, items]) => ({
      sector,
      items,
      color: getSectorColor(sector)
    }));
  }, [data]);

  // Custom scatter Tooltip
  const renderTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const info = payload[0].payload;
      return (
        <div className="glassmorphism p-4 rounded-lg border border-brand-border shadow-2xl max-w-sm font-mono text-xs">
          <p className="text-black dark:text-white font-bold text-sm leading-snug font-sans">{info.name} ({info.symbol})</p>
          <div className="mt-2 space-y-1">
            <p className="text-brand-textMuted">Sector: <span className="text-black dark:text-white font-semibold">{info.sector}</span></p>
            <p className="text-brand-textMuted">Beta (Market Risk): <span className="text-brand-primary font-semibold">{info.x.toFixed(2)}</span></p>
            <p className="text-brand-textMuted">3-Year CAGR: <span className="text-brand-success font-semibold">{info.y.toFixed(2)}%</span></p>
            <p className="text-brand-textMuted">1-Year Return: <span className="text-brand-warning font-semibold">{info.cagr_1y.toFixed(2)}%</span></p>
            <p className="text-brand-textMuted">Alpha Score: <span className="text-brand-primary font-semibold font-bold">{info.alpha_score}</span></p>
          </div>
          <p className="text-[9px] text-brand-primary mt-2 uppercase border-t border-brand-border/40 pt-1.5 font-bold">[Click node to open terminal]</p>
        </div>
      );
    }
    return null;
  };

  const handleNodeClick = (node) => {
    if (node && node.symbol) {
      navigate(`/stocks/detail/${node.symbol}`);
    }
  };

  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl p-6 shadow-2xl h-full flex flex-col">
      <div className="mb-4">
        <h3 className="text-lg font-bold text-black dark:text-white tracking-wide">Stock Risk-Return Scatter Matrix</h3>
        <p className="text-brand-textMuted text-xs mt-0.5 font-sans">Plotting Beta (Volatility) against CAGR 3Y. Node size indicates Alpha Score (0-100).</p>
      </div>

      {/* Sectors Legend */}
      <div className="flex flex-wrap gap-3 mb-6 bg-brand-bg/50 p-2 rounded-lg border border-brand-border/40">
        {sectorsList.map((sec) => (
          <div key={sec} className="flex items-center gap-1.5 text-xs text-brand-textMuted font-mono">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: getSectorColor(sec) }} />
            {sec}
          </div>
        ))}
      </div>

      {/* Chart Canvas */}
      <div className="h-[300px] w-full">
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis 
                type="number" 
                dataKey="x" 
                name="Beta" 
                domain={[0, 'auto']} 
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
              >
                <Label value="Beta (Market Volatility)" offset={0} position="insideBottom" fill="var(--text-muted)" fontSize={11} dy={15} />
              </XAxis>
              <YAxis 
                type="number" 
                dataKey="y" 
                name="CAGR" 
                unit="%" 
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
              >
                <Label value="3-Year CAGR (%)" angle={-90} position="insideLeft" fill="var(--text-muted)" fontSize={11} dx={-10} />
              </YAxis>
              <ZAxis type="number" dataKey="z" range={[80, 500]} />
              <Tooltip content={renderTooltip} cursor={{ strokeDasharray: '3:3', stroke: 'var(--border-color)' }} />
              {groupedData.map((group) => (
                <Scatter
                  key={group.sector}
                  name={group.sector}
                  data={group.items}
                  fill={group.color}
                  shape="circle"
                  line={false}
                  opacity={0.85}
                  onClick={handleNodeClick}
                  className="cursor-pointer"
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-brand-textMuted text-sm font-mono">
            COMPILING EQUITY RISK COORDINATES...
          </div>
        )}
      </div>
    </div>
  );
}
