"""
AlphaMatrix — Backtesting Engine v3
=====================================
Generates retrospective verdicts using historical price data and
measures actual performance vs. those verdicts over multiple horizons.

Methodology:
  - Uses existing StockPriceHistory records (no new data required)
  - Generates verdict at T-0 using metrics available at that date
  - Measures actual returns at T+30, T+90, T+180, T+365
  - Compares against NIFTY 50 baseline (proxy: Reliance + HDFCBANK avg)
  - Reports: BUY/HOLD/AVOID accuracy, avg return, win rate, max drawdown

NOTE: For demonstration, uses the deterministic scoring engine with
      the price data available at each historical point. In production,
      this would require storing historical fundamental snapshots.
"""

import logging
import math
import random
from datetime import date, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger("app.services.backtesting")

# ─────────────────────────────────────────────────────────────
# VERDICT THRESHOLDS (same as Institutional Rating Engine v2)
# ─────────────────────────────────────────────────────────────
def _score_to_verdict(score: float) -> str:
    if score >= 75:   return "STRONG BUY"
    elif score >= 62: return "BUY"
    elif score >= 47: return "HOLD"
    elif score >= 33: return "REDUCE"
    else:             return "AVOID"

# ─────────────────────────────────────────────────────────────
# TECHNICAL SCORE from price window (simplified)
# ─────────────────────────────────────────────────────────────
def _calculate_momentum_score(prices: List[float]) -> float:
    """
    Simplified momentum score from a price window.
    Inputs: list of closing prices.
    """
    if len(prices) < 20:
        return 50.0

    # 20-day vs 50-day SMA crossover
    sma20 = sum(prices[-20:]) / 20
    sma50 = sum(prices[-50:]) / 50 if len(prices) >= 50 else sum(prices) / len(prices)

    # RSI approximation (last 14 periods)
    gains = []
    losses = []
    for i in range(max(len(prices) - 14, 1), len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains) / 14 if gains else 0
    avg_loss = sum(losses) / 14 if losses else 0.001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Score components
    sma_score = 65.0 if sma20 > sma50 else 35.0
    rsi_score = 80.0 if 45 <= rsi <= 65 else (60.0 if 35 <= rsi < 45 else (55.0 if 65 < rsi <= 75 else 30.0))
    return sma_score * 0.5 + rsi_score * 0.5


def _calculate_cagr_from_window(prices: List[float], window_days: int) -> float:
    """Compute annualized return from a price window."""
    if len(prices) < 2:
        return 0.0
    start = prices[0]
    end = prices[-1]
    if start <= 0:
        return 0.0
    years = window_days / 365.25
    if years <= 0:
        return 0.0
    try:
        cagr = ((end / start) ** (1.0 / years) - 1.0) * 100
        return round(cagr, 4)
    except Exception:
        return 0.0


def _compute_max_drawdown(prices: List[float]) -> float:
    """Maximum drawdown in percent."""
    if len(prices) < 2:
        return 0.0
    peak = prices[0]
    max_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        dd = (peak - p) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 4)


def _composite_score(prices_window: List[float], window_days: int) -> float:
    """Simplified composite score from historical price window only."""
    momentum = _calculate_momentum_score(prices_window)
    cagr = _calculate_cagr_from_window(prices_window, window_days)
    cagr_score = max(0.0, min(100.0, 50 + cagr * 2))
    dd = _compute_max_drawdown(prices_window)
    risk_score = max(0.0, min(100.0, 80 - dd * 2))
    return momentum * 0.40 + cagr_score * 0.35 + risk_score * 0.25


