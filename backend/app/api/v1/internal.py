"""
Internal endpoints — called by QStash (not user-facing).

POST /api/v1/internal/ingest-background
  QStash-triggered endpoint that runs the full stock ingestion pipeline:
    1. quick_discover_stock  — fetch company info from yfinance, update DB record
    2. ingest_step1_history  — download 3Y price history, write StockPriceHistory
    3. ingest_step2_analytics — compute Alpha Score, CAGR, ratings
    4. ingest_step3_briefing  — generate AI equity intelligence briefing via Groq

  All four steps run in one QStash invocation (~12-14s total), well within
  Vercel's 60s maxDuration.

  Security: requests are verified using QStash JWT signature. Unsigned requests
  are rejected with 401.

  Idempotency: protected by Redis pipeline_lock:{symbol} to prevent duplicate
  runs if QStash retries.
"""
import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.redis import redis_client
from app.models.stock import StockMaster
from app.services.qstash import verify_qstash_signature

logger = logging.getLogger("app.api.v1.internal")

router = APIRouter()


class IngestRequest(BaseModel):
    symbol: str


class FundIngestRequest(BaseModel):
    scheme_code: int
    mode: str = "full"  # "full" | "ai_summary_only"


# ── Dependency: verify QStash signature ──────────────────────────────────────

async def _require_qstash_signature(
    request: Request,
    upstash_signature: Optional[str] = Header(default=None, alias="upstash-signature"),
):
    """
    FastAPI dependency that verifies the QStash webhook signature.
    Rejects the request with 401 if the signature is missing or invalid.
    Falls through (allows) if signing keys are not configured — useful for
    local dev where QStash isn't set up.
    """
    from app.services.qstash import is_qstash_configured

    if not is_qstash_configured():
        # Dev mode — no signing keys configured, allow through
        logger.warning("[Internal] QStash not configured — skipping signature check (dev mode)")
        return

    body = await request.body()
    url = str(request.url)

    if not verify_qstash_signature(upstash_signature, body, url):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing QStash signature",
        )


# ── Full pipeline endpoint ────────────────────────────────────────────────────

