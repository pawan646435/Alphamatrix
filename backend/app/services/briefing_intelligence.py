"""
Briefing Intelligence — grounding layer for the AI Equity Briefing Report.

This module sits between the raw stock metrics and the LLM prompt used by
`ai_agent.generate_stock_briefing`. It provides:

  1. SECTOR_BENCHMARKS — a static, curated table of Indian-market sector medians
     used purely for the briefing's narrative grounding/citations. This is
     intentionally separate from `stock_ingestion.get_sector_averages()`, which
     computes *live* DB averages for the Alpha Score engine — that source can be
     noisy or empty for sparsely-populated sectors, whereas this table gives the
     LLM a stable comparison point for every symbol regardless of DB population.
  2. assess_data_quality — flags missing/anomalous metrics before the LLM ever
     sees them, so gaps are known facts rather than silently-guessed narrative.
  3. score_verdict — a deterministic BUY/HOLD/SELL rubric independent of the LLM,
     used to anchor the briefing's narrative. NOTE: this is a distinct, additive
     verdict for grounding the *briefing text* only — it does not replace or feed
     `StockMaster.investor_verdict` / `trader_verdict`, which remain driven by the
     existing 5-factor Alpha Score model (`calculate_institutional_ratings`) and
     continue to drive the page's main "System Investment Verdict" banner unchanged.
  4. build_briefing_prompt — assembles the system prompt with citation/labelling/
     anomaly/verdict-anchor rules layered onto the briefing's *existing* section
     structure (Executive Summary, Performance Analysis, ... Final Verdict, etc.)
     rather than replacing it, since the frontend parses those exact "### Header"
     strings in several places (bull/bear case cards, Research Timeline, Confidence
     Score badge) that must keep working for every briefing, old and new.
  5. validate_briefing_output — post-hoc checks the LLM actually complied.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ── 1A. Sector benchmarks ───────────────────────────────────────────────────
# Realistic Indian-market medians (NSE sectoral indices / Screener.in ballparks).
# Keys match the short sector labels this codebase actually stores for its
# ~40 curated/overridden symbols (see stock_ingestion.SECTOR_OVERRIDES).
SECTOR_BENCHMARKS: Dict[str, Dict[str, float]] = {
    "Cement":              {"pe_ratio": 28.0, "pb_ratio": 3.5, "roe": 12.0, "debt_equity": 0.4, "cagr_3y": 0.12, "ebitda_margin": 20.0},
    "IT":                  {"pe_ratio": 26.0, "pb_ratio": 8.0, "roe": 28.0, "debt_equity": 0.1, "cagr_3y": 0.13, "ebitda_margin": 24.0},
    "Banking":             {"pe_ratio": 14.0, "pb_ratio": 2.2, "roe": 15.0, "debt_equity": 6.0, "cagr_3y": 0.15, "ebitda_margin": 30.0},
    "Pharma":              {"pe_ratio": 32.0, "pb_ratio": 5.0, "roe": 16.0, "debt_equity": 0.3, "cagr_3y": 0.14, "ebitda_margin": 22.0},
    "FMCG":                {"pe_ratio": 45.0, "pb_ratio": 12.0, "roe": 30.0, "debt_equity": 0.2, "cagr_3y": 0.11, "ebitda_margin": 20.0},
    "Auto":                {"pe_ratio": 22.0, "pb_ratio": 4.0, "roe": 16.0, "debt_equity": 0.5, "cagr_3y": 0.14, "ebitda_margin": 12.0},
    "Realty":              {"pe_ratio": 35.0, "pb_ratio": 3.0, "roe": 10.0, "debt_equity": 0.8, "cagr_3y": 0.20, "ebitda_margin": 25.0},
    "Energy":              {"pe_ratio": 12.0, "pb_ratio": 1.8, "roe": 14.0, "debt_equity": 0.7, "cagr_3y": 0.10, "ebitda_margin": 15.0},
    "Metal":               {"pe_ratio": 10.0, "pb_ratio": 1.5, "roe": 12.0, "debt_equity": 0.6, "cagr_3y": 0.10, "ebitda_margin": 15.0},
    "Textile":             {"pe_ratio": 20.0, "pb_ratio": 2.5, "roe": 12.0, "debt_equity": 0.6, "cagr_3y": 0.10, "ebitda_margin": 10.0},
    "NBFC":                {"pe_ratio": 18.0, "pb_ratio": 2.5, "roe": 14.0, "debt_equity": 4.5, "cagr_3y": 0.16, "ebitda_margin": 40.0},
    "Infrastructure":      {"pe_ratio": 25.0, "pb_ratio": 3.5, "roe": 12.0, "debt_equity": 1.0, "cagr_3y": 0.15, "ebitda_margin": 15.0},
    "Consumer Durables":   {"pe_ratio": 55.0, "pb_ratio": 9.0, "roe": 18.0, "debt_equity": 0.3, "cagr_3y": 0.15, "ebitda_margin": 12.0},
    "Chemicals":           {"pe_ratio": 28.0, "pb_ratio": 4.0, "roe": 15.0, "debt_equity": 0.4, "cagr_3y": 0.12, "ebitda_margin": 18.0},
    "Healthcare":          {"pe_ratio": 40.0, "pb_ratio": 6.0, "roe": 15.0, "debt_equity": 0.3, "cagr_3y": 0.13, "ebitda_margin": 20.0},
    "Logistics":           {"pe_ratio": 30.0, "pb_ratio": 4.0, "roe": 14.0, "debt_equity": 0.5, "cagr_3y": 0.13, "ebitda_margin": 14.0},
    "Telecom":             {"pe_ratio": 35.0, "pb_ratio": 4.0, "roe": 8.0, "debt_equity": 1.2, "cagr_3y": 0.12, "ebitda_margin": 38.0},
    "Power":               {"pe_ratio": 15.0, "pb_ratio": 1.8, "roe": 12.0, "debt_equity": 1.5, "cagr_3y": 0.10, "ebitda_margin": 30.0},
    "Agriculture":         {"pe_ratio": 22.0, "pb_ratio": 3.0, "roe": 14.0, "debt_equity": 0.5, "cagr_3y": 0.11, "ebitda_margin": 12.0},
    "Default":             {"pe_ratio": 24.0, "pb_ratio": 3.5, "roe": 15.0, "debt_equity": 0.6, "cagr_3y": 0.12, "ebitda_margin": 18.0},
}

# Aliases for sector strings this codebase actually stores that don't literally
# match a SECTOR_BENCHMARKS key — either legacy short labels used by
# stock_ingestion.SECTOR_OVERRIDES (e.g. "Metals", "Defence", "PSU") or the raw
# yfinance GICS-style sector names returned for any symbol without an override
# (the majority of dynamically-ingested stocks).
SECTOR_ALIASES: Dict[str, str] = {
    "Metals": "Metal",
    "Defence": "Infrastructure",
    "PSU": "Power",
    "Capital Goods": "Infrastructure",
    "Technology": "IT",
    "Financial Services": "Banking",
    "Consumer Cyclical": "Auto",
    "Consumer Defensive": "FMCG",
    "Basic Materials": "Metal",
    "Communication Services": "Telecom",
    "Industrials": "Infrastructure",
    "Utilities": "Power",
    "Real Estate": "Realty",
}

NIFTY_CAGR_BENCHMARK = 0.12  # ~12% long-run Nifty 50 CAGR assumption


def resolve_sector_benchmark(sector: Optional[str]) -> Tuple[str, Dict[str, float]]:
    """Returns (resolved_label, benchmark_dict) for a raw DB sector string."""
    if sector:
        if sector in SECTOR_BENCHMARKS:
            return sector, SECTOR_BENCHMARKS[sector]
        alias = SECTOR_ALIASES.get(sector)
        if alias and alias in SECTOR_BENCHMARKS:
            return alias, SECTOR_BENCHMARKS[alias]
    return "Default", SECTOR_BENCHMARKS["Default"]


# ── 1B. Data quality assessor ───────────────────────────────────────────────
REQUIRED_METRICS = [
    "pe_ratio", "pb_ratio", "roe", "debt_equity", "dividend_yield", "beta",
    "cagr_1y", "cagr_3y", "cagr_5y", "market_cap", "alpha_score", "sector",
]


def assess_data_quality(stock_data: Dict[str, Any]) -> Dict[str, Any]:
    missing_fields: List[str] = []
    available = 0
    for field in REQUIRED_METRICS:
        val = stock_data.get(field)
        if val is None or val == "Unknown" or val == "":
            missing_fields.append(field)
        else:
            available += 1

    anomalies: List[str] = []
    pe = stock_data.get("pe_ratio")
    pb = stock_data.get("pb_ratio")
    roe = stock_data.get("roe")
    de = stock_data.get("debt_equity")
    beta = stock_data.get("beta")

    if pe is not None and pe < 0:
        anomalies.append(f"Negative P/E ({pe}) — company likely loss-making")
    if pb is not None and pb < 0:
        anomalies.append("Negative P/B — possible negative book value")
    if roe is not None and roe > 100:
        anomalies.append("Abnormally high ROE — may indicate near-zero equity")
    if de is not None and de > 5:
        anomalies.append(f"Very high leverage ({de}x)")
    if beta is not None and abs(beta) > 3:
        anomalies.append("Extreme beta — possible data quality issue")

    total = len(REQUIRED_METRICS)
    completeness_pct = round((available / total) * 100, 1) if total else 0.0

    if completeness_pct >= 80:
        confidence_label = "HIGH"
    elif completeness_pct >= 55:
        confidence_label = "MEDIUM"
    else:
        confidence_label = "LOW"

    return {
        "total_metrics": total,
        "available_metrics": available,
        "missing_fields": missing_fields,
        "anomalies": anomalies,
        "data_completeness_pct": completeness_pct,
        "confidence_label": confidence_label,
    }


# ── 1C. Deterministic verdict scorer ────────────────────────────────────────
def _clamp(v: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, v))


# Pillar weights for the deterministic briefing rubric. Technical carries the
# Alpha Score model's own technical_score (RSI/MACD/DMA/trend) so the rubric is
# no longer blind to market-structure signals; the other four weights are scaled
# down proportionally (0.85x their original 30/25/20/25 split) so the total still
# sums to 100%. See PHASE 0 divergence analysis: thresholds were already aligned
# (rubric BUY >= 6.5/10 ~= Alpha Score BUY >= 66/100) — the real gap was missing
# inputs, and Technical was the one available-but-unused signal.
PILLAR_WEIGHTS: Dict[str, float] = {
    "valuation": 0.26,
    "quality": 0.21,
    "momentum": 0.17,
    "risk": 0.21,
    "technical": 0.15,
}


def score_verdict(stock_data: Dict[str, Any], benchmarks: Dict[str, float]) -> Dict[str, Any]:
    notes: Dict[str, List[str]] = {"valuation": [], "quality": [], "momentum": [], "risk": [], "technical": []}

    # ── Valuation (30%) — P/E and P/B vs sector median, cheaper = higher score
    pe, pb = stock_data.get("pe_ratio"), stock_data.get("pb_ratio")
    val_scores = []
    if pe is not None and benchmarks["pe_ratio"]:
        s = _clamp(10 - ((pe / benchmarks["pe_ratio"]) - 1) * 10)
        val_scores.append(s)
        notes["valuation"].append(f"P/E {pe} vs sector median {benchmarks['pe_ratio']}")
    if pb is not None and benchmarks["pb_ratio"]:
        s = _clamp(10 - ((pb / benchmarks["pb_ratio"]) - 1) * 10)
        val_scores.append(s)
        notes["valuation"].append(f"P/B {pb} vs sector median {benchmarks['pb_ratio']}")
    if val_scores:
        valuation_score = sum(val_scores) / len(val_scores)
    else:
        valuation_score = 5.0
        notes["valuation"].append("P/E and P/B unavailable — scored neutral (data gap)")

    # ── Quality (25%) — ROE (higher better) and Debt/Equity (lower better)
    roe, de = stock_data.get("roe"), stock_data.get("debt_equity")
    qual_scores = []
    if roe is not None and benchmarks["roe"]:
        s = _clamp(5 + ((roe / benchmarks["roe"]) - 1) * 5)
        qual_scores.append(s)
        notes["quality"].append(f"ROE {roe}% vs sector median {benchmarks['roe']}%")
    if de is not None and benchmarks["debt_equity"]:
        s = _clamp(10 - ((de / benchmarks["debt_equity"]) - 1) * 5)
        qual_scores.append(s)
        notes["quality"].append(f"Debt/Equity {de}x vs sector median {benchmarks['debt_equity']}x")
    if qual_scores:
        quality_score = sum(qual_scores) / len(qual_scores)
    else:
        quality_score = 5.0
        notes["quality"].append("ROE and Debt/Equity unavailable — scored neutral (data gap)")

    # ── Momentum (20%) — 1Y/3Y CAGR vs Nifty 50 and sector median
    cagr_1y, cagr_3y = stock_data.get("cagr_1y"), stock_data.get("cagr_3y")
    mom_scores = []
    if cagr_1y is not None:
        s = _clamp(5 + ((cagr_1y - NIFTY_CAGR_BENCHMARK) / 0.10) * 5)
        mom_scores.append(s)
        notes["momentum"].append(f"1Y CAGR {round(cagr_1y * 100, 1)}% vs Nifty ~{round(NIFTY_CAGR_BENCHMARK * 100)}%")
    if cagr_3y is not None and benchmarks["cagr_3y"]:
        s = _clamp(5 + ((cagr_3y - benchmarks["cagr_3y"]) / 0.10) * 5)
        mom_scores.append(s)
        notes["momentum"].append(f"3Y CAGR {round(cagr_3y * 100, 1)}% vs sector median {round(benchmarks['cagr_3y'] * 100)}%")
    if mom_scores:
        momentum_score = sum(mom_scores) / len(mom_scores)
    else:
        momentum_score = 5.0
        notes["momentum"].append("1Y/3Y CAGR unavailable — scored neutral (data gap)")

    # ── Risk (25%) — lower beta = higher score
    beta = stock_data.get("beta")
    if beta is not None:
        risk_score = _clamp(10 - beta * 3)
        notes["risk"].append(f"Beta {beta}")
    else:
        risk_score = 5.0
        notes["risk"].append("Beta unavailable — scored neutral (data gap)")

    # ── Technical (15%) — reuses the Alpha Score model's own technical_score
    # (RSI/MACD/DMA50/DMA200/trend-structure, 0-100), rescaled to 0-10. This is
    # the same signal `calculate_institutional_ratings` uses, so the rubric no
    # longer ignores market-structure entirely.
    technical_score_100 = stock_data.get("technical_score")
    if technical_score_100 is not None:
        technical_score = _clamp(technical_score_100 / 10.0)
        notes["technical"].append(f"Technical score {technical_score_100}/100 (RSI/MACD/trend-derived)")
    else:
        technical_score = 5.0
        notes["technical"].append("Technical score unavailable — scored neutral (data gap)")

    pillar_scores = {
        "valuation": round(valuation_score, 2),
        "quality": round(quality_score, 2),
        "momentum": round(momentum_score, 2),
        "risk": round(risk_score, 2),
        "technical": round(technical_score, 2),
    }

    final_score = round(
        sum(pillar_scores[k] * w for k, w in PILLAR_WEIGHTS.items()),
        2,
    )

    if final_score >= 7.5:
        verdict, stance = "BUY", "STRONG BUY"
    elif final_score >= 6.5:
        verdict, stance = "BUY", "ACCUMULATE"
    elif final_score >= 4.5:
        verdict, stance = "HOLD", "HOLD"
    elif final_score >= 3.5:
        verdict, stance = "SELL", "REDUCE"
    else:
        verdict, stance = "SELL", "STRONG SELL"

    return {
        "pillar_scores": pillar_scores,
        "pillar_notes": notes,
        "final_score": final_score,
        "verdict": verdict,
        "stance": stance,
    }


# Alpha Score model verdicts (calculate_institutional_ratings.map_verdict in
# stock_ingestion.py) use a 5-tier scale; the briefing rubric above uses a
# 3-tier BUY/HOLD/SELL scale. Both must be compared by *direction*, not by
# exact string, or "STRONG BUY" vs "BUY" would falsely register as a divergence.
ALPHA_VERDICT_TO_DIRECTION = {
    "STRONG BUY": "BUY", "BUY": "BUY",
    "HOLD": "HOLD",
    "REDUCE": "SELL", "AVOID": "SELL", "SELL": "SELL", "STRONG SELL": "SELL",
}


def normalize_alpha_direction(verdict: Optional[str]) -> str:
    if not verdict:
        return "HOLD"
    return ALPHA_VERDICT_TO_DIRECTION.get(verdict.upper().strip(), "HOLD")


def check_verdict_divergence(anchor: Dict[str, Any], stock_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compares the briefing rubric's verdict direction against the Alpha Score
    model's investor_verdict/trader_verdict (see calculate_institutional_ratings
    in stock_ingestion.py) — a separate, independently-weighted model. Rubric
    weights/Alpha Score model are NOT touched here; this only flags disagreement."""
    investor_direction = normalize_alpha_direction(stock_data.get("investor_verdict"))
    trader_direction = normalize_alpha_direction(stock_data.get("trader_verdict"))
    rubric_direction = anchor["verdict"]
    return {
        "diverges": rubric_direction != investor_direction or rubric_direction != trader_direction,
        "investor_direction": investor_direction,
        "trader_direction": trader_direction,
    }