# ─────────────────────────────────────────────────────────────
# BACKTEST: SINGLE STOCK
# ─────────────────────────────────────────────────────────────
def backtest_stock(
    symbol: str,
    prices: List[Dict[str, Any]],
    current_verdict: Optional[str] = None,
    current_score: Optional[float] = None
) -> Dict[str, Any]:
    """
    Runs a backtest for a single stock using its stored price history.

    Args:
        symbol: Stock ticker
        prices: List of {date: date, close: float} sorted ascending
        current_verdict: The current institutional verdict (for display)
        current_score: The current institutional score

    Returns:
        dict with backtest results at T+30, T+90, T+180, T+365
    """
    if len(prices) < 90:
        return {
            "symbol": symbol,
            "status": "insufficient_data",
            "message": f"Need 90+ days of price history. Have {len(prices)}.",
        }

    price_vals = [p["close"] for p in prices]
    dates      = [p["date"]  for p in prices]

    # Use first 60% as "training" window to generate historical verdict
    split_idx = max(60, len(price_vals) - 365)
    training_prices = price_vals[:split_idx]
    eval_start_price = price_vals[split_idx]
    eval_start_date  = dates[split_idx]

    # Generate historical verdict from training window
    hist_score = _composite_score(training_prices, min(len(training_prices), 252))
    historical_verdict = _score_to_verdict(hist_score)

    # Measure returns at horizons
    remaining_prices = price_vals[split_idx:]
    remaining_dates  = dates[split_idx:]

    def _return_at_days(n_days: int) -> Optional[float]:
        """Find closing price approximately n_days after eval_start."""
        target = eval_start_date + timedelta(days=n_days)
        best = None
        for d, p in zip(remaining_dates, remaining_prices):
            if d <= target:
                best = p
            else:
                break
        if best is None:
            return None
        return round((best - eval_start_price) / eval_start_price * 100, 4)

    ret_30  = _return_at_days(30)
    ret_90  = _return_at_days(90)
    ret_180 = _return_at_days(180)
    ret_365 = _return_at_days(365)

    # Benchmark: simple NIFTY 50 proxy — assume 12% annualized
    bench_30  = round(12.0 / 365 * 30, 4)
    bench_90  = round(12.0 / 365 * 90, 4)
    bench_180 = round(12.0 / 365 * 180, 4)
    bench_365 = round(12.0, 4)

    def _verdict_success(verdict: str, ret: Optional[float], bench: float) -> Optional[bool]:
        """Returns True if verdict was correct, False if wrong, None if no data."""
        if ret is None:
            return None
        if verdict in ("BUY", "STRONG BUY"):
            return ret > bench       # success = outperformed benchmark
        elif verdict == "HOLD":
            return abs(ret - bench) <= 5.0  # within 5% of benchmark
        elif verdict in ("AVOID", "REDUCE"):
            return ret < bench       # success = underperformed (avoided loss)
        return None

    success_365 = _verdict_success(historical_verdict, ret_365, bench_365)
    success_90  = _verdict_success(historical_verdict, ret_90,  bench_90)

    return {
        "symbol":             symbol,
        "status":             "completed",
        "historical_verdict": historical_verdict,
        "historical_score":   round(hist_score, 2),
        "current_verdict":    current_verdict,
        "current_score":      current_score,
        "eval_start_date":    eval_start_date.isoformat() if hasattr(eval_start_date, "isoformat") else str(eval_start_date),
        "returns": {
            "t30_days":   {"return_pct": ret_30,  "benchmark_pct": bench_30,  "outperformed": ret_30 is not None and ret_30 > bench_30},
            "t90_days":   {"return_pct": ret_90,  "benchmark_pct": bench_90,  "outperformed": ret_90 is not None and ret_90 > bench_90},
            "t180_days":  {"return_pct": ret_180, "benchmark_pct": bench_180, "outperformed": ret_180 is not None and ret_180 > bench_180},
            "t365_days":  {"return_pct": ret_365, "benchmark_pct": bench_365, "outperformed": ret_365 is not None and ret_365 > bench_365},
        },
        "verdict_success_90d":  success_90,
        "verdict_success_365d": success_365,
        "max_drawdown_eval": _compute_max_drawdown(remaining_prices[:min(len(remaining_prices), 252)]),
    }


# ─────────────────────────────────────────────────────────────
# AGGREGATE BACKTESTING SUMMARY
# ─────────────────────────────────────────────────────────────
def aggregate_backtest_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregates individual backtest results into an engine-level accuracy report.
    """
    completed = [r for r in results if r.get("status") == "completed"]
    if not completed:
        return {"status": "no_data", "total_stocks": len(results)}

    # Verdict accuracy at 365d
    buy_results   = [r for r in completed if r["historical_verdict"] in ("BUY", "STRONG BUY") and r["verdict_success_365d"] is not None]
    hold_results  = [r for r in completed if r["historical_verdict"] == "HOLD"                 and r["verdict_success_365d"] is not None]
    avoid_results = [r for r in completed if r["historical_verdict"] in ("AVOID", "REDUCE")    and r["verdict_success_365d"] is not None]

    def _accuracy(lst):
        if not lst: return None
        return round(sum(1 for r in lst if r["verdict_success_365d"]) / len(lst) * 100, 1)

    buy_accuracy   = _accuracy(buy_results)
    hold_accuracy  = _accuracy(hold_results)
    avoid_accuracy = _accuracy(avoid_results)

    # Average returns by verdict at T+365
    def _avg_return(lst):
        rets = [r["returns"]["t365_days"]["return_pct"] for r in lst if r["returns"]["t365_days"]["return_pct"] is not None]
        return round(sum(rets) / len(rets), 2) if rets else None

    # Overall win rate (outperformed benchmark at T+365)
    with_365 = [r for r in completed if r["returns"]["t365_days"]["return_pct"] is not None]
    win_rate = round(sum(1 for r in with_365 if r["returns"]["t365_days"]["outperformed"]) / len(with_365) * 100, 1) if with_365 else None

    # Max drawdown average
    drawdowns = [r["max_drawdown_eval"] for r in completed if r.get("max_drawdown_eval") is not None]
    avg_drawdown = round(sum(drawdowns) / len(drawdowns), 2) if drawdowns else None

    return {
        "status":                 "completed",
        "total_stocks":           len(results),
        "evaluated_stocks":       len(completed),
        "benchmark":              "NIFTY 50 (12% annualized proxy)",
        "verdict_accuracy": {
            "BUY_STRONG_BUY": {
                "accuracy_365d": buy_accuracy,
                "avg_return_365d": _avg_return(buy_results),
                "count": len(buy_results)
            },
            "HOLD": {
                "accuracy_365d": hold_accuracy,
                "avg_return_365d": _avg_return(hold_results),
                "count": len(hold_results)
            },
            "AVOID_REDUCE": {
                "accuracy_365d": avoid_accuracy,
                "avg_return_365d": _avg_return(avoid_results),
                "count": len(avoid_results)
            },
        },
        "overall_win_rate_365d": win_rate,
        "avg_max_drawdown_pct":  avg_drawdown,
        "t90_win_rate": round(
            sum(1 for r in completed if r["returns"]["t90_days"]["outperformed"]) /
            max(1, len([r for r in completed if r["returns"]["t90_days"]["return_pct"] is not None])) * 100, 1
        ),
    }
