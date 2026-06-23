/**
 * AnalystResponseCard.jsx
 * Shared component for the AlphaMatrix AI Analyst Terminal.
 *
 * Transforms raw AI markdown text into structured research cards:
 *   - Metric chips   (P/E, ROE, Beta, CAGR… extracted via regex)
 *   - Section blocks (### headers or **Label:** patterns)
 *   - Bullet lists   (- / * lines → visual items)
 *   - Verdict banner (BUY / HOLD / AVOID, color-coded)
 *
 * User messages stay as compact right-aligned query chips.
 */

import { ShieldCheck, ShieldAlert, AlertTriangle } from 'lucide-react';

// ─── Metric extraction ───────────────────────────────────────────────────────
const METRIC_PATTERNS = [
  { label: 'P/E Ratio',    regex: /P\/E\s*(?:Ratio)?[:\s]+([0-9.]+)/i },
  { label: 'ROE',          regex: /\bROE[:\s]+([0-9.]+)%?/i },
  { label: 'Beta',         regex: /\bBeta[:\s]+([0-9.]+)/i },
  { label: 'Div. Yield',   regex: /Div(?:idend)?\s*Yield[:\s]+([0-9.]+)%?/i },
  { label: 'CAGR 1Y',      regex: /CAGR\s*1[Yy][:\s]+([0-9.]+)%?/i },
  { label: 'CAGR 3Y',      regex: /CAGR\s*3[Yy][:\s]+([0-9.]+)%?/i },
  { label: 'CAGR 5Y',      regex: /CAGR\s*5[Yy][:\s]+([0-9.]+)%?/i },
  { label: 'Alpha Score',  regex: /Alpha\s*Score[:\s]+([0-9.]+)/i },
  { label: 'Sharpe',       regex: /\bSharpe(?:\s*Ratio)?[:\s]+([0-9.]+)/i },
  { label: 'Sortino',      regex: /\bSortino(?:\s*Ratio)?[:\s]+([0-9.]+)/i },
  { label: 'Expense',      regex: /Expense\s*Ratio[:\s]+([0-9.]+)%?/i },
  { label: 'Debt/Equity',  regex: /Debt[/\s]*Equity[:\s]+([0-9.]+)/i },
];

function extractMetrics(text) {
  return METRIC_PATTERNS
    .map(({ label, regex }) => {
      const m = text.match(regex);
      return m ? { label, value: m[1] } : null;
    })
    .filter(Boolean);
}

// ─── Verdict extraction ──────────────────────────────────────────────────────
const VERDICT_KEYWORDS = {
  BUY:   /\b(STRONG BUY|ACCUMULATE|OUTPERFORM|BUY)\b/i,
  AVOID: /\b(AVOID|SELL|UNDERPERFORM|HIGH RISK|REDUCE)\b/i,
  HOLD:  /\b(HOLD|NEUTRAL|WAIT|MARKET PERFORM)\b/i,
};

function extractVerdict(text) {
  // 1. Prefer bold-wrapped verdict: **BUY**, **HOLD**, **AVOID**
  const boldMatch = text.match(
    /\*\*(STRONG BUY|ACCUMULATE|OUTPERFORM|BUY|HOLD|NEUTRAL|WAIT|MARKET PERFORM|AVOID|SELL|UNDERPERFORM|HIGH RISK|REDUCE)\*\*/i
  );
  if (boldMatch) {
    const v = boldMatch[1].toUpperCase();
    if (VERDICT_KEYWORDS.BUY.test(v))   return 'BUY';
    if (VERDICT_KEYWORDS.AVOID.test(v)) return 'AVOID';
    return 'HOLD';
  }

  // 2. "Verdict: BUY" / "Recommendation: HOLD" line patterns
  const lineMatch = text.match(
    /(?:verdict|recommendation|stance|rating)[:\s]+\*?\s*(STRONG BUY|ACCUMULATE|BUY|HOLD|NEUTRAL|WAIT|AVOID|SELL)\s*\*?/i
  );
  if (lineMatch) {
    const v = lineMatch[1].toUpperCase();
    if (VERDICT_KEYWORDS.BUY.test(v))   return 'BUY';
    if (VERDICT_KEYWORDS.AVOID.test(v)) return 'AVOID';
    return 'HOLD';
  }

  return null; // Short / purely informational response — no verdict card
}

