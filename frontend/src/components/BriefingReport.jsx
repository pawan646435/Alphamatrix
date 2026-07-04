import React, { useState } from 'react';
import { Cpu, Star, ShieldCheck, ShieldAlert, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';

/**
 * Parses the `ai_summary` field, which is either:
 *  - v1: a plain Markdown string (older briefings, or the mock fallback), or
 *  - v2: a JSON string `{"text": "...markdown...", "meta": {...trust/quality/verdict...}}`
 * Both must keep rendering identically for the existing `### Header`-based
 * section splitting below — only `meta` (null for v1) drives the new trust UI.
 */
function parseBriefingPayload(aiSummary) {
  if (!aiSummary || typeof aiSummary !== 'string') return { text: aiSummary || null, meta: null };
  const trimmed = aiSummary.trim();
  if (trimmed.startsWith('{')) {
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed && typeof parsed.text === 'string') {
        return { text: parsed.text, meta: parsed.meta || null };
      }
    } catch {
      // Not valid JSON — treat as plain v1 text below.
    }
  }
  return { text: aiSummary, meta: null };
}

/** Shared inline-markdown + trust-annotation renderer for all briefing text. */
function annotateBriefingHtml(raw) {
  if (!raw) return '';
  return raw
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\[FACT:([^\]]+)\]/g, '<span class="font-mono text-[10px] text-brand-success bg-brand-success/10 border border-brand-success/25 px-1 rounded">[FACT:$1]</span>')
    .replace(/\[DATA\]/g, '<span class="font-bold text-brand-primary/90">[DATA]</span>')
    .replace(/\[ANALYTICAL\]/g, '<span class="italic text-brand-textMuted/70">[ANALYTICAL]</span>')
    .replace(/\[MACRO CONTEXT[^\]]*\]/g, (m) => `<span class="italic text-brand-textMuted/70">${m}</span>`)
    .replace(/^⚠️\s*DATA GAP:?(.*)$/gm, '<div class="border-l-2 border-brand-warning/60 pl-2 my-1 text-brand-warning">⚠️ DATA GAP:$1</div>')
    .replace(/^⚠️\s*ANOMALY:?(.*)$/gm, '<div class="border-l-2 border-brand-danger/60 pl-2 my-1 text-brand-danger">⚠️ ANOMALY:$1</div>')
    .replace(/^-\s*(.*)$/gm, '• $1<br/>')
    .split('\n')
    .filter((line) => line.trim())
    .join('<br/>');
}

const PILLAR_META = [
  { key: 'valuation', label: 'VALUATION', weight: 30 },
  { key: 'quality', label: 'QUALITY', weight: 25 },
  { key: 'momentum', label: 'MOMENTUM', weight: 20 },
  { key: 'risk', label: 'RISK', weight: 25 },
];