@router.post(
    "/ingest-background",
    dependencies=[Depends(_require_qstash_signature)],
    summary="QStash-triggered full stock ingestion pipeline",
)
async def ingest_background(
    payload: IngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Full ingestion pipeline triggered by QStash:
      discover → history → analytics → briefing

    Runs all 4 steps sequentially in ~12-14s.
    Protected by Redis lock to prevent duplicate runs on QStash retry.
    Sets Redis progress keys after each stage so /status reflects real-time progress.
    """
    symbol = payload.symbol.upper().strip()
    start_t = time.perf_counter()

    logger.info(f"[BgIngest] Starting background pipeline for {symbol}")

    # ── Redis distributed lock — prevent duplicate runs ───────────────────────
    lock_key = f"pipeline_lock:{symbol}"
    try:
        # TTL bumped from 120s to 280s to stay above the QStash publish
        # timeout (also 280s, see services/qstash.py) now that Fluid Compute
        # allows up to 300s maxDuration — previously both were tuned for the
        # pre-Fluid 60s ceiling (120s lock, 55s QStash timeout). Keeping the
        # lock TTL >= the QStash timeout avoids the lock expiring mid-run and
        # letting a QStash retry acquire a fresh lock while the original
        # invocation is still legitimately in progress.
        lock_acquired = await redis_client.set_nx(lock_key, "qstash", ex=280)
    except Exception:
        lock_acquired = True  # Fail open if Redis is down

    if not lock_acquired:
        logger.info(f"[BgIngest] {symbol} already being ingested — skipping (pipeline_lock held)")
        return {"symbol": symbol, "status": "already_running", "message": "Pipeline lock held by another instance"}

    try:
        from app.workers.stock_ingestion import (
            quick_discover_stock,
            ingest_step1_history,
            ingest_step2_analytics,
            ingest_step3_briefing,
        )

        # ── Step 0: Discover (company info, current price, sector) ───────────
        logger.info(f"[BgIngest] {symbol} step0: discover")
        discover_result = await quick_discover_stock(symbol, db)

        if discover_result.get("status") == "not_found":
            # Update stub record to FAILED so /status shows an error
            stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
            stock = stock_q.scalar_one_or_none()
            if stock:
                stock.ingestion_status = "FAILED"
                stock.sector = "Invalid"
                await db.commit()
            logger.warning(f"[BgIngest] {symbol} not found on any exchange")
            return {"symbol": symbol, "status": "not_found"}

        t0 = time.perf_counter() - start_t
        logger.info(f"[BgIngest] {symbol} discover done in {t0:.1f}s — status={discover_result.get('status')}")

        # ── Step 1: Price history ─────────────────────────────────────────────
        logger.info(f"[BgIngest] {symbol} step1: history")
        step1 = await ingest_step1_history(symbol, db)

        if step1.get("status") == "failed":
            logger.error(f"[BgIngest] {symbol} step1 failed: {step1}")
            return {"symbol": symbol, "status": "step1_failed"}

        t1 = time.perf_counter() - start_t
        logger.info(f"[BgIngest] {symbol} step1 done in {t1:.1f}s — {step1.get('price_rows')} rows")

        # ── Step 2: Analytics + Alpha Score ──────────────────────────────────
        logger.info(f"[BgIngest] {symbol} step2: analytics")
        step2 = await ingest_step2_analytics(symbol, db)

        t2 = time.perf_counter() - start_t
        logger.info(f"[BgIngest] {symbol} step2 done in {t2:.1f}s — alpha={step2.get('alpha_score')}")

        # ── Step 3: AI Briefing ───────────────────────────────────────────────
        logger.info(f"[BgIngest] {symbol} step3: briefing")
        step3 = await ingest_step3_briefing(symbol, db)

        t3 = time.perf_counter() - start_t
        logger.info(f"[BgIngest] {symbol} step3 done in {t3:.1f}s — status={step3.get('status')}")

        total = round(time.perf_counter() - start_t, 2)
        logger.info(f"[BgIngest] ✅ {symbol} READY in {total}s")

        return {
            "symbol": symbol,
            "status": "READY",
            "total_seconds": total,
            "steps": {
                "discover_s": round(t0, 2),
                "history_s": round(t1 - t0, 2),
                "analytics_s": round(t2 - t1, 2),
                "briefing_s": round(t3 - t2, 2),
            },
            "price_rows": step1.get("price_rows"),
            "alpha_score": step2.get("alpha_score"),
        }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[BgIngest] {symbol} pipeline crashed: {e}\n{tb}")
        return {"symbol": symbol, "status": "error", "error": str(e)[:500]}

    finally:
        # Always release the lock
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass


# ── Fund ingestion endpoint ───────────────────────────────────────────────────
# Mirrors the stock pipeline above: QStash calls this instead of the old
# FastAPI BackgroundTasks.add_task(...) calls in api/v1/funds.py, which did not
# reliably survive across separate Vercel serverless invocations.

@router.post(
    "/ingest-fund-background",
    dependencies=[Depends(_require_qstash_signature)],
    summary="QStash-triggered fund ingestion / AI summary regeneration",
)
async def ingest_fund_background(
    payload: FundIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Fund ingestion triggered by QStash. Two modes:
      "full"            — NAV ingest + rating recompute + AI summary
                           (mirrors the old funds.py `_ingest_and_brief`)
      "ai_summary_only" — regenerate just the AI summary

    Protected by Redis lock (fund_pipeline_lock:{scheme_code}) to prevent
    duplicate runs on QStash retry, same pattern as pipeline_lock:{symbol}.
    """
    from app.models.fund import FundMaster
    from app.workers.ingestion import ingest_fund, generate_summary_background

    scheme_code = payload.scheme_code
    mode = payload.mode
    start_t = time.perf_counter()

    logger.info(f"[BgFundIngest] Starting fund pipeline for {scheme_code} (mode={mode})")

    lock_key = f"fund_pipeline_lock:{scheme_code}"
    try:
        lock_acquired = await redis_client.set_nx(lock_key, "qstash", ex=280)
    except Exception:
        lock_acquired = True  # Fail open if Redis is down

    if not lock_acquired:
        logger.info(f"[BgFundIngest] {scheme_code} already being ingested — skipping (fund_pipeline_lock held)")
        return {"scheme_code": scheme_code, "status": "already_running", "message": "Pipeline lock held by another instance"}

    try:
        if mode == "ai_summary_only":
            await generate_summary_background(scheme_code)
        else:
            try:
                await ingest_fund(db, scheme_code, force_recompute=True)
                await generate_summary_background(scheme_code)
            except Exception as e:
                logger.error(f"[BgFundIngest] Full ingest failed for {scheme_code}: {e}")
                # Mark fund as invalid in database to prevent infinite discovery loops
                # (mirrors the old funds.py `_ingest_and_brief` except-block behavior)
                res = await db.execute(select(FundMaster).where(FundMaster.scheme_code == scheme_code))
                f = res.scalar_one_or_none()
                if f:
                    f.isin = "Invalid"
                    f.fund_name = f"Invalid Fund ({scheme_code})"
                    await db.commit()
                total = round(time.perf_counter() - start_t, 2)
                return {"scheme_code": scheme_code, "status": "error", "error": str(e)[:500], "total_seconds": total}

        total = round(time.perf_counter() - start_t, 2)
        logger.info(f"[BgFundIngest] ✅ {scheme_code} done in {total}s (mode={mode})")
        return {"scheme_code": scheme_code, "status": "READY", "mode": mode, "total_seconds": total}

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[BgFundIngest] {scheme_code} pipeline crashed: {e}\n{tb}")
        return {"scheme_code": scheme_code, "status": "error", "error": str(e)[:500]}

    finally:
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass
