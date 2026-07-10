"""
AlphaMatrix — Backtesting Engine v4 (snapshot-based, Phase 4 Track 2)
=======================================================================
Backtests the ACTUAL Alpha Score model's own past verdicts, using real
`VerdictSnapshot` rows recorded at ingestion time (see
workers/stock_ingestion.py:write_verdict_snapshot), instead of the
price-only proxy model in services/backtesting.py (`_composite_score`/
`_score_to_verdict`), which is unrelated to the Alpha Score model and the
AI briefing rubric — see that module's docstring for the full explanation
of why it's an independent model.

DATA AVAILABILITY: this only works from the point verdict_snapshots starts
accumulating (Phase 4 Track 2's rollout date) onward — there is no
retroactive backfill possible, since a snapshot is a record of what the
model actually said *at the time*, not something that can be reconstructed
after the fact from data available today. Expect "insufficient_data" for
most/all symbols for a while after rollout; see the Phase 4 summary for the
approximate date the first T+30 comparison becomes possible.

METHODOLOGY — deliberately different from v1's single-anchor design:
  - v1 (backtesting.py) generates ONE retrospective verdict at a single
    "eval_start" date (~60% through the stored price series) and measures
    T+30/90/180/365 returns all from that same anchor.
  - v2 (this module) instead has up to FOUR real, independently-timed
    verdict snapshots available — one taken ~30 days ago, one ~90, one
    ~180, one ~365 (whenever the stock happened to be re-ingested near
    those points) — because the model's actual verdict legitimately
    changes over time as fundamentals/technicals/price move. Each horizon
    is therefore anchored to ITS OWN closest prior snapshot, not a shared
    anchor: "how did the T-90 snapshot's verdict perform over its own
    90-day forward window", not "how did today's verdict look 90 days
    ago" (which isn't answerable — verdicts aren't retroactively knowable).
  - "as of" reference = the latest available price date for the symbol
    (not necessarily today), so this degrades gracefully for a stock that
    hasn't been re-ingested recently rather than raising an error.

Reuses the SAME flat 12%-annualized NIFTY 50 proxy and the same
BUY/HOLD/AVOID success classification as v1 (duplicated here, not
cross-imported) — kept identical on purpose so v1 and v2 win-rates are
directly comparable while both run in parallel (see
api/v1/stocks.py:/backtest-v2/{symbol}, not yet wired into the live
/backtest/summary endpoint). Changing the benchmark itself is out of scope
for this phase — see services/backtesting.py's docstring.

model_version (from VerdictSnapshot) is returned per-horizon for
transparency but not filtered on yet — there is currently only one version
("v2", see workers/stock_ingestion.py:ALPHA_MODEL_VERSION). Once the
scoring formula changes and that constant is bumped, filtering/flagging
cross-version comparisons is a natural next step, not implemented here.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.services.backtesting_v2")

HORIZONS_DAYS = (30, 90, 180, 365)


def _verdict_success(verdict: Optional[str], ret: Optional[float], bench: float) -> Optional[bool]:
    """Returns True if verdict was correct, False if wrong, None if no data.
    Identical classification to backtesting.py's _verdict_success — kept in
    sync deliberately, see module docstring."""
    if ret is None or not verdict:
        return None
    if verdict in ("BUY", "STRONG BUY"):
        return ret > bench
    elif verdict == "HOLD":
        return abs(ret - bench) <= 5.0
    elif verdict in ("AVOID", "REDUCE"):
        return ret < bench
    return None


def _benchmark_pct(n_days: int) -> float:
    """Flat 12%-annualized NIFTY 50 proxy — same as backtesting.py, see module docstring."""
    if n_days >= 365:
        return round(12.0, 4)
    return round(12.0 / 365 * n_days, 4)


def _max_drawdown_pct(closes: List[float]) -> Optional[float]:
    """Maximum peak-to-trough drawdown, as a percentage — same logic as
    backtesting.py's _compute_max_drawdown, duplicated for module independence."""
    if len(closes) < 2:
        return None
    peak = closes[0]
    max_dd = 0.0
    for p in closes:
        if p > peak:
            peak = p
        dd = (peak - p) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 4)


def _price_on_or_before(dates: List[date], closes: List[float], target: date) -> Optional[float]:
    """Closest close price on or before `target`. Returns None if no such price exists."""
    best = None
    for d, p in zip(dates, closes):
        if d <= target:
            best = p
        else:
            break
    return best


def _closest_snapshot_on_or_before(
    snapshots: List[Dict[str, Any]], target: date
) -> Optional[Dict[str, Any]]:
    """Latest snapshot dated on or before `target` (snapshots must be sorted ascending by date).
    Returns None if no snapshot is that old yet — this is the expected, common case for months
    after rollout (see module docstring)."""
    best = None
    for snap in snapshots:
        if snap["snapshot_date"] <= target:
            best = snap
        else:
            break
    return best