# Pillars the Alpha Score model scores that the briefing rubric still does not
# (Technical was moved out of this list once it became a rubric pillar above).
# Kept honest rather than hidden — see Task 3/5 in the divergence-explainability work.
RUBRIC_MISSING_PILLARS = [
    "Fundamental (ROCE/margins/growth)",
    "Sector Relative (live peer comparison)",
]

_DIRECTION_RANK = {"SELL": 0, "HOLD": 1, "BUY": 2}


def compute_divergence_reason(anchor: Dict[str, Any], divergence: Dict[str, Any]) -> Dict[str, Any]:
    """Builds a specific, pillar-grounded explanation for why the briefing rubric's
    verdict disagrees with the Alpha Score model, instead of a generic "diverges" flag.
    Used both to ground the LLM prompt's reconciliation note and to populate the
    `divergence_reason` field persisted in the briefing's meta payload."""
    rubric_direction = anchor["verdict"]

    if not divergence.get("diverges"):
        return {
            "rubric_verdict": rubric_direction,
            "rubric_score": anchor["final_score"],
            "alpha_verdict": divergence.get("investor_direction", "HOLD"),
            "gap_explanation": "Rubric and Alpha Score model agree directionally — no reconciliation needed.",
            "missing_pillars": RUBRIC_MISSING_PILLARS,
        }

    investor_direction = divergence.get("investor_direction", "HOLD")
    trader_direction = divergence.get("trader_direction", "HOLD")
    investor_gap = abs(_DIRECTION_RANK[rubric_direction] - _DIRECTION_RANK[investor_direction])
    trader_gap = abs(_DIRECTION_RANK[rubric_direction] - _DIRECTION_RANK[trader_direction])
    # Whichever of investor/trader sits furthest from the rubric drives the explanation.
    alpha_direction = investor_direction if investor_gap >= trader_gap else trader_direction
    rank_gap = max(investor_gap, trader_gap)
    magnitude = "Opposite-direction (BUY vs SELL)" if rank_gap >= 2 else "Adjacent-tier"

    strongest_pillar = max(anchor["pillar_scores"], key=anchor["pillar_scores"].get)
    weakest_pillar = min(anchor["pillar_scores"], key=anchor["pillar_scores"].get)

    gap_explanation = (
        f"{magnitude} divergence: rubric says {rubric_direction} ({anchor['final_score']}/10), "
        f"Alpha Score model says {alpha_direction}. The rubric is pulled toward {rubric_direction} "
        f"mainly by its {strongest_pillar} pillar ({anchor['pillar_scores'][strongest_pillar]}/10) "
        f"and dragged down by {weakest_pillar} ({anchor['pillar_scores'][weakest_pillar]}/10). The Alpha "
        f"Score model additionally scores {' and '.join(RUBRIC_MISSING_PILLARS)}, which the rubric does "
        f"not include — a strong rubric pillar here can outweigh a weaker signal visible only to the "
        f"Alpha Score model."
    )

    return {
        "rubric_verdict": rubric_direction,
        "rubric_score": anchor["final_score"],
        "alpha_verdict": alpha_direction,
        "gap_explanation": gap_explanation,
        "missing_pillars": RUBRIC_MISSING_PILLARS,
    }


