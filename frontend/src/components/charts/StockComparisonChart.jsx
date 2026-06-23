import { useState, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function StockComparisonChart({ 
  priceHistory1 = [], 
  priceHistory2 = [], 
  symbol1 = 'Asset 1', 
  symbol2 = 'Asset 2' 
}) {
  const [range, setRange] = useState('3Y'); // 1M, 6M, 1Y, 3Y, 5Y, MAX

  const filteredData = useMemo(() => {
    if (!priceHistory1.length && !priceHistory2.length) return [];

    // Reverse descending arrays to chronological (earliest-first)
    const chrono1 = [...priceHistory1].reverse();
    const chrono2 = [...priceHistory2].reverse();

    // Determine cutoff date
    let latestDateStr = '';
    if (chrono1.length) latestDateStr = chrono1[chrono1.length - 1].date;
    if (chrono2.length && (!latestDateStr || new Date(chrono2[chrono2.length - 1].date) > new Date(latestDateStr))) {
      latestDateStr = chrono2[chrono2.length - 1].date;
    }

    if (!latestDateStr) return [];

    const latestDate = new Date(latestDateStr);
    let cutoffDate = new Date(latestDate);

    if (range !== 'MAX') {
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
    }

    // Filter both series
    const s1Filtered = range === 'MAX' ? chrono1 : chrono1.filter(item => new Date(item.date) >= cutoffDate);
    const s2Filtered = range === 'MAX' ? chrono2 : chrono2.filter(item => new Date(item.date) >= cutoffDate);

    // Merge by date
    const s1Map = new Map(s1Filtered.map(item => [item.date, item.close]));
    const s2Map = new Map(s2Filtered.map(item => [item.date, item.close]));
    
    const allDates = Array.from(new Set([...s1Map.keys(), ...s2Map.keys()])).sort();

    // Find baselines (earliest valid prices)
    let s1_base = null;
    let s2_base = null;
    for (const d of allDates) {
      if (s1_base === null && s1Map.has(d)) s1_base = s1Map.get(d);
      if (s2_base === null && s2Map.has(d)) s2_base = s2Map.get(d);
      if (s1_base !== null && s2_base !== null) break;
    }

    const merged = [];
    allDates.forEach(date => {
      const p1 = s1Map.get(date);
      const p2 = s2Map.get(date);

      merged.push({
        date,
        // Normalized price starting at 100
        norm1: p1 && s1_base ? (p1 / s1_base) * 100 : null,
        norm2: p2 && s2_base ? (p2 / s2_base) * 100 : null,
        // Raw values for tooltip reference
        raw1: p1 || null,
        raw2: p2 || null
      });
    });

    return merged;
  }, [priceHistory1, priceHistory2, range]);

  const formatXAxis = (tickItem) => {
    try {
      const d = new Date(tickItem);
      return d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
    } catch {
      return tickItem;
    }
  };

  const renderTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0].payload;
      const dateVal = new Date(dataPoint.date).toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });

      return (
        <div className="glassmorphism p-3 rounded-lg border border-brand-border shadow-xl font-mono text-[10px] space-y-1.5">
          <p className="text-brand-textMuted font-bold border-b border-brand-border/40 pb-1">{dateVal}</p>
          <div className="space-y-1">
            <p className="text-brand-primary flex justify-between gap-4">
              <span>{symbol1}:</span>
              <span className="font-bold text-black dark:text-white">
                {dataPoint.norm1 ? `${dataPoint.norm1.toFixed(1)}%` : '—'} (₹{dataPoint.raw1 ? dataPoint.raw1.toFixed(2) : '—'})
              </span>
            </p>
            <p className="text-orange-400 flex justify-between gap-4">
              <span>{symbol2}:</span>
              <span className="font-bold text-black dark:text-white">
                {dataPoint.norm2 ? `${dataPoint.norm2.toFixed(1)}%` : '—'} (₹{dataPoint.raw2 ? dataPoint.raw2.toFixed(2) : '—'})
              </span>
            </p>
          </div>
        </div>
      );
    }
    return null;
  };

  const ranges = ['1M', '6M', '1Y', '3Y', '5Y', 'MAX'];

  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl p-6 shadow-2xl space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h3 className="text-sm font-bold text-black dark:text-white uppercase tracking-wider font-display flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 bg-brand-primary" /> {symbol1} <span className="text-brand-textMuted font-normal lowercase font-mono">vs</span> <span className="inline-block w-2.5 h-2.5 bg-orange-400" /> {symbol2}
          </h3>
          <p className="text-brand-textMuted text-[10px] font-mono mt-0.5">Normalized historical comparison (Base 100%)</p>
        </div>

        {/* Duration Selectors */}
        <div className="flex bg-brand-bg rounded-lg p-0.5 border border-brand-border self-stretch sm:self-auto font-mono">
          {ranges.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`flex-1 sm:flex-none px-3 py-2 min-h-[36px] text-[10px] font-bold rounded-md transition-all ${
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

      <div className="h-[280px] sm:h-[350px] w-full">
        {filteredData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={filteredData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
              <XAxis 
                dataKey="date" 
                tickFormatter={formatXAxis} 
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-muted)', fontSize: 9, fontFamily: 'monospace' }}
                axisLine={{ stroke: 'var(--border-color)' }}
              />
              <YAxis 
                domain={['auto', 'auto']} 
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-muted)', fontSize: 9, fontFamily: 'monospace' }}
                axisLine={{ stroke: 'var(--border-color)' }}
                tickFormatter={(val) => `${val.toFixed(0)}%`}
              />
              <Tooltip content={renderTooltip} />
              <Line 
                type="monotone" 
                dataKey="norm1" 
                stroke="var(--accent-gold)" 
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
              <Line 
                type="monotone" 
                dataKey="norm2" 
                stroke="#f97316" 
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-brand-textMuted text-xs font-mono">
            No overlapping historical records found.
          </div>
        )}
      </div>
    </div>
  );
}
