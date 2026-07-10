/**
 * analystText.js
 * Shared text-labeling helpers for AI-generated analyst copy, used by both
 * BriefingReport.jsx (AI Equity Briefing) and AnalystResponseCard.jsx
 * (Interactive Analyst chat), so [DATA]/[ANALYTICAL]/[MACRO] tags and
 * [FACT:...] citations render identically wherever the LLM emits them
 * rather than each surface parsing its own dialect.
 */

/** Strips a leading [DATA] / [ANALYTICAL] / [MACRO CONTEXT ...] tag off a line, if present. */
export function stripLeadLabel(line) {
  if (/^\[DATA\]/i.test(line)) return { type: 'DATA', text: line.replace(/^\[DATA\]\s*/i, '') };
  if (/^\[ANALYTICAL\]/i.test(line)) return { type: 'ANALYTICAL', text: line.replace(/^\[ANALYTICAL\]\s*/i, '') };
  const macroMatch = line.match(/^\[MACRO CONTEXT[^\]]*\]\s*(.*)$/i);
  if (macroMatch) return { type: 'MACRO', text: macroMatch[1] };
  return { type: null, text: line };
}

/** Replaces [FACT: ...] tags with a superscript footnote ref, pushing the fact text into `footnotes`. */
export function formatInline(text, footnotes) {
  let out = text.replace(/\[FACT:([^\]]+)\]/g, (_, inner) => {
    footnotes.push(inner.trim());
    return `<sup class="text-brand-primary/80 font-mono" style="font-size:9px;margin:0 1px;">${footnotes.length}</sup>`;
  });
  out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  return out;
}

export const LABEL_STYLE = {
  DATA: { border: 'border-l-brand-success', badge: 'text-brand-success' },
  ANALYTICAL: { border: 'border-l-brand-primary', badge: 'text-brand-primary' },
  MACRO: { border: 'border-l-[#555555]', badge: 'text-[#888888]' },
};
