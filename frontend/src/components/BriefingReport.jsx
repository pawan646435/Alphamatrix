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

/** Strips a leading [DATA] / [ANALYTICAL] / [MACRO CONTEXT ...] tag off a line, if present. */
function stripLeadLabel(line) {
  if (/^\[DATA\]/i.test(line)) return { type: 'DATA', text: line.replace(/^\[DATA\]\s*/i, '') };
  if (/^\[ANALYTICAL\]/i.test(line)) return { type: 'ANALYTICAL', text: line.replace(/^\[ANALYTICAL\]\s*/i, '') };
  const macroMatch = line.match(/^\[MACRO CONTEXT[^\]]*\]\s*(.*)$/i);
  if (macroMatch) return { type: 'MACRO', text: macroMatch[1] };
  return { type: null, text: line };
}

/** Replaces [FACT: ...] tags with a superscript footnote ref, pushing the fact text into `footnotes`. */
function formatInline(text, footnotes) {
  let out = text.replace(/\[FACT:([^\]]+)\]/g, (_, inner) => {
    footnotes.push(inner.trim());
    return `<sup class="text-brand-primary/80 font-mono" style="font-size:9px;margin:0 1px;">${footnotes.length}</sup>`;
  });
  out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  return out;
}

const LABEL_STYLE = {
  DATA: { border: 'border-l-brand-success', badge: 'text-brand-success' },
  ANALYTICAL: { border: 'border-l-brand-primary', badge: 'text-brand-primary' },
  MACRO: { border: 'border-l-[#555555]', badge: 'text-[#888888]' },
};

/** Splits raw briefing markdown into labeled paragraph blocks + a shared footnote list. */
function parseSectionBlocks(sectionContent) {
  const footnotes = [];
  const lines = (sectionContent || '').split('\n').map((l) => l.trim()).filter(Boolean);
  const blocks = [];
  lines.forEach((rawLine) => {
    const gapMatch = rawLine.match(/^⚠️\s*DATA GAP:?(.*)$/);
    const anomalyMatch = rawLine.match(/^⚠️\s*ANOMALY:?(.*)$/);
    if (gapMatch) {
      blocks.push({ kind: 'warning', color: 'warning', html: `⚠️ DATA GAP:${formatInline(gapMatch[1], footnotes)}` });
      return;
    }
    if (anomalyMatch) {
      blocks.push({ kind: 'warning', color: 'danger', html: `⚠️ ANOMALY:${formatInline(anomalyMatch[1], footnotes)}` });
      return;
    }
    const isBullet = /^[-*]\s*/.test(rawLine);
    const stripped = rawLine.replace(/^[-*]\s*/, '');
    const { type, text } = stripLeadLabel(stripped);
    const html = (isBullet ? '• ' : '') + formatInline(text, footnotes);
    blocks.push({ kind: 'para', type, html });
  });
  return { blocks, footnotes };
}

function FootnoteList({ footnotes }) {
  if (!footnotes || footnotes.length === 0) return null;
  return (
    <div className="mt-2 pt-2 border-t border-brand-border/30 space-y-0.5">
      {footnotes.map((f, i) => (
        <p key={i} className="font-mono text-[9px] text-brand-textMuted/50 leading-relaxed">
          <sup className="mr-1">{i + 1}</sup>{f}
        </p>
      ))}
    </div>
  );
}

/** Renders the labeled-paragraph blocks produced by parseSectionBlocks, plus a trailing footnote list. */
function SectionBlocks({ blocks, footnotes, plain = false }) {
  if (!blocks || blocks.length === 0) return null;
  return (
    <div className="space-y-2">
      {blocks.map((b, i) => {
        if (b.kind === 'warning') {
          const isWarn = b.color === 'warning';
          return (
            <div
              key={i}
              className={`border-l-2 pl-2.5 py-1 text-xs font-sans ${isWarn ? 'border-brand-warning/60 text-brand-warning' : 'border-brand-danger/60 text-brand-danger'}`}
              dangerouslySetInnerHTML={{ __html: b.html }}
            />
          );
        }
        const style = !plain && b.type ? LABEL_STYLE[b.type] : null;
        return (
          <div key={i} className={`relative text-xs leading-relaxed font-sans text-brand-textMuted ${style ? `border-l-2 ${style.border} pl-3 py-1` : ''}`}>
            {style && (
              <span className={`absolute top-0.5 right-0 font-mono uppercase tracking-wider opacity-35 ${style.badge}`} style={{ fontSize: '9px' }}>
                {b.type}
              </span>
            )}
            <p className={style ? 'pr-14' : ''} dangerouslySetInnerHTML={{ __html: b.html }} />
          </div>
        );
      })}
      <FootnoteList footnotes={footnotes} />
    </div>
  );
}

const PILLAR_META = [
  { key: 'valuation', label: 'VALUATION', weight: 30 },
  { key: 'quality', label: 'QUALITY', weight: 25 },
  { key: 'momentum', label: 'MOMENTUM', weight: 20 },
  { key: 'risk', label: 'RISK', weight: 25 },
];

const CASE_STYLE = {
  'Bull Case': { border: 'border-t-brand-success', label: 'BULL CASE', color: 'text-brand-success' },
  'Base Case': { border: 'border-t-brand-primary', label: 'BASE CASE', color: 'text-brand-primary' },
  'Bear Case': { border: 'border-t-brand-danger', label: 'BEAR CASE', color: 'text-brand-danger' },
};

function verdictToType(v) {
  if (!v) return 'HOLD';
  const s = v.toUpperCase();
  if (s.includes('BUY')) return 'BUY';
  if (s.includes('SELL') || s.includes('AVOID') || s.includes('REDUCE')) return 'AVOID';
  return 'HOLD';
}

function verdictColorClass(type) {
  return type === 'BUY' ? 'text-brand-success' : type === 'AVOID' ? 'text-brand-danger' : 'text-brand-warning';
}

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

  const getSectionContent = (sectionTitle) => {
    if (!briefingText) return null;
    const parts = briefingText.split(`### ${sectionTitle}`);
    if (parts.length < 2) return null;
    return parts[1].split('###')[0].trim();
  };

  const renderBriefingSection = (sectionTitle) => {
    const sectionContent = getSectionContent(sectionTitle);
    if (!sectionContent) return null;
    const { blocks, footnotes } = parseSectionBlocks(sectionContent);
    return (
      <div>
        <h4 className="text-[10px] font-bold text-brand-primary uppercase tracking-wider font-display pb-2.5 mb-3 border-b border-brand-border/40">{sectionTitle}</h4>
        <SectionBlocks blocks={blocks} footnotes={footnotes} />
      </div>
    );
  };

  const renderBriefingSectionContentOnly = (sectionTitle) => {
    const sectionContent = getSectionContent(sectionTitle);
    if (!sectionContent) return null;
    const { blocks, footnotes } = parseSectionBlocks(sectionContent);
    return <SectionBlocks blocks={blocks} footnotes={footnotes} />;
  };

  const renderCaseCard = (title) => {
    const sectionContent = getSectionContent(title);
    if (!sectionContent) return null;
    const { blocks, footnotes } = parseSectionBlocks(sectionContent);
    const style = CASE_STYLE[title];
    return (
      <div className={`border-t-2 ${style.border} bg-brand-bg/40 p-4 space-y-2.5`}>
        <h5 className={`text-[10px] font-bold uppercase tracking-wider font-display ${style.color}`}>{style.label}</h5>
        <SectionBlocks blocks={blocks} footnotes={footnotes} plain />
      </div>
    );
  };

  const renderRiskFactors = (raw) => {
    if (!raw) return null;
    const footnotes = [];
    const lines = raw.split('\n').map((l) => l.trim()).filter(Boolean);
    const items = [];
    lines.forEach((line) => {
      const stripped = line.replace(/^[-*]\s*/, '');
      const { text } = stripLeadLabel(stripped);
      if (text.trim()) items.push(formatInline(text, footnotes));
    });
    if (items.length === 0) return null;
    return (
      <div className="space-y-2">
        {items.map((html, i) => (
          <div key={i} className="flex items-start gap-2 border-l-2 border-brand-warning/60 bg-brand-warning/5 px-3 py-2">
            <span className="text-brand-warning shrink-0 text-xs">⚠</span>
            <p className="text-xs font-sans text-brand-textMuted leading-relaxed" dangerouslySetInnerHTML={{ __html: html }} />
          </div>
        ))}
        <FootnoteList footnotes={footnotes} />
      </div>
    );
  };

  // ── Verdict parsing — mirrors the original StockDetail.jsx logic, now
  // operating on the unwrapped briefingText so v1 and v2 both work. ──
  let investorVerdict = investorVerdictProp || 'HOLD';
  let traderVerdict = traderVerdictProp || 'HOLD';
  let stockConfidence = confidenceScoreProp ? `${Math.round(confidenceScoreProp)}%` : '';
  let stockStanceHtml = '';

  if (!isBriefingLoading && briefingText) {
    const verdictParts = briefingText.split('### Final Verdict');
    if (verdictParts.length >= 2) {
      const verdictContent = verdictParts[1].split('###')[0].trim();
      const { blocks, footnotes } = parseSectionBlocks(verdictContent);
      stockStanceHtml = blocks.map((b) => b.html).join(' ');
      if (footnotes.length) {
        // Facts referenced in the final-verdict prose are folded into the same footnote list.
      }
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

  const alphaModelType = verdictToType(investorVerdict.includes('BUY') || traderVerdict.includes('BUY') ? 'BUY' : (investorVerdict.includes('AVOID') || traderVerdict.includes('AVOID') || investorVerdict.includes('REDUCE') || traderVerdict.includes('REDUCE')) ? 'AVOID' : 'HOLD');

  const verdictAnchor = meta?.verdict_anchor || null;
  const primaryVerdictType = verdictAnchor ? verdictToType(verdictAnchor.verdict) : alphaModelType;
  const showVerdictBox = !!verdictAnchor || !!stockStanceHtml;

  const verdictBoxTheme =
    primaryVerdictType === 'BUY'
      ? { card: 'bg-green-500/5 border-brand-success/40 shadow-[0_0_18px_rgba(34,197,94,0.06)]', bar: 'bg-brand-success', text: 'text-brand-success', icon: <ShieldCheck className="h-5 w-5 text-brand-success" /> }
      : primaryVerdictType === 'AVOID'
      ? { card: 'bg-red-500/5 border-brand-danger/40 shadow-[0_0_18px_rgba(239,68,68,0.06)]', bar: 'bg-brand-danger', text: 'text-brand-danger', icon: <ShieldAlert className="h-5 w-5 text-brand-danger" /> }
      : { card: 'bg-yellow-500/5 border-brand-warning/40 shadow-[0_0_18px_rgba(234,179,8,0.06)]', bar: 'bg-brand-warning', text: 'text-brand-warning', icon: <AlertTriangle className="h-5 w-5 text-brand-warning" /> };

  const confidenceBadgeColor =
    meta?.data_confidence_label === 'HIGH' ? 'text-brand-success border-brand-success/30 bg-brand-success/10'
      : meta?.data_confidence_label === 'MEDIUM' ? 'text-brand-warning border-brand-warning/30 bg-brand-warning/10'
      : 'text-brand-danger border-brand-danger/30 bg-brand-danger/10';

  const hasGapsOrAnomalies = meta && ((meta.missing_fields?.length || 0) > 0 || (meta.anomalies?.length || 0) > 0);

  return (
    <div data-symbol={symbol} className="w-full border border-brand-border bg-brand-surface shadow-xl flex flex-col justify-between animate-fade-in-up" style={{ animationDelay: '200ms' }}>
      {/* Panel header */}
      <div className="bg-brand-bg border-b border-brand-border px-5 py-5 flex flex-col gap-3 text-xs">
        <div className="flex items-center gap-2 text-brand-primary">
          <Cpu className="h-4 w-4 animate-pulse-subtle" />
          <h3 className="font-bold text-black dark:text-white uppercase tracking-wider font-display">AI EQUITY BRIEFING REPORT</h3>
        </div>

        {meta && !isBriefingLoading ? (
          <div className="flex flex-col gap-2">
            {/* Row 1 — primary trust indicators */}
            <div className="flex flex-wrap items-center gap-2">
              <span className={`px-3 py-1 border font-mono font-bold text-[11px] ${confidenceBadgeColor}`}>
                DATA CONFIDENCE: {meta.data_confidence_label} · {meta.data_completeness_pct}% COVERAGE
              </span>
              <span className="px-2 py-1 border border-brand-border font-mono text-[9px] text-brand-textMuted">
                INTEGRITY: {Math.round(meta.trust_score)}/100
              </span>
              <span className="px-2 py-1 border border-brand-border font-mono text-[9px] text-brand-textMuted uppercase">
                [RAG_TELEMETRY: v2 · RUBRIC_ANCHORED]
              </span>
            </div>
            {/* Row 2 — secondary metadata */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[9px] text-brand-textMuted/70">
              <span>ANALYSIS BASED ON {meta.available_metrics}/{meta.total_metrics} AVAILABLE METRICS</span>
              {meta.generated_at && <span>GENERATED: {new Date(meta.generated_at).toLocaleString('en-IN')}</span>}
              {lastSync && <span>DATA SYNC: {new Date(lastSync).toLocaleString('en-IN')}</span>}
            </div>
          </div>
        ) : (
          <span className="font-mono text-[9px] text-brand-textMuted uppercase self-start">[RAG_TELEMETRY: aligned]</span>
        )}
      </div>

      <div className="p-6 sm:p-7 md:p-8">
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
          <div className="space-y-7">
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
              <div className="p-4 border border-brand-primary/20 bg-brand-primary/5 space-y-2.5">
                <div className="flex items-center gap-1.5 text-brand-primary">
                  <Star className="h-3.5 w-3.5 fill-current" />
                  <h4 className="text-[10px] font-bold uppercase tracking-wider font-display">Core Investment Thesis</h4>
                </div>
                <SectionBlocks {...parseSectionBlocks(bullCase)} />
              </div>
            ) : (briefingText && briefingText.includes('### Investment Thesis') && (
              <div className="p-4 border border-brand-primary/20 bg-brand-primary/5 space-y-2.5">
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

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-t border-brand-border/40 pt-7">
              {renderCaseCard('Bull Case')}
              {renderCaseCard('Base Case')}
              {renderCaseCard('Bear Case')}
            </div>

            {/* Risk Factors */}
            {bearCase ? (
              <div className="border-t border-brand-border/40 pt-7 space-y-3">
                <h4 className="text-[10px] font-bold text-brand-warning uppercase tracking-wider font-display flex items-center gap-1.5">⚠️ Key Risk Factors</h4>
                {renderRiskFactors(bearCase)}
              </div>
            ) : (briefingText && briefingText.includes('### Risk Factors') && (
              <div className="border-t border-brand-border/40 pt-7 space-y-3">
                <h4 className="text-[10px] font-bold text-brand-warning uppercase tracking-wider font-display flex items-center gap-1.5">⚠️ Key Risk Factors</h4>
                {renderRiskFactors(getSectionContent('Risk Factors'))}
              </div>
            ))}

            {/* ── Consolidated Verdict Card — merges the pillar-score breakdown
                (rubric model) with the Alpha Score model verdict, so the two
                verdict systems appear once instead of as two stacked boxes. ── */}
            {showVerdictBox && (
              <div className={`border-t border-brand-border/40 pt-7`}>
                <div className={`border p-5 sm:p-6 relative overflow-hidden ${verdictBoxTheme.card}`}>
                  <div className={`absolute top-0 bottom-0 left-0 w-1 ${verdictBoxTheme.bar}`} />
                  <div className="space-y-4 pl-3">
                    {/* Header row */}
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2">
                        {verdictBoxTheme.icon}
                        <span className={`font-mono text-xs uppercase font-extrabold tracking-wider ${verdictBoxTheme.text}`}>
                          Verdict Breakdown
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {stockConfidence && (
                          <span className={`text-[9px] font-mono px-2 py-0.5 border ${verdictBoxTheme.text} border-current/30 bg-current/10`}>
                            CONFIDENCE: {stockConfidence}
                          </span>
                        )}
                        {verdictAnchor?.diverges_from_alpha_score && (
                          <span className="text-[9px] font-mono font-bold px-2 py-0.5 border border-brand-warning/40 bg-brand-warning/10 text-brand-warning uppercase">
                            ⚠️ DIVERGES FROM ALPHA SCORE MODEL
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Pillar bars — rubric model, v2 only */}
                    {verdictAnchor && (
                      <div className="space-y-1.5">
                        {PILLAR_META.map(({ key, label, weight }) => {
                          const score = verdictAnchor.pillar_scores?.[key] ?? 0;
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
                      </div>
                    )}

                    {/* Weighted score / verdict / stance — rubric model */}
                    {verdictAnchor && (
                      <div className="flex flex-wrap justify-between gap-2 font-mono text-[10px] pt-2 border-t border-brand-border/20">
                        <span>WEIGHTED: <strong className="text-black dark:text-white">{verdictAnchor.final_score}/10</strong></span>
                        <span>VERDICT: <strong className={verdictColorClass(primaryVerdictType)}>{verdictAnchor.verdict}</strong></span>
                        <span>STANCE: <strong className="text-black dark:text-white">{verdictAnchor.stance}</strong></span>
                      </div>
                    )}

                    {/* Alpha Score model — secondary row */}
                    <div className="grid grid-cols-2 gap-4 border-t border-brand-border/20 pt-3 font-mono text-[10px]">
                      <div className="space-y-0.5">
                        <span className="text-brand-textMuted uppercase font-bold text-[8px] block">Alpha Score Model — Investor (Long)</span>
                        <span className={`text-xs font-extrabold ${verdictColorClass(verdictToType(investorVerdict))}`}>{investorVerdict}</span>
                      </div>
                      <div className="space-y-0.5">
                        <span className="text-brand-textMuted uppercase font-bold text-[8px] block">Alpha Score Model — Trader (Short)</span>
                        <span className={`text-xs font-extrabold ${verdictColorClass(verdictToType(traderVerdict))}`}>{traderVerdict}</span>
                      </div>
                    </div>

                    {verdictAnchor?.diverges_from_alpha_score && (
                      <p className="text-[9px] font-mono text-brand-warning">
                        NOTE: Rubric diverges from Alpha Score model — see analysis above.
                      </p>
                    )}

                    {stockStanceHtml && (
                      <p className="text-xs text-black dark:text-white leading-relaxed font-sans pt-3 border-t border-brand-border/20" dangerouslySetInnerHTML={{ __html: stockStanceHtml }} />
                    )}
                  </div>
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
