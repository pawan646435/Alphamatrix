"""
AlphaMatrix — Fund Rating Engine v1
====================================
Deterministic, 6-factor composite scoring for mutual funds.
Mirrors the architecture of the Stock Institutional Rating Engine v2.

AI explains the rating. Engine decides the rating.

Score Bands:
  90–100 → Elite
  75–89  → Strong
  60–74  → Good
  45–59  → Average
  0–44   → Avoid
"""

import math
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("app.services.fund_rating_engine")

# ─────────────────────────────────────────────────────────────
# WEIGHT CONFIGURATION
# ─────────────────────────────────────────────────────────────
WEIGHTS = {
    "cagr":        0.25,   # 25% — CAGR across 1Y/3Y/5Y (time-weighted)
    "consistency": 0.15,   # 15% — Rolling return consistency
    "risk":        0.20,   # 20% — Sharpe + Sortino + Max Drawdown
    "quality":     0.15,   # 15% — Expense ratio + AUM strength
    "alpha":       0.15,   # 15% — Alpha vs benchmark
    "peer":        0.10,   # 10% — Category-relative rank
}

# ─────────────────────────────────────────────────────────────
# VERDICT MAPPING
# ─────────────────────────────────────────────────────────────
def map_verdict(score: float) -> str:
    if score >= 90:
        return "Elite"
    elif score >= 75:
        return "Strong"
    elif score >= 60:
        return "Good"
    elif score >= 45:
        return "Average"
    else:
        return "Avoid"


# ─────────────────────────────────────────────────────────────
# FACTOR 1: CAGR Score (25%)
# Weights: 1Y=20%, 3Y=50%, 5Y=30%
# Benchmark: Large Cap → 12%, Mid Cap → 15%, Small Cap → 18%, Index → 10%
# ─────────────────────────────────────────────────────────────
CATEGORY_CAGR_BENCHMARKS = {
    "Large Cap":  {"1y": 12.0, "3y": 12.0, "5y": 12.0},
    "Mid Cap":    {"1y": 15.0, "3y": 16.0, "5y": 16.0},
    "Small Cap":  {"1y": 18.0, "3y": 20.0, "5y": 20.0},
    "Index":      {"1y": 10.0, "3y": 11.0, "5y": 11.0},
    "Sectoral":   {"1y": 14.0, "3y": 15.0, "5y": 14.0},
    "Flexi Cap":  {"1y": 13.0, "3y": 14.0, "5y": 13.0},
    "ELSS":       {"1y": 12.0, "3y": 13.0, "5y": 13.0},
    "Debt":       {"1y":  6.0, "3y":  7.0, "5y":  7.0},
    "Hybrid":     {"1y":  9.0, "3y": 10.0, "5y": 10.0},
}

def _get_benchmark(category: str) -> Dict[str, float]:
    for key in CATEGORY_CAGR_BENCHMARKS:
        if key.lower() in category.lower():
            return CATEGORY_CAGR_BENCHMARKS[key]
    return CATEGORY_CAGR_BENCHMARKS["Large Cap"]

def calculate_cagr_score(cagr_1y: Optional[float], cagr_3y: Optional[float],
                          cagr_5y: Optional[float], category: str) -> float:
    """
    Scores CAGR against category benchmarks.
    Outperformance mapped to 0–100.
    """
    benchmark = _get_benchmark(category)

    def score_single(actual: Optional[float], bench: float) -> float:
        if actual is None:
            return 50.0  # neutral when missing
        # Each 5% above benchmark = +10 pts, capped 0–100
        delta = actual - bench
        raw = 50.0 + (delta / 5.0) * 10.0
        return max(0.0, min(100.0, raw))

    s1 = score_single(cagr_1y, benchmark["1y"])
    s3 = score_single(cagr_3y, benchmark["3y"])
    s5 = score_single(cagr_5y, benchmark["5y"])

    # Time-weighted: 1Y=20%, 3Y=50%, 5Y=30%
    if cagr_5y is not None:
        return s1 * 0.20 + s3 * 0.50 + s5 * 0.30
    elif cagr_3y is not None:
        return s1 * 0.30 + s3 * 0.70
    else:
        return s1


