import React from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis, Label } from 'recharts';

export default function RiskScatterplot({ funds = [] }) {
  // Pre-process data
  const data = React.useMemo(() => {
    return funds
      .filter(f => f.beta !== null && f.cagr_3y !== null)
      .map(f => ({
        name: f.fund_name,
        category: f.category,
        x: f.beta,                                  // Beta on X
        y: Math.round((f.cagr_3y || 0) * 1000) / 10,  // CAGR % on Y
        z: Math.max(0.1, f.sharpe_ratio || 0),       // Sharpe for size
        sharpe: f.sharpe_ratio,
        alpha: f.alpha ? Math.round(f.alpha * 1000) / 10 : 0
      }));
  }, [funds]);

  // Color mapping based on category
  const getCategoryColor = (category) => {
    switch (category) {
      case 'Large Cap': return '#6366f1'; // Indigo
      case 'Mid Cap': return '#06b6d4';   // Cyan
      case 'Small Cap': return '#f43f5e'; // Rose
      case 'Index': return '#10b981';     // Emerald
      case 'Sectoral': return '#f59e0b';  // Amber
      default: return '#9ca3af';          // Gray
    }
  };

  // Group by category to plot separate series for legend colors
  const groupedData = React.useMemo(() => {
    const groups = {};
    data.forEach(item => {
      if (!groups[item.category]) {
        groups[item.category] = [];
      }
      groups[item.category].push(item);
    });
    return Object.entries(groups).map(([category, items]) => ({
      category,
      items,
      color: getCategoryColor(category)
    }));
  }, [data]);

  // Custom scatter Tooltip
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const info = payload[0].payload;
      return (
        <div className="glassmorphism p-4 rounded-lg border border-brand-border shadow-2xl max-w-sm">
          <p className="text-black dark:text-white font-bold text-sm leading-snug">{info.name}</p>
          <div className="mt-2 space-y-1 text-xs">
            <p className="text-brand-textMuted">Category: <span className="text-black dark:text-white font-semibold">{info.category}</span></p>
            <p className="text-brand-textMuted">Beta (Market Volatility): <span className="text-brand-primary font-semibold">{info.x.toFixed(2)}</span></p>
            <p className="text-brand-textMuted">3-Year CAGR: <span className="text-brand-success font-semibold">{info.y.toFixed(2)}%</span></p>
            <p className="text-brand-textMuted">Alpha (vs Nifty 50): <span className="text-brand-warning font-semibold">{info.alpha.toFixed(2)}%</span></p>
            <p className="text-brand-textMuted">Sharpe Ratio: <span className="text-brand-primary font-semibold">{info.sharpe ? info.sharpe.toFixed(2) : 'N/A'}</span></p>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl p-6 shadow-2xl h-full flex flex-col">
      <div className="mb-4">
        <h3 className="text-lg font-bold text-black dark:text-white tracking-wide">Risk-Return Scatter Matrix</h3>
        <p className="text-brand-textMuted text-xs mt-0.5">Plotting Beta (Volatility) against CAGR 3Y. Node size indicates Sharpe ratio.</p>
      </div>

      {/* Categories Legend */}
      <div className="flex flex-wrap gap-3 mb-6 bg-brand-bg/50 p-2 rounded-lg border border-brand-border/40">
        {['Large Cap', 'Mid Cap', 'Small Cap', 'Index', 'Sectoral'].map((cat) => (
          <div key={cat} className="flex items-center gap-1.5 text-xs text-brand-textMuted font-mono">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: getCategoryColor(cat) }} />
            {cat}
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
                <Label value="Beta (Market Risk)" offset={0} position="insideBottom" fill="var(--text-muted)" fontSize={11} dy={15} />
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
              <ZAxis type="number" dataKey="z" range={[50, 450]} />
              <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3', stroke: 'var(--border-color)' }} />
              {groupedData.map((group) => (
                <Scatter
                  key={group.category}
                  name={group.category}
                  data={group.items}
                  fill={group.color}
                  shape="circle"
                  line={false}
                  opacity={0.85}
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-brand-textMuted text-sm">
            Not enough data available to render Risk-Return coordinates. Seeding might be in progress.
          </div>
        )}
      </div>
    </div>
  );
}