// ─── Section parsing ─────────────────────────────────────────────────────────
function parseSections(text) {
  // Mode A: ### Section Headers
  if (text.includes('###')) {
    return text
      .split(/###\s+/)
      .filter((p) => p.trim())
      .map((part) => {
        const nl = part.indexOf('\n');
        if (nl === -1) return { title: part.trim(), content: '' };
        return {
          title:   part.substring(0, nl).trim(),
          content: part.substring(nl).trim(),
        };
      });
  }

  // Mode B: **Label:** semi-structured headers at line start
  if (/^\*\*[A-Z][^*\n]+[*:]/m.test(text)) {
    const parts = text.split(/(?=^\*\*[A-Z][^*\n]+\*\*)/m);
    return parts.filter((p) => p.trim()).map((part) => {
      const match = part.match(/^\*\*([^*\n]+)\*\*[:\s]*([\s\S]*)/);
      if (match) {
        return {
          title: match[1].replace(/[*_~`#>-]/g, '').trim(),
          content: match[2].trim(),
        };
      }
      return { title: '', content: part.trim() };
    });
  }

  // Mode C: single prose block
  return [{ title: '', content: text.trim() }];
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function MetricChip({ label, value }) {
  return (
    <div className="flex flex-col items-center bg-brand-surface border border-brand-border px-3 py-2 min-w-[72px] text-center">
      <span className="text-[7px] font-mono uppercase tracking-wider text-brand-textMuted leading-tight">
        {label}
      </span>
      <span className="text-sm font-bold text-brand-primary font-mono mt-0.5">{value}</span>
    </div>
  );
}

function SectionHeader({ title }) {
  if (!title) return null;
  // Don't render a section header that is just a verdict word alone
  if (/^(STRONG BUY|ACCUMULATE|BUY|HOLD|NEUTRAL|AVOID|SELL)$/i.test(title.trim())) return null;
  return (
    <div className="flex items-center gap-2 pt-4 pb-1.5">
      <div className="w-0.5 h-3.5 bg-brand-primary/60 shrink-0" />
      <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-brand-primary">
        {title}
      </span>
    </div>
  );
}

function ContentBlock({ text }) {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  const groups = [];
  let currentBullets = [];

  const flushBullets = () => {
    if (currentBullets.length > 0) {
      groups.push({ type: 'bullets', items: [...currentBullets] });
      currentBullets = [];
    }
  };

  lines.forEach((line) => {
    if (/^[-*•]\s/.test(line)) {
      // Bullet line
      currentBullets.push(line.replace(/^[-*•]\s+/, ''));
    } else {
      flushBullets();
      // Skip bare verdict keyword lines — handled by VerdictBanner
      if (
        /^\*\*(STRONG BUY|ACCUMULATE|BUY|HOLD|NEUTRAL|AVOID|SELL)\*\*$/i.test(line)
      ) return;
      groups.push({ type: 'text', content: line });
    }
  });
  flushBullets();

  if (groups.length === 0) return null;

  return (
    <div className="space-y-2">
      {groups.map((g, i) => {
        if (g.type === 'bullets') {
          return (
            <ul key={i} className="space-y-1.5 pl-1">
              {g.items.map((item, j) => (
                <li
                  key={j}
                  className="flex items-start gap-2 text-[11px] text-black dark:text-white leading-relaxed font-sans"
                >
                  <span className="text-brand-primary shrink-0 font-bold mt-0.5">›</span>
                  <span
                    dangerouslySetInnerHTML={{
                      __html: item.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'),
                    }}
                  />
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p
            key={i}
            className="text-[11px] text-black dark:text-white leading-relaxed font-sans"
            dangerouslySetInnerHTML={{
              __html: g.content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'),
            }}
          />
        );
      })}
    </div>
  );
}

const VERDICT_CONFIG = {
  BUY: {
    border:  'border-brand-success/40',
    bg:      'bg-green-500/5',
    shadow:  'shadow-[0_0_14px_rgba(34,197,94,0.07)]',
    bar:     'bg-brand-success',
    text:    'text-brand-success',
    badge:   'text-brand-success border-brand-success/30 bg-brand-success/10',
    icon:    <ShieldCheck className="h-4 w-4" />,
    label:   'BUY',
  },
  HOLD: {
    border:  'border-brand-warning/40',
    bg:      'bg-yellow-500/5',
    shadow:  'shadow-[0_0_14px_rgba(234,179,8,0.07)]',
    bar:     'bg-brand-warning',
    text:    'text-brand-warning',
    badge:   'text-brand-warning border-brand-warning/30 bg-brand-warning/10',
    icon:    <AlertTriangle className="h-4 w-4" />,
    label:   'HOLD',
  },
  AVOID: {
    border:  'border-brand-danger/40',
    bg:      'bg-red-500/5',
    shadow:  'shadow-[0_0_14px_rgba(239,68,68,0.07)]',
    bar:     'bg-brand-danger',
    text:    'text-brand-danger',
    badge:   'text-brand-danger border-brand-danger/30 bg-brand-danger/10',
    icon:    <ShieldAlert className="h-4 w-4" />,
    label:   'AVOID',
  },
};

function VerdictBanner({ verdict }) {
  const c = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.HOLD;
  return (
    <div
      className={`mt-4 border p-4 relative overflow-hidden ${c.border} ${c.bg} ${c.shadow}`}
    >
      {/* Colored left accent bar */}
      <div className={`absolute top-0 bottom-0 left-0 w-1 ${c.bar}`} />
      <div className="pl-3 flex items-center justify-between gap-2 flex-wrap">
        <div className={`flex items-center gap-2 ${c.text}`}>
          {c.icon}
          <span className="font-mono text-xs font-extrabold uppercase tracking-wider">
            System Investment Verdict: {c.label}
          </span>
        </div>
        <span
          className={`text-[9px] font-mono px-2 py-0.5 border font-bold ${c.badge}`}
        >
          {c.label}
        </span>
      </div>
    </div>
  );
}

// ─── Main export ─────────────────────────────────────────────────────────────
export default function AnalystResponseCard({ message }) {
  const { role, content } = message;

  // ── User query chip ──────────────────────────────────────────────────────
  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-brand-primary/10 border border-brand-primary px-3.5 py-2 text-[11px] text-black dark:text-white font-sans leading-relaxed">
          {content}
        </div>
      </div>
    );
  }

  // ── AI Research Card ─────────────────────────────────────────────────────
  const metrics  = extractMetrics(content);
  const verdict  = extractVerdict(content);
  const sections = parseSections(content);

  return (
    <div className="border border-brand-border/70 bg-brand-bg">
      {/* Metric chips strip */}
      {metrics.length > 0 && (
        <div className="border-b border-brand-border/40 px-4 py-3">
          <p className="text-[7px] font-mono text-brand-textMuted uppercase tracking-widest mb-2.5">
            [EXTRACTED_METRICS]
          </p>
          <div className="flex flex-wrap gap-2">
            {metrics.map((m, i) => (
              <MetricChip key={i} label={m.label} value={m.value} />
            ))}
          </div>
        </div>
      )}

      {/* Sections body */}
      <div className="px-4 pb-4">
        {sections.map((sec, i) => (
          <div key={i}>
            <SectionHeader title={sec.title} />
            {sec.content && <ContentBlock text={sec.content} />}
          </div>
        ))}

        {/* Verdict banner */}
        {verdict && <VerdictBanner verdict={verdict} />}
      </div>
    </div>
  );
}