# ─────────────────────────────────────────────────────────────
# FACTOR 2: Consistency Score (15%)
# Derived from NAV history — rolling 12-month return variance
# ─────────────────────────────────────────────────────────────
def calculate_consistency_score(nav_prices: List[float], std_deviation: Optional[float]) -> float:
    """
    Evaluates how consistently a fund delivers returns.
    Low std_deviation = high consistency.
    """
    if std_deviation is not None:
        # Penalize high volatility: <5% → 90+, 5–10% → 70–90, 10–20% → 40–70, >20% → <40
        if std_deviation <= 5:
            return min(100.0, 90 + (5 - std_deviation) * 2)
        elif std_deviation <= 10:
            return 70 + (10 - std_deviation) * 4
        elif std_deviation <= 20:
            return 40 + (20 - std_deviation) * 3
        else:
            return max(0.0, 40 - (std_deviation - 20) * 2)

    if len(nav_prices) < 252:
        return 50.0  # Neutral when insufficient history

    # Compute rolling 12-month returns
    annual_returns = []
    for i in range(252, len(nav_prices)):
        ret = (nav_prices[i] / nav_prices[i - 252] - 1) * 100
        annual_returns.append(ret)

    if not annual_returns:
        return 50.0

    mean_ret = sum(annual_returns) / len(annual_returns)
    variance = sum((r - mean_ret) ** 2 for r in annual_returns) / len(annual_returns)
    sd = math.sqrt(variance)

    if sd <= 3:
        return min(100.0, 92.0)
    elif sd <= 8:
        return 70 + (8 - sd) * 4.4
    elif sd <= 15:
        return 45 + (15 - sd) * 3.57
    else:
        return max(0.0, 45 - (sd - 15) * 2.0)


# ─────────────────────────────────────────────────────────────
# FACTOR 3: Risk Score (20%)
# Inputs: Sharpe, Sortino, Max Drawdown
# ─────────────────────────────────────────────────────────────
def calculate_risk_score(sharpe: Optional[float], sortino: Optional[float],
                          max_drawdown: Optional[float]) -> float:
    """
    Higher Sharpe/Sortino = better risk-adjusted returns.
    Lower drawdown = more capital-protective.
    """
    sharpe_score = 50.0
    if sharpe is not None:
        # Sharpe <0 → bad, 0–0.5 → average, 0.5–1 → good, 1+ → excellent
        if sharpe >= 1.5:
            sharpe_score = 95.0
        elif sharpe >= 1.0:
            sharpe_score = 80.0 + (sharpe - 1.0) * 30
        elif sharpe >= 0.5:
            sharpe_score = 60.0 + (sharpe - 0.5) * 40
        elif sharpe >= 0:
            sharpe_score = 40.0 + sharpe * 40
        else:
            sharpe_score = max(0.0, 40.0 + sharpe * 20)

    sortino_score = 50.0
    if sortino is not None:
        if sortino >= 2.0:
            sortino_score = 95.0
        elif sortino >= 1.2:
            sortino_score = 75.0 + (sortino - 1.2) * 25
        elif sortino >= 0.6:
            sortino_score = 50.0 + (sortino - 0.6) * 41.7
        elif sortino >= 0:
            sortino_score = 30.0 + sortino * 33.3
        else:
            sortino_score = max(0.0, 30 + sortino * 15)

    drawdown_score = 60.0
    if max_drawdown is not None:
        dd = abs(max_drawdown)  # drawdown is typically negative
        if dd <= 5:
            drawdown_score = 95.0
        elif dd <= 10:
            drawdown_score = 80.0 - (dd - 5) * 3
        elif dd <= 20:
            drawdown_score = 65.0 - (dd - 10) * 1.5
        elif dd <= 35:
            drawdown_score = 50.0 - (dd - 20) * 1.0
        else:
            drawdown_score = max(0.0, 35.0 - (dd - 35) * 1.0)

    return sharpe_score * 0.40 + sortino_score * 0.35 + drawdown_score * 0.25


