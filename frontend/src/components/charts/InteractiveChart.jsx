import { useState, useMemo } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function InteractiveChart({ navHistory = [] }) {
  const [range, setRange] = useState('3Y'); // 1M, 6M, 1Y, 3Y, 5Y, MAX

  // Filter history based on range selector
  const filteredData = useMemo(() => {
    if (!navHistory.length) return [];
    
    // MFapi data is sorted latest-first. Let's reverse it to chronological order for graphing!
    const chronological = [...navHistory].reverse();
    
    if (range === 'MAX') return chronological;

    const latestDate = new Date(chronological[chronological.length - 1].date);
    let cutoffDate = new Date(latestDate);

    switch (range) {
      case '1M':
        cutoffDate.setMonth(cutoffDate.getMonth() - 1);
        break;
      case '6M':
        cutoffDate.setMonth(cutoffDate.getMonth() - 6);
        break;
      case '1Y':
        cutoffDate.setFullYear(cutoffDate.getFullYear() - 1);
        break;
      case '3Y':
        cutoffDate.setFullYear(cutoffDate.getFullYear() - 3);
        break;
      case '5Y':
        cutoffDate.setFullYear(cutoffDate.getFullYear() - 5);
        break;
      default:
        break;
    }

    return chronological.filter(item => new Date(item.date) >= cutoffDate);
  }, [navHistory, range]);

  // Format date for axis labels
  const formatXAxis = (tickItem) => {
    try {
      const d = new Date(tickItem);
      return d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
    } catch {
      return tickItem;
    }
  };

  // Custom premium Tooltip
  const renderTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const dateVal = new Date(payload[0].payload.date).toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
      return (
        <div className="glassmorphism p-3 rounded-lg border border-brand-border shadow-xl">
          <p className="text-brand-textMuted text-xs font-semibold">{dateVal}</p>
          <p className="text-brand-primary text-base font-bold">
            NAV: <span className="text-black dark:text-white">₹{payload[0].value.toFixed(4)}</span>
          </p>
        </div>
      );
    }
    return null;
  };

  const ranges = ['1M', '6M', '1Y', '3Y', '5Y', 'MAX'];

  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl p-6 shadow-2xl">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h3 className="text-lg font-bold text-black dark:text-white tracking-wide">Historical Net Asset Value (NAV)</h3>
          <p className="text-brand-textMuted text-xs mt-0.5">Time-series price analysis and growth rate</p>
        </div>
        
        {/* Duration Selectors */}
        <div className="flex bg-brand-bg rounded-lg p-0.5 border border-brand-border self-stretch sm:self-auto">
          {ranges.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`flex-1 sm:flex-none px-3 py-1.5 text-xs font-bold rounded-md transition-all ${
                range === r
                  ? 'bg-brand-primary text-black shadow-md'
                  : 'text-brand-textMuted hover:text-black dark:hover:text-white hover:bg-brand-border'
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="h-[350px] w-full">
        {filteredData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={filteredData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorNav" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent-gold)" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="var(--accent-gold)" stopOpacity={0.0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
              <XAxis 
                dataKey="date" 
                tickFormatter={formatXAxis} 
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                axisLine={{ stroke: 'var(--border-color)' }}
              />
              <YAxis 
                domain={['auto', 'auto']} 
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                axisLine={{ stroke: 'var(--border-color)' }}
                tickFormatter={(val) => `₹${val.toFixed(0)}`}
              />
              <Tooltip content={renderTooltip} />
              <Area 
                type="monotone" 
                dataKey="nav" 
                stroke="var(--accent-gold)" 
                strokeWidth={2.5}
                fillOpacity={1} 
                fill="url(#colorNav)" 
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-brand-textMuted text-sm">
            No historical NAV records available for display
          </div>
        )}
      </div>
    </div>
  );
}