# ── 1D. Prompt builder ──────────────────────────────────────────────────────
def build_briefing_prompt(stock_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    quality = assess_data_quality(stock_data)
    sector_label, benchmarks = resolve_sector_benchmark(stock_data.get("sector"))
    anchor = score_verdict(stock_data, benchmarks)
    divergence = check_verdict_divergence(anchor, stock_data)
    divergence_reason = compute_divergence_reason(anchor, divergence)

    context = {
        "data_quality": quality,
        "verdict_anchor": anchor,
        "sector": sector_label,
        "benchmarks": benchmarks,
        "divergence": divergence,
        "divergence_reason": divergence_reason,
    }

    benchmark_table = "\n".join(f"- {k}: {v}" for k, v in benchmarks.items())
    metrics_vs_benchmark = "\n".join(
        f"- {field}: {stock_data.get(field)} (sector median: {benchmarks.get(field, 'n/a')})"
        for field in ("pe_ratio", "pb_ratio", "roe", "debt_equity", "cagr_3y")
    )
    missing_str = ", ".join(quality["missing_fields"]) or "None"
    anomalies_str = "\n".join(f"- {a}" for a in quality["anomalies"]) or "None detected"
    pillar_str = "\n".join(
        f"- {pillar.title()} ({int(PILLAR_WEIGHTS[pillar] * 100)}%): {anchor['pillar_scores'][pillar]}/10 — "
        f"{'; '.join(anchor['pillar_notes'][pillar])}"
        for pillar in ("valuation", "quality", "momentum", "risk", "technical")
    )
    weights_str = ", ".join(f"{k.title()} {int(w * 100)}%" for k, w in PILLAR_WEIGHTS.items())

    system_prompt = f"""
You are a Lead Portfolio Manager and CFA specializing in Indian Equities, writing
a grounded, auditable equity research briefing. Follow these rules exactly.

RULE 1 — CITE YOUR EVIDENCE
Every factual claim must reference a specific metric from the data block below
using the format [FACT: metric_name=value]. Example:
"Valuation is elevated [FACT: pe_ratio={stock_data.get('pe_ratio')} vs sector {benchmarks['pe_ratio']}]".

RULE 2 — LABEL YOUR REASONING
Every paragraph must be prefixed with [DATA] for direct metric claims or
[ANALYTICAL] for interpretation/projection.

RULE 3 — HONOUR THE VERDICT ANCHOR
Your investment verdict MUST be {anchor['verdict']} with stance {anchor['stance']}.
This was computed from a deterministic rubric ({weights_str} — weighted score
{anchor['final_score']}/10). You may add
narrative nuance but you CANNOT reverse or contradict this direction. If you
believe qualitative factors override this, write "OVERRIDE NOTE: [reason]" and
it will be reviewed by a human analyst — do not silently substitute your own verdict.

RULE 4 — FLAG MISSING DATA
Fields unavailable for this stock: {missing_str}.
For each one referenced in your analysis, write "⚠️ DATA GAP: {{field_name}} unavailable — analysis limited."
Do NOT estimate, infer, or silently skip missing fields.

RULE 5 — NO HALLUCINATION
Do not reference news, earnings calls, management commentary, or any information
not present in the data block below. Macro context is allowed but must be labelled
"[MACRO CONTEXT — external knowledge]" and limited to 2 sentences max per section.

RULE 6 — FLAG ANOMALIES
Detected anomalies:
{anomalies_str}
Flag each one with "⚠️ ANOMALY" in the relevant section. Do not silently normalise anomalous data.
{f'''
RULE 7 — RECONCILE WITH THE ALPHA SCORE MODEL
The platform's separate Alpha Score model (a different, independently-weighted
scoring engine) gives Investor Verdict "{stock_data.get('investor_verdict') or 'HOLD'}"
and Trader Verdict "{stock_data.get('trader_verdict') or 'HOLD'}" — this DIVERGES in
direction from the rubric verdict above ({anchor['verdict']}).

Specific, pre-computed reason for this divergence (grounded in the actual pillar
scores below — cite it, do not invent a different explanation):
{divergence_reason['gap_explanation']}

In the "### Final Verdict" section you MUST include a line in EXACTLY this format:
"NOTE: Rubric score ({anchor['final_score']}/10 → {anchor['verdict']}) diverges from
Alpha Score model ({divergence_reason['alpha_verdict']}). Reason: [briefly restate the
pre-computed reason above in your own words, staying grounded in the cited pillars]."
Do not omit this line.
''' if divergence['diverges'] else ''}
── STOCK DATA BLOCK ──
Symbol: {stock_data.get('symbol')}
Name: {stock_data.get('company_name')}
Sector: {stock_data.get('sector')} (benchmarked against: {sector_label})
Industry: {stock_data.get('industry')}
Market Cap: ₹{stock_data.get('market_cap')} Cr
{metrics_vs_benchmark}
- dividend_yield: {stock_data.get('dividend_yield')}
- beta: {stock_data.get('beta')}
- 1Y CAGR: {round((stock_data.get('cagr_1y') or 0) * 100, 2)}%
- 3Y CAGR: {round((stock_data.get('cagr_3y') or 0) * 100, 2)}%
- 5Y CAGR: {round((stock_data.get('cagr_5y') or 0) * 100, 2)}%
- Alpha Score: {stock_data.get('alpha_score')}/100

── SECTOR BENCHMARK TABLE ({sector_label}) ──
{benchmark_table}

── DATA QUALITY SUMMARY ──
Completeness: {quality['data_completeness_pct']}% ({quality['available_metrics']}/{quality['total_metrics']} metrics available)
Confidence: {quality['confidence_label']}
Missing fields: {missing_str}
Anomalies: {anomalies_str}

── PRE-COMPUTED VERDICT RUBRIC (do not recompute, cite as-is) ──
{pillar_str}
Weighted Score: {anchor['final_score']}/10
Verdict: {anchor['verdict']} | Stance: {anchor['stance']}

Note: the platform separately shows a "System Investment Verdict" of
{stock_data.get('investor_verdict') or 'HOLD'} (investor) / {stock_data.get('trader_verdict') or 'HOLD'} (trader),
computed by a different 5-factor model. Both are grounded in the same underlying
metrics and should usually agree directionally; if you notice tension between
them, note it plainly rather than picking one silently.

── REQUIRED OUTPUT FORMAT ──
Return clean Markdown with EXACTLY these headers, in this order (do not rename,
merge, or drop any of them — downstream parsing depends on these exact strings):
### Executive Summary
### Performance Analysis
### Fundamental Analysis
### Sector Analysis
### Macro Analysis
### Geopolitical Analysis
### Investment Thesis
### Risk Factors
### Research Timeline
(3 to 5 entries, newest to oldest, each on its own line in EXACTLY this format:
"- **Month Year - Event Title**: Detailed description | Relevance Score: [1-10]/10 | Impact Assessment: [High | Medium | Low]")
### Bull Case
### Base Case
### Bear Case
### Final Verdict
Restate the exact pillar scores and weighted total from the rubric above
verbatim, then add your narrative — do not invent different numbers. Also state
the system Investor/Trader Verdict from the note above.
### Confidence Score
Confidence Score: {quality['confidence_label']} ({quality['data_completeness_pct']}%)
Explain this rating with reference to data completeness and metric agreement.

Safety Constraint: Do NOT state anything with absolute certainty. Always use
probability-based language (e.g. "represents a likely possibility", "probable trend").
"""
    return system_prompt, context


# ── 1E. Output validator ────────────────────────────────────────────────────
# Matches the "REQUIRED OUTPUT FORMAT" headers above (kept identical to the
# pre-existing prompt's section names so parse_briefing_sections() and the
# frontend's `### Header`-based rendering — bull/bear case cards, Research
# Timeline, Confidence Score badge, Final Verdict banner — keep working
# unchanged for both v1 and v2 briefings).
REQUIRED_SECTIONS = [
    "Executive Summary", "Investment Thesis", "Performance Analysis",
    "Fundamental Analysis", "Sector Analysis", "Risk Factors",
    "Final Verdict", "Confidence Score",
]


def validate_briefing_output(
    raw_llm_output: str,
    stock_data: Dict[str, Any],
    verdict_anchor: Dict[str, Any],
) -> Dict[str, Any]:
    text = raw_llm_output or ""
    trust_score = 100.0
    warnings: List[str] = []

    sections_present = [s for s in REQUIRED_SECTIONS if f"### {s}" in text]
    sections_missing = [s for s in REQUIRED_SECTIONS if s not in sections_present]
    if sections_missing:
        trust_score -= 8 * len(sections_missing)
        warnings.append(f"Missing sections: {', '.join(sections_missing)}")

    lower = text.lower()
    verdict_match = verdict_anchor["verdict"].lower() in lower or verdict_anchor["stance"].lower() in lower
    # An explicit OVERRIDE NOTE is a deliberate, flagged deviation — don't
    # penalise it as a silent contradiction, but it still needs human review.
    if "override note" in lower:
        verdict_match = True
        warnings.append("LLM issued an OVERRIDE NOTE — flagged for human analyst review")
    elif not verdict_match:
        trust_score -= 20
        warnings.append(f"Verdict mismatch: expected {verdict_anchor['verdict']}/{verdict_anchor['stance']} not found in output")

    quality = assess_data_quality(stock_data)
    for field in quality["missing_fields"]:
        if field not in lower and "data gap" not in lower:
            trust_score -= 3
            warnings.append(f"Missing field '{field}' not flagged with DATA GAP")

    if quality["anomalies"] and "anomaly" not in lower and "⚠️" not in text:
        trust_score -= 5
        warnings.append("Anomalies detected but not flagged with ⚠️ ANOMALY in output")

    word_count = len(text.split())
    if word_count < 300:
        trust_score -= 15
        warnings.append(f"Output is short ({word_count} words) — may be truncated")

    trust_score = max(0.0, min(100.0, trust_score))
    is_valid = trust_score >= 60 and verdict_match and not sections_missing

    return {
        "is_valid": is_valid,
        "trust_score": round(trust_score, 1),
        "warnings": warnings,
        "verdict_match": verdict_match,
        "sections_present": sections_present,
        "sections_missing": sections_missing,
        "cleaned_text": text.strip(),
    }


def build_storage_payload(
    text: str,
    quality: Dict[str, Any],
    anchor: Dict[str, Any],
    validation: Dict[str, Any],
    divergence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assembles the v2 ai_summary storage payload (see Task 2 Step 6)."""
    divergence = divergence or {"diverges": False, "investor_direction": "HOLD", "trader_direction": "HOLD"}
    divergence_reason = compute_divergence_reason(anchor, divergence)
    return {
        "text": text,
        "meta": {
            "trust_score": validation["trust_score"],
            "data_completeness_pct": quality["data_completeness_pct"],
            "data_confidence_label": quality["confidence_label"],
            "total_metrics": quality["total_metrics"],
            "available_metrics": quality["available_metrics"],
            "missing_fields": quality["missing_fields"],
            "anomalies": quality["anomalies"],
            "verdict_anchor": {
                "verdict": anchor["verdict"],
                "stance": anchor["stance"],
                "final_score": anchor["final_score"],
                "pillar_scores": anchor["pillar_scores"],
                "diverges_from_alpha_score": divergence.get("diverges", False),
            },
            "divergence_reason": divergence_reason if divergence.get("diverges") else None,
            "validation_warnings": validation["warnings"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "briefing_version": "v2",
        },
    }