def backtest_stock_from_snapshots(
    symbol: str,
    snapshots: List[Dict[str, Any]],
    prices: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Backtests `symbol` using real VerdictSnapshot history instead of a
    recomputed price-only proxy score.

    Args:
        symbol: Stock ticker
        snapshots: List of {snapshot_date: date, verdict: str, score: float,
                   model_version: str}, sorted ascending by snapshot_date.
                   (Pillar-level detail intentionally omitted here — the
                   caller already has the full VerdictSnapshot.pillar_scores
                   JSON if needed for future analysis.)
        prices: List of {date: date, close: float}, sorted ascending —
                same shape as backtesting.backtest_stock's `prices` arg.

    Returns:
        Same top-level shape as backtesting.backtest_stock() (status,
        historical_verdict, historical_score, current_verdict,
        current_score, eval_start_date, returns{t30/90/180/365_days},
        verdict_success_90d/365d, max_drawdown_eval) so the frontend does
        not need to change to consume this — plus additive fields
        (snapshot_verdict/snapshot_score/model_version per horizon,
        engine: "v2") that are not yet consumed by anything.
    """
    if not snapshots:
        return {
            "symbol": symbol,
            "engine": "v2",
            "status": "insufficient_data",
            "message": (
                f"No verdict snapshots recorded yet for {symbol}. A snapshot is written on every "
                "(re)ingestion — this becomes available after the next ingestion cycle, and a "
                "backtest with real forward-looking data requires waiting the full horizon "
                "afterward (30/90/180/365 days). See Phase 4 summary for the earliest realistic date."
            ),
        }

    if len(prices) < 2:
        return {
            "symbol": symbol,
            "engine": "v2",
            "status": "insufficient_data",
            "message": f"Need at least 2 price history rows to compute a return. Have {len(prices)}.",
        }

    dates = [p["date"] for p in prices]
    closes = [p["close"] for p in prices]
    as_of_date = dates[-1]
    as_of_price = closes[-1]

    results: Dict[str, Dict[str, Any]] = {}
    verdict_success: Dict[str, Optional[bool]] = {}

    for n_days in HORIZONS_DAYS:
        key = f"t{n_days}_days" if n_days != 365 else "t365_days"
        target_date = as_of_date - timedelta(days=n_days)
        snap = _closest_snapshot_on_or_before(snapshots, target_date)

        if snap is None:
            results[key] = {
                "return_pct": None,
                "benchmark_pct": _benchmark_pct(n_days),
                "outperformed": False,
                "snapshot_verdict": None,
                "snapshot_score": None,
                "snapshot_date": None,
                "model_version": None,
            }
            verdict_success[key] = None
            continue

        start_price = _price_on_or_before(dates, closes, snap["snapshot_date"])
        if start_price is None or start_price == 0:
            ret_pct = None
        else:
            ret_pct = round((as_of_price - start_price) / start_price * 100, 4)

        bench = _benchmark_pct(n_days)
        success = _verdict_success(snap["verdict"], ret_pct, bench)
        verdict_success[key] = success

        results[key] = {
            "return_pct": ret_pct,
            "benchmark_pct": bench,
            "outperformed": ret_pct is not None and ret_pct > bench,
            "snapshot_verdict": snap["verdict"],
            "snapshot_score": snap["score"],
            "snapshot_date": snap["snapshot_date"].isoformat(),
            "model_version": snap.get("model_version"),
        }

    # Headline historical_verdict/historical_score for rough shape-parity with
    # v1's single top-level value — prefer the longest horizon with data
    # (365 -> 180 -> 90 -> 30), since that's the most-tested verdict.
    headline = None
    for n_days in reversed(HORIZONS_DAYS):
        key = f"t{n_days}_days" if n_days != 365 else "t365_days"
        if results[key]["snapshot_verdict"] is not None:
            headline = results[key]
            break

    if headline is None:
        return {
            "symbol": symbol,
            "engine": "v2",
            "status": "insufficient_data",
            "message": (
                f"{symbol} has {len(snapshots)} verdict snapshot(s), but none are old enough yet "
                "for even the shortest (30-day) backtest horizon. Check back after 30 days have "
                "elapsed since the symbol's first snapshot."
            ),
        }

    # Max drawdown over the eval window: from the headline snapshot's date
    # through the latest available price — same window v1 evaluates over.
    from datetime import date as _date
    headline_date = _date.fromisoformat(headline["snapshot_date"])
    eval_window_closes = [c for d, c in zip(dates, closes) if d >= headline_date]
    max_drawdown_eval = _max_drawdown_pct(eval_window_closes)

    return {
        "symbol": symbol,
        "engine": "v2",
        "status": "completed",
        "historical_verdict": headline["snapshot_verdict"],
        "historical_score": headline["snapshot_score"],
        "current_verdict": snapshots[-1]["verdict"],
        "current_score": snapshots[-1]["score"],
        "eval_start_date": headline["snapshot_date"],
        "returns": results,
        "verdict_success_90d": verdict_success.get("t90_days"),
        "verdict_success_365d": verdict_success.get("t365_days"),
        "max_drawdown_eval": max_drawdown_eval,
    }