# ─────────────────────────────────────────────────────────────
# FACTOR 4: Quality Score (15%)
# Inputs: Expense Ratio, AUM
# ─────────────────────────────────────────────────────────────
def calculate_quality_score(expense_ratio: Optional[float], aum: Optional[float],
                             category: str) -> float:
    """
    Low expense ratio and large AUM indicate operational quality.
    Debt funds have different expense ratio benchmarks.
    """
    # Expense ratio scoring
    exp_score = 60.0
    if expense_ratio is not None:
        is_index = "index" in category.lower() or "etf" in category.lower()
        is_debt = "debt" in category.lower()
        if is_index:
            # Index funds should be <0.3%
            if expense_ratio <= 0.10:
                exp_score = 98.0
            elif expense_ratio <= 0.30:
                exp_score = 85.0 - (expense_ratio - 0.10) * 65
            elif expense_ratio <= 0.60:
                exp_score = 60.0 - (expense_ratio - 0.30) * 83.3
            else:
                exp_score = max(10.0, 60.0 - expense_ratio * 30)
        elif is_debt:
            if expense_ratio <= 0.50:
                exp_score = 90.0
            elif expense_ratio <= 1.0:
                exp_score = 70.0 - (expense_ratio - 0.50) * 40
            else:
                exp_score = max(20.0, 70.0 - expense_ratio * 25)
        else:
            # Active equity: 0–1% great, 1–1.5% okay, 1.5–2.5% average, >2.5% penalty
            if expense_ratio <= 0.5:
                exp_score = 95.0
            elif expense_ratio <= 1.0:
                exp_score = 80.0 - (expense_ratio - 0.5) * 30
            elif expense_ratio <= 1.5:
                exp_score = 65.0 - (expense_ratio - 1.0) * 30
            elif expense_ratio <= 2.5:
                exp_score = 35.0 - (expense_ratio - 1.5) * 10
            else:
                exp_score = max(10.0, 25.0 - expense_ratio * 5)

    # AUM scoring: very small (<100Cr) or very large (>50000Cr) both have concerns
    aum_score = 60.0
    if aum is not None:
        if aum >= 10000:
            aum_score = 85.0
        elif aum >= 2000:
            aum_score = 75.0 + (aum - 2000) / 800
        elif aum >= 500:
            aum_score = 60.0 + (aum - 500) / 100
        elif aum >= 100:
            aum_score = 40.0 + (aum - 100) / 25
        else:
            aum_score = max(15.0, aum / 10)

    return exp_score * 0.65 + aum_score * 0.35


# ─────────────────────────────────────────────────────────────
# FACTOR 5: Alpha Score (15%)
# ─────────────────────────────────────────────────────────────
def calculate_alpha_component_score(alpha: Optional[float]) -> float:
    """
    Score based on alpha vs benchmark.
    Alpha > 0 = outperforming, < 0 = underperforming.
    """
    if alpha is None:
        return 50.0
    if alpha >= 5:
        return min(100.0, 90 + (alpha - 5) * 2)
    elif alpha >= 2:
        return 75 + (alpha - 2) * 5
    elif alpha >= 0:
        return 55 + alpha * 10
    elif alpha >= -3:
        return 40 + alpha * 5
    else:
        return max(0.0, 40 + alpha * 3)


# ─────────────────────────────────────────────────────────────
# FACTOR 6: Peer Relative Score (10%)
# Based on category rank vs category count
# ─────────────────────────────────────────────────────────────
def calculate_peer_score(category_rank: Optional[int], category_count: Optional[int]) -> float:
    """
    Converts category rank percentile into a score.
    Top 10% → 90+, Bottom 20% → <30
    """
    if category_rank is None or category_count is None or category_count == 0:
        return 55.0  # neutral
    percentile = 1.0 - (category_rank / category_count)
    return max(0.0, min(100.0, percentile * 100))


