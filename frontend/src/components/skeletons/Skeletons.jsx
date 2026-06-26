/**
 * Skeleton loaders for AlphaMatrix.
 *
 * Uses a simple pulse animation (already defined in Tailwind config via
 * `animate-pulse`) to give perceived loading feedback without spinner fatigue.
 *
 * Rules:
 *  - No spinners. Spinners block cognitive processing; skeletons feel instant.
 *  - Match the exact shape/layout of the real content being replaced.
 *  - All components use only existing brand tokens (bg-brand-surface, etc.)
 */

/** Generic shimmer line — configurable width and height */
export function SkeletonLine({ className = '' }) {
  return (
    <div
      className={`bg-brand-border/50 animate-pulse rounded-sm ${className}`}
    />
  );
}

/** Skeleton for a single stat/metric card (used in StockHome, Home dashboards) */
export function CardSkeleton() {
  return (
    <div className="terminal-card flex items-center gap-4">
      {/* Icon placeholder */}
      <div className="w-10 h-10 shrink-0 bg-brand-border/40 animate-pulse" />
      <div className="flex-1 space-y-2">
        <SkeletonLine className="h-2 w-24" />
        <SkeletonLine className="h-5 w-16" />
      </div>
    </div>
  );
}

/** Skeleton for a list-row item (funds list, stocks list) */
export function RowSkeleton({ cols = 4 }) {
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-brand-border/30">
      <SkeletonLine className="h-3 w-8 shrink-0" />
      <SkeletonLine className="h-3 flex-1" />
      {Array.from({ length: cols - 2 }).map((_, i) => (
        <SkeletonLine key={i} className="h-3 w-16 shrink-0" />
      ))}
    </div>
  );
}

/** Skeleton for a news card */
export function NewsCardSkeleton() {
  return (
    <div className="terminal-card space-y-3">
      <div className="flex items-center gap-2">
        <SkeletonLine className="h-2 w-12" />
        <SkeletonLine className="h-2 w-16" />
      </div>
      <SkeletonLine className="h-4 w-full" />
      <SkeletonLine className="h-3 w-3/4" />
      <div className="flex gap-2 mt-2">
        <SkeletonLine className="h-2 w-10" />
        <SkeletonLine className="h-2 w-14" />
      </div>
    </div>
  );
}

/** Skeleton for the chart area (StockDetail, Detail pages) */
export function ChartSkeleton({ height = 'h-64' }) {
  return (
    <div className={`relative border border-brand-border/40 bg-brand-surface ${height} overflow-hidden`}>
      {/* Fake axis lines */}
      <div className="absolute left-0 top-0 bottom-0 w-px bg-brand-border/30" />
      <div className="absolute left-0 right-0 bottom-0 h-px bg-brand-border/30" />
      {/* Shimmering bars */}
      <div className="absolute inset-4 flex items-end gap-2">
        {Array.from({ length: 18 }).map((_, i) => (
          <div
            key={i}
            className="flex-1 bg-brand-border/30 animate-pulse rounded-sm"
            style={{
              height: `${30 + Math.sin(i * 0.8) * 25 + Math.random() * 20}%`,
              animationDelay: `${i * 50}ms`,
            }}
          />
        ))}
      </div>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="font-mono text-[10px] text-brand-textMuted/60 tracking-widest uppercase">
          Loading chart data...
        </span>
      </div>
    </div>
  );
}

/** Skeleton grid for a set of cards */
export function CardGridSkeleton({ count = 4, cols = 'grid-cols-2 md:grid-cols-4' }) {
  return (
    <div className={`grid ${cols} gap-4 sm:gap-6`}>
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}

/** Skeleton for the stock/fund table list */
export function TableSkeleton({ rows = 8, cols = 5 }) {
  return (
    <div className="border border-brand-border/40">
      {/* Header */}
      <div className="flex items-center gap-4 px-4 py-2 bg-brand-bg border-b border-brand-border">
        {Array.from({ length: cols }).map((_, i) => (
          <SkeletonLine key={i} className={`h-2 ${i === 1 ? 'flex-1' : 'w-14 shrink-0'}`} />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <RowSkeleton key={i} cols={cols} />
      ))}
    </div>
  );
}