export default function BriefingReport({
  aiSummary,
  symbol,
  lastSync,
  bullCase,
  bearCase,
  investorVerdict: investorVerdictProp,
  traderVerdict: traderVerdictProp,
  confidenceScore: confidenceScoreProp,
  isLoading,
}) {
  const [showGaps, setShowGaps] = useState(true);
  const [showWarnings, setShowWarnings] = useState(false);

  const { text: briefingText, meta } = parseBriefingPayload(aiSummary);
  const isBriefingLoading = isLoading || !briefingText || briefingText === 'Generating Equity Intelligence Briefing in the background...';

  const renderBriefingSection = (sectionTitle) => {
    if (!briefingText) return null;
    const parts = briefingText.split(`### ${sectionTitle}`);
    if (parts.length < 2) return null;
    const sectionContent = parts[1].split('###')[0].trim();
    return (
      <div className="space-y-1">
        <h4 className="text-[10px] font-bold text-brand-primary uppercase tracking-wider font-display">{sectionTitle}</h4>
        <p className="text-xs leading-relaxed font-sans text-brand-textMuted" dangerouslySetInnerHTML={{ __html: annotateBriefingHtml(sectionContent) }} />
      </div>
    );
  };

  const renderBriefingSectionContentOnly = (sectionTitle) => {
    if (!briefingText) return null;
    const parts = briefingText.split(`### ${sectionTitle}`);
    if (parts.length < 2) return null;
    const sectionContent = parts[1].split('###')[0].trim();
    return <p className="text-xs leading-relaxed font-sans text-brand-textMuted" dangerouslySetInnerHTML={{ __html: annotateBriefingHtml(sectionContent) }} />;
  };

  // ── Verdict parsing — mirrors the original StockDetail.jsx logic, now
  // operating on the unwrapped briefingText so v1 and v2 both work. ──
  let investorVerdict = investorVerdictProp || 'HOLD';
  let traderVerdict = traderVerdictProp || 'HOLD';
  let stockConfidence = confidenceScoreProp ? `${Math.round(confidenceScoreProp)}%` : '';
  let stockStanceType;
  let stockStanceHtml = '';

  if (!isBriefingLoading && briefingText) {
    const verdictParts = briefingText.split('### Final Verdict');
    if (verdictParts.length >= 2) {
      const verdictContent = verdictParts[1].split('###')[0].trim();
      stockStanceHtml = annotateBriefingHtml(verdictContent);
      const lower = verdictContent.toLowerCase();
      if (!investorVerdictProp || !traderVerdictProp) {
        let parsedStance = 'HOLD';
        if (/\bstrong buy\b|\baccumulate\b|\boutperform\b|\bbuy\b/.test(lower)) parsedStance = 'BUY';
        else if (/\bavoid\b|\bsell\b|\bunderperform\b|\bhigh risk\b|\breduce\b/.test(lower)) parsedStance = 'AVOID';
        investorVerdict = parsedStance;
        traderVerdict = parsedStance;
      }
    }
    if (!stockConfidence) {
      const confParts = briefingText.split('### Confidence Score');
      if (confParts.length >= 2) {
        const confContent = confParts[1].split('###')[0];
        const confMatch = confContent.match(/(\d{1,3})%/);
        if (confMatch) stockConfidence = confMatch[1] + '%';
      }
    }
  }

  if (investorVerdict.includes('BUY') || traderVerdict.includes('BUY')) stockStanceType = 'BUY';
  else if (investorVerdict.includes('AVOID') || traderVerdict.includes('AVOID') || investorVerdict.includes('REDUCE') || traderVerdict.includes('REDUCE')) stockStanceType = 'AVOID';
  else stockStanceType = 'HOLD';

  const confidenceBadgeColor =
    meta?.data_confidence_label === 'HIGH' ? 'text-brand-success border-brand-success/30 bg-brand-success/10'
      : meta?.data_confidence_label === 'MEDIUM' ? 'text-brand-warning border-brand-warning/30 bg-brand-warning/10'
      : 'text-brand-danger border-brand-danger/30 bg-brand-danger/10';

  const hasGapsOrAnomalies = meta && ((meta.missing_fields?.length || 0) > 0 || (meta.anomalies?.length || 0) > 0);

  return (
    <div data-symbol={symbol} className="w-full border border-brand-border bg-brand-surface shadow-xl flex flex-col justify-between animate-fade-in-up" style={{ animationDelay: '200ms' }}>
      {/* Panel header */}
      <div className="bg-brand-bg border-b border-brand-border px-5 py-4 flex flex-col gap-2 text-xs">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <div className="flex items-center gap-2 text-brand-primary">
            <Cpu className="h-4 w-4 animate-pulse-subtle" />
            <h3 className="font-bold text-black dark:text-white uppercase tracking-wider font-display">AI EQUITY BRIEFING REPORT</h3>
          </div>
          <span className="font-mono text-[9px] text-brand-textMuted uppercase">
            [RAG_TELEMETRY: {meta ? 'v2 · RUBRIC_ANCHORED' : 'aligned'}]
          </span>
        </div>
        {meta && !isBriefingLoading && (
          <div className="flex flex-wrap items-center gap-2 font-mono text-[9px] text-brand-textMuted">
            <span className={`px-2 py-0.5 border font-bold ${confidenceBadgeColor}`}>
              DATA CONFIDENCE: {meta.data_confidence_label} · {meta.data_completeness_pct}% COVERAGE
            </span>
            <span className="px-2 py-0.5 border border-brand-border text-brand-textMuted">
              INTEGRITY: {Math.round(meta.trust_score)}/100
            </span>
            <span className="px-2 py-0.5 border border-brand-border text-brand-textMuted">
              ANALYSIS BASED ON {meta.available_metrics}/{meta.total_metrics} AVAILABLE METRICS
            </span>
            {meta.generated_at && <span>GENERATED: {new Date(meta.generated_at).toLocaleString('en-IN')}</span>}
            {lastSync && <span>DATA SYNC: {new Date(lastSync).toLocaleString('en-IN')}</span>}
          </div>
        )}
      </div>

      <div className="p-6 md:p-8">
        {isBriefingLoading ? (
          <div className="space-y-6 py-4 animate-pulse">
            <div className="space-y-2">
              <div className="h-3 w-1/4 bg-brand-border/40 rounded" />
              <div className="h-2 w-full bg-brand-border/30 rounded" />
              <div className="h-2 w-full bg-brand-border/30 rounded" />
              <div className="h-2 w-5/6 bg-brand-border/30 rounded" />
            </div>
            <div className="space-y-2 pt-4 border-t border-brand-border/20">
              <div className="h-3 w-1/4 bg-brand-border/40 rounded" />
              <div className="h-2 w-full bg-brand-border/30 rounded" />
              <div className="h-2 w-full bg-brand-border/30 rounded" />
            </div>
            <div className="space-y-2 pt-4 border-t border-brand-border/20">
              <div className="h-3 w-1/5 bg-brand-border/40 rounded" />
              <div className="h-2 w-full bg-brand-border/30 rounded" />
              <div className="h-2 w-4/5 bg-brand-border/30 rounded" />
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Data gaps / anomalies panel — only rendered when issues exist */}
            {hasGapsOrAnomalies && (
              <div className="border border-brand-warning/30 bg-brand-warning/5 rounded">
                <button
                  type="button"
                  onClick={() => setShowGaps((s) => !s)}
                  className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-bold uppercase text-brand-warning"
                >
                  <span>⚠️ Data Gaps &amp; Anomalies</span>
                  {showGaps ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </button>
                {showGaps && (
                  <div className="px-3 pb-3 space-y-1 font-mono text-[10px]">
                    {(meta.missing_fields || []).map((f) => (
                      <div key={f} className="text-brand-warning">⚠️ {f} unavailable</div>
                    ))}
                    {(meta.anomalies || []).map((a, i) => (
                      <div key={i} className="text-brand-danger">⚠️ {a}</div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {renderBriefingSection('Executive Summary')}

            {/* Investment Thesis — dedicated premium card */}
            {bullCase ? (
              <div className="p-4 border border-brand-primary/20 bg-brand-primary/5 space-y-2">
                <div className="flex items-center gap-1.5 text-brand-primary">
                  <Star className="h-3.5 w-3.5 fill-current" />
                  <h4 className="text-[10px] font-bold uppercase tracking-wider font-display">Core Investment Thesis</h4>
                </div>
                <p className="text-xs leading-relaxed font-sans text-brand-textMuted" dangerouslySetInnerHTML={{ __html: annotateBriefingHtml(bullCase) }} />
              </div>
            ) : (briefingText && briefingText.includes('### Investment Thesis') && (
              <div className="p-4 border border-brand-primary/20 bg-brand-primary/5 space-y-2">
                <div className="flex items-center gap-1.5 text-brand-primary">
                  <Star className="h-3.5 w-3.5 fill-current" />
                  <h4 className="text-[10px] font-bold uppercase tracking-wider font-display">Core Investment Thesis</h4>
                </div>
                {renderBriefingSectionContentOnly('Investment Thesis')}
              </div>
            ))}

            {renderBriefingSection('Performance Analysis')}
            {renderBriefingSection('Fundamental Analysis')}
            {renderBriefingSection('Sector Analysis')}
            {renderBriefingSection('Macro Analysis')}
            {renderBriefingSection('Geopolitical Analysis')}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-t border-brand-border/40 pt-4">
              {renderBriefingSection('Bull Case')}
              {renderBriefingSection('Base Case')}
              {renderBriefingSection('Bear Case')}
            </div>

            {/* Risk Factors */}
            {bearCase ? (
              <div className="border-t border-brand-border/40 pt-4 space-y-1">
                <h4 className="text-[10px] font-bold text-brand-warning uppercase tracking-wider font-display flex items-center gap-1.5">⚠️ Key Risk Factors</h4>
                <p className="text-xs leading-relaxed font-sans text-brand-textMuted" dangerouslySetInnerHTML={{ __html: annotateBriefingHtml(bearCase) }} />
              </div>
            ) : (briefingText && briefingText.includes('### Risk Factors') && (
              <div className="border-t border-brand-border/40 pt-4 space-y-1">
                <h4 className="text-[10px] font-bold text-brand-warning uppercase tracking-wider font-display flex items-center gap-1.5">⚠️ Key Risk Factors</h4>
                {renderBriefingSectionContentOnly('Risk Factors')}
              </div>
            ))}

            {/* Verdict Breakdown — v2 only, additive to the existing verdict card below */}
            {meta?.verdict_anchor && (
              <div className="border-t border-brand-border/40 pt-4 space-y-2">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <h4 className="text-[10px] font-bold text-brand-primary uppercase tracking-wider font-display">Verdict Breakdown</h4>
                  {meta.verdict_anchor.diverges_from_alpha_score && (
                    <span className="text-[9px] font-mono font-bold px-2 py-0.5 border border-brand-warning/40 bg-brand-warning/10 text-brand-warning uppercase">
                      ⚠️ DIVERGES FROM ALPHA SCORE MODEL — see verdict notes
                    </span>
                  )}
                </div>
                {PILLAR_META.map(({ key, label, weight }) => {
                  const score = meta.verdict_anchor.pillar_scores?.[key] ?? 0;
                  const barColor = score >= 7 ? 'bg-brand-success' : score >= 4.5 ? 'bg-brand-warning' : 'bg-brand-danger';
                  return (
                    <div key={key} className="flex items-center gap-2 font-mono text-[10px]">
                      <span className="w-24 shrink-0 text-brand-textMuted">{label} {weight}%</span>
                      <div className="flex-1 h-2 bg-brand-border/20 rounded overflow-hidden">
                        <div className={`h-full ${barColor}`} style={{ width: `${Math.max(0, Math.min(100, score * 10))}%` }} />
                      </div>
                      <span className="w-12 shrink-0 text-right text-black dark:text-white">{score.toFixed(1)}/10</span>
                    </div>
                  );
                })}
                <div className="flex flex-wrap justify-between gap-2 font-mono text-[10px] pt-1 border-t border-brand-border/20">
                  <span>WEIGHTED SCORE: <strong className="text-black dark:text-white">{meta.verdict_anchor.final_score}/10</strong></span>
                  <span>SYSTEM VERDICT: <strong className="text-black dark:text-white">{meta.verdict_anchor.verdict}</strong></span>
                  <span>STANCE: <strong className="text-black dark:text-white">{meta.verdict_anchor.stance}</strong></span>
                </div>
              </div>
            )}

            {/* ── Professional Investment Verdict Card ──────────────────── */}
            {stockStanceHtml && (
              <div className={`mt-2 border p-5 relative overflow-hidden transition-all duration-300 ${
                stockStanceType === 'BUY'
                  ? 'bg-green-500/5 border-brand-success/40 shadow-[0_0_18px_rgba(34,197,94,0.06)] animate-fade-in'
                  : stockStanceType === 'AVOID'
                  ? 'bg-red-500/5 border-brand-danger/40 shadow-[0_0_18px_rgba(239,68,68,0.06)] animate-fade-in'
                  : 'bg-yellow-500/5 border-brand-warning/40 shadow-[0_0_18px_rgba(234,179,8,0.06)] animate-fade-in'
              }`}>
                <div className={`absolute top-0 bottom-0 left-0 w-1 ${
                  stockStanceType === 'BUY' ? 'bg-brand-success' : stockStanceType === 'AVOID' ? 'bg-brand-danger' : 'bg-brand-warning'
                }`} />
                <div className="space-y-3 pl-3">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      {stockStanceType === 'BUY'
                        ? <ShieldCheck className="h-5 w-5 text-brand-success" />
                        : stockStanceType === 'AVOID'
                        ? <ShieldAlert className="h-5 w-5 text-brand-danger" />
                        : <AlertTriangle className="h-5 w-5 text-brand-warning" />}
                      <span className={`font-mono text-xs uppercase font-extrabold tracking-wider ${
                        stockStanceType === 'BUY' ? 'text-brand-success' : stockStanceType === 'AVOID' ? 'text-brand-danger' : 'text-brand-warning'
                      }`}>
                        System Investment Verdict: {stockStanceType}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {stockConfidence && (
                        <span className={`text-[9px] font-mono px-2 py-0.5 border ${
                          stockStanceType === 'BUY' ? 'text-brand-success border-brand-success/30 bg-brand-success/10' :
                          stockStanceType === 'AVOID' ? 'text-brand-danger border-brand-danger/30 bg-brand-danger/10' :
                          'text-brand-warning border-brand-warning/30 bg-brand-warning/10'
                        }`}>
                          CONFIDENCE: {stockConfidence}
                        </span>
                      )}
                      <span className={`text-[9px] font-mono px-2 py-0.5 border font-bold ${
                        stockStanceType === 'BUY' ? 'text-brand-success border-brand-success/30 bg-brand-success/10' :
                        stockStanceType === 'AVOID' ? 'text-brand-danger border-brand-danger/30 bg-brand-danger/10' :
                        'text-brand-warning border-brand-warning/30 bg-brand-warning/10'
                      }`}>
                        {stockStanceType}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 border-b border-brand-border/30 pb-3 mt-1 mb-2 font-mono text-[10px]">
                    <div className="space-y-0.5">
                      <span className="text-brand-textMuted uppercase font-bold text-[8px] block">Investor Verdict (Long-Term)</span>
                      <span className={`text-xs font-extrabold ${
                        investorVerdict.includes('BUY') ? 'text-brand-success' : investorVerdict.includes('AVOID') || investorVerdict.includes('REDUCE') ? 'text-brand-danger' : 'text-brand-warning'
                      }`}>
                        {investorVerdict}
                      </span>
                    </div>
                    <div className="space-y-0.5">
                      <span className="text-brand-textMuted uppercase font-bold text-[8px] block">Trader Verdict (Short-Term)</span>
                      <span className={`text-xs font-extrabold ${
                        traderVerdict.includes('BUY') ? 'text-brand-success' : traderVerdict.includes('AVOID') || traderVerdict.includes('REDUCE') ? 'text-brand-danger' : 'text-brand-warning'
                      }`}>
                        {traderVerdict}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-black dark:text-white leading-relaxed font-sans" dangerouslySetInnerHTML={{ __html: stockStanceHtml }} />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quality notes — collapsed, power-user only */}
      {meta?.validation_warnings?.length > 0 && (
        <div className="px-5 border-t border-brand-border/40">
          <button
            type="button"
            onClick={() => setShowWarnings((s) => !s)}
            className="text-[9px] font-mono text-brand-textMuted py-2"
          >
            {showWarnings ? '▲' : '▼'} {meta.validation_warnings.length} QUALITY NOTE{meta.validation_warnings.length > 1 ? 'S' : ''}
          </button>
          {showWarnings && (
            <ul className="pb-3 space-y-1 text-[9px] font-mono text-brand-textMuted list-disc pl-4">
              {meta.validation_warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* Footer disclaimer */}
      <div className="bg-brand-bg border-t border-brand-border px-5 py-3.5 flex items-center gap-3 font-mono text-[9px] text-brand-textMuted leading-relaxed">
        <ShieldCheck className="h-4 w-4 text-brand-primary shrink-0" />
        <p>
          * WARNING: STATISTICAL VALUATIONS REPRESENT PROBABILISTIC FORECASTS, NOT GUARANTEES. NOT FINANCIAL ADVICE.
          {meta && <span className="block mt-0.5 opacity-70">[RAG_TELEMETRY: v2 · RUBRIC_ANCHORED]</span>}
        </p>
      </div>
    </div>
  );
}