# ─────────────────────────────────────────────────────────────
# MAIN ENGINE
# ─────────────────────────────────────────────────────────────
def calculate_fund_ratings(
    fund_data: Dict[str, Any],
    nav_prices: List[float],
    category_peers: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Main Fund Rating Engine entry point.

    Args:
        fund_data: dict with fund fields (cagr_1y, cagr_3y, cagr_5y, sharpe_ratio,
                   sortino_ratio, alpha, beta, expense_ratio, aum, category, std_deviation,
                   max_drawdown, category_rank, category_count)
        nav_prices: list of historical NAV float values (most recent last)
        category_peers: list of peer fund dicts for computing relative metrics

    Returns:
        dict with all computed scores + final score + verdict
    """
    category = fund_data.get("category", "Large Cap")

    # ── Factor scores ──
    cagr_score = calculate_cagr_score(
        fund_data.get("cagr_1y"),
        fund_data.get("cagr_3y"),
        fund_data.get("cagr_5y"),
        category
    )

    std_dev = fund_data.get("std_deviation")
    consistency = calculate_consistency_score(nav_prices, std_dev)

    risk_score = calculate_risk_score(
        fund_data.get("sharpe_ratio"),
        fund_data.get("sortino_ratio"),
        fund_data.get("max_drawdown")
    )

    quality = calculate_quality_score(
        fund_data.get("expense_ratio"),
        fund_data.get("aum"),
        category
    )

    alpha_score = calculate_alpha_component_score(fund_data.get("alpha"))

    peer_score = calculate_peer_score(
        fund_data.get("category_rank"),
        fund_data.get("category_count")
    )

    # ── Compute category peers context if provided ──
    cat_avg_cagr_3y = None
    cat_avg_sharpe = None
    cat_avg_alpha = None
    if category_peers:
        cagrs = [p.get("cagr_3y") for p in category_peers if p.get("cagr_3y") is not None]
        sharpes = [p.get("sharpe_ratio") for p in category_peers if p.get("sharpe_ratio") is not None]
        alphas = [p.get("alpha") for p in category_peers if p.get("alpha") is not None]
        cat_avg_cagr_3y = sum(cagrs) / len(cagrs) if cagrs else None
        cat_avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else None
        cat_avg_alpha = sum(alphas) / len(alphas) if alphas else None

    # ── Weighted final score ──
    final_score = (
        cagr_score        * WEIGHTS["cagr"]        +
        consistency       * WEIGHTS["consistency"]  +
        risk_score        * WEIGHTS["risk"]         +
        quality           * WEIGHTS["quality"]      +
        alpha_score       * WEIGHTS["alpha"]        +
        peer_score        * WEIGHTS["peer"]
    )
    final_score = max(0.0, min(100.0, round(final_score, 2)))

    verdict = map_verdict(final_score)

    logger.info(
        f"[FundRatingEngine] {fund_data.get('fund_name', 'Unknown')} | "
        f"Score={final_score:.1f} | Verdict={verdict} | "
        f"CAGR={cagr_score:.1f} Consistency={consistency:.1f} Risk={risk_score:.1f} "
        f"Quality={quality:.1f} Alpha={alpha_score:.1f} Peer={peer_score:.1f}"
    )

    return {
        "fund_score":          final_score,
        "fund_verdict":        verdict,
        "cagr_score":          round(cagr_score, 2),
        "consistency_score":   round(consistency, 2),
        "risk_score":          round(risk_score, 2),
        "quality_score":       round(quality, 2),
        "alpha_component":     round(alpha_score, 2),
        "peer_score":          round(peer_score, 2),
        "category_avg_cagr_3y": cat_avg_cagr_3y,
        "category_avg_sharpe":  cat_avg_sharpe,
        "category_avg_alpha":   cat_avg_alpha,
    }


# ─────────────────────────────────────────────────────────────
# HELPERS: Compute std_deviation and max_drawdown from NAV prices
# ─────────────────────────────────────────────────────────────
def compute_std_deviation(nav_prices: List[float]) -> Optional[float]:
    """Annualized standard deviation from daily NAV prices."""
    if len(nav_prices) < 30:
        return None
    daily_returns = [
        (nav_prices[i] / nav_prices[i - 1] - 1) * 100
        for i in range(1, len(nav_prices))
    ]
    if not daily_returns:
        return None
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / len(daily_returns)
    daily_sd = math.sqrt(variance)
    annualized = daily_sd * math.sqrt(252)
    return round(annualized, 4)


def compute_max_drawdown(nav_prices: List[float]) -> Optional[float]:
    """Maximum peak-to-trough drawdown as a percentage."""
    if len(nav_prices) < 30:
        return None
    max_drawdown = 0.0
    peak = nav_prices[0]
    for price in nav_prices:
        if price > peak:
            peak = price
        dd = (price - peak) / peak * 100
        if dd < max_drawdown:
            max_drawdown = dd
    return round(max_drawdown, 4)


def generate_ai_fund_prompt(fund_data: Dict[str, Any], ratings: Dict[str, Any]) -> str:
    """
    Generates a structured prompt for AI to explain the fund rating.
    AI explains, does NOT decide.
    """
    fund_name = fund_data.get("fund_name", "Unknown Fund")
    category = fund_data.get("category", "Unknown")
    verdict = ratings["fund_verdict"]
    score = ratings["fund_score"]

    cagr_1y = fund_data.get("cagr_1y")
    cagr_3y = fund_data.get("cagr_3y")
    cagr_5y = fund_data.get("cagr_5y")
    sharpe = fund_data.get("sharpe_ratio")
    sortino = fund_data.get("sortino_ratio")
    alpha = fund_data.get("alpha")
    beta = fund_data.get("beta")
    expense_ratio = fund_data.get("expense_ratio")
    aum = fund_data.get("aum")
    std_dev = fund_data.get("std_deviation")
    max_dd = fund_data.get("max_drawdown")
    cat_rank = fund_data.get("category_rank")
    cat_count = fund_data.get("category_count")

    def fmt(v, suffix=""):
        return f"{v:.2f}{suffix}" if v is not None else "N/A"

    prompt = f"""You are an institutional fund analyst at AlphaMatrix. A deterministic quantitative engine has already assigned this fund a rating.

YOUR TASK: Explain the rating in professional, concise language.
DO NOT change or question the verdict. DO NOT say "I recommend" or "you should buy".

=== FUND PROFILE ===
Fund: {fund_name}
Category: {category}
Score: {score}/100
Verdict: {verdict}

=== PERFORMANCE ===
CAGR 1Y: {fmt(cagr_1y, '%')}  |  CAGR 3Y: {fmt(cagr_3y, '%')}  |  CAGR 5Y: {fmt(cagr_5y, '%')}

=== RISK-ADJUSTED METRICS ===
Sharpe Ratio: {fmt(sharpe)}
Sortino Ratio: {fmt(sortino)}
Alpha: {fmt(alpha)}
Beta: {fmt(beta)}
Std Deviation: {fmt(std_dev, '%')}
Max Drawdown: {fmt(max_dd, '%')}

=== QUALITY ===
Expense Ratio: {fmt(expense_ratio, '%')}
AUM: {fmt(aum, ' Cr')}
Category Rank: {cat_rank}/{cat_count} in {category}

=== SCORE BREAKDOWN ===
CAGR Score: {ratings.get('cagr_score', 'N/A')}
Consistency Score: {ratings.get('consistency_score', 'N/A')}
Risk Score: {ratings.get('risk_score', 'N/A')}
Quality Score: {ratings.get('quality_score', 'N/A')}
Alpha Component: {ratings.get('alpha_component', 'N/A')}
Peer Score: {ratings.get('peer_score', 'N/A')}

=== OUTPUT FORMAT (strictly follow) ===
Write three labeled paragraphs:

**BULL CASE:**
(2–3 sentences explaining the fund's strongest attributes that justify holding or adding it)

**BEAR CASE:**
(2–3 sentences explaining the key risks or weaknesses in this fund's profile)

**RATING RATIONALE:**
(2–3 sentences explaining why the engine scored this fund {score}/100 and rated it {verdict})

Keep each paragraph professional, data-driven, and under 80 words. Do not add headers or bullet points outside this structure.
"""
    return prompt
