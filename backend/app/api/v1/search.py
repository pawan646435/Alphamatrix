import logging
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text

from app.core.database import get_db
from app.core.security import check_rate_limit
from app.models.stock import StockMaster
from app.api.v1 import funds
import redis
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger("app.api.v1.search")

# Initialize Redis client if REDIS_URL is configured
redis_client = None
if settings.REDIS_URL:
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to connect to Redis for Search caching: {e}")

@router.get("", dependencies=[Depends(check_rate_limit)])
async def global_search(query: str, type: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    Unified search endpoint with context-aware isolation.
    Returns matches from Stocks or Mutual Funds based on the 'type' parameter.
    For stock searches with no local results, does a quick Yahoo Finance lookup.
    """
    query_clean = query.strip().lower()
    if not query_clean or len(query_clean) < 2:
        return []
        
    cache_key = f"global_search:{type or 'all'}:{query_clean}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Redis get global search failed: {e}")

    results = []
    
    # Construct prefix FTS5 search query
    escaped_query = query_clean.replace('"', '""')
    words = [w for w in escaped_query.split() if w]
    fts_query = " ".join([f"{w}*" for w in words]) if words else ""

    search_stocks = (type is None or type == "stock")
    search_funds = (type is None or type == "fund")

    # 1. Search Stocks
    if search_stocks and fts_query:
        try:
            # Query FTS5 index joined with stock_masters to get sector
            stock_q = await db.execute(
                text("""
                    SELECT s.symbol, s.company_name, m.sector
                    FROM stock_search_index s
                    JOIN stock_masters m ON s.symbol = m.symbol
                    WHERE s.stock_search_index MATCH :q
                    LIMIT 10
                """),
                {"q": fts_query}
            )
            stocks = stock_q.all()
            for s in stocks:
                results.append({
                    "type": "stock",
                    "symbol": s.symbol,
                    "name": s.company_name,
                    "sector": s.sector
                })
        except Exception as e:
            logger.error(f"Stock FTS5 search failed, falling back: {e}")
            # Fallback to standard LIKE
            try:
                q_wild = f"%{query_clean}%"
                stock_q = await db.execute(
                    select(StockMaster.symbol, StockMaster.company_name, StockMaster.sector)
                    .where(
                        (StockMaster.symbol.ilike(q_wild)) |
                        (StockMaster.company_name.ilike(q_wild))
                    )
                    .limit(10)
                )
                for s in stock_q.all():
                    results.append({
                        "type": "stock",
                        "symbol": s.symbol,
                        "name": s.company_name,
                        "sector": s.sector
                    })
            except Exception as fallback_err:
                logger.error(f"Stock search fallback failed: {fallback_err}")

    # 2. Search Mutual Funds
    if search_funds and fts_query:
        try:
            # Query FTS5 virtual table
            fund_q = await db.execute(
                text("""
                    SELECT scheme_code, scheme_name 
                    FROM fund_search_index 
                    WHERE fund_search_index MATCH :q
                    LIMIT 15
                """),
                {"q": fts_query}
            )
            funds_res = fund_q.all()
            for f in funds_res:
                results.append({
                    "type": "fund",
                    "scheme_code": int(f.scheme_code),
                    "name": f.scheme_name
                })
        except Exception as e:
            logger.error(f"Fund FTS5 search failed, falling back: {e}")
            # Fallback to in-memory cache scan
            try:
                await funds.load_master_list_if_empty()
                if funds.MF_MASTER_LIST:
                    count = 0
                    for item in funds.MF_MASTER_LIST:
                        name = item.get("schemeName", "")
                        code = str(item.get("schemeCode", ""))
                        if query_clean in name.lower() or query_clean in code:
                            results.append({
                                "type": "fund",
                                "scheme_code": item.get("schemeCode"),
                                "name": name
                            })
                            count += 1
                            if count >= 15:
                                break
            except Exception as fallback_err:
                logger.error(f"Fund search fallback failed: {fallback_err}")

    # 3. Dynamic ticker suggestion for stocks context
    #    Only run if we are in stock/all search context, have no stock matches, and query looks like a symbol
    no_stocks = not any(r["type"] == "stock" for r in results)
    looks_like_ticker = len(query_clean) <= 15 and " " not in query_clean

    if search_stocks and no_stocks and looks_like_ticker:
        ticker_upper = query_clean.upper()

        def _quick_check():
            try:
                import yfinance as yf
                t = yf.Ticker(f"{ticker_upper}.NS")
                info = t.info or {}
                name = info.get("longName") or info.get("shortName")
                if name:
                    return {"name": name, "symbol": ticker_upper}
            except Exception:
                pass
            return None

        try:
            loop = asyncio.get_event_loop()
            yf_result = await asyncio.wait_for(
                loop.run_in_executor(None, _quick_check),
                timeout=4.0
            )
            if yf_result:
                results.append({
                    "type": "stock",
                    "symbol": yf_result["symbol"],
                    "name": yf_result["name"],
                    "sector": "Unknown",
                    "discover": True
                })
        except asyncio.TimeoutError:
            logger.info(f"yfinance quick-check timed out for ticker {ticker_upper}")
        except Exception as e:
            logger.debug(f"yfinance quick-check failed for {ticker_upper}: {e}")

    if redis_client and results:
        try:
            redis_client.setex(cache_key, 600, json.dumps(results))
        except Exception as e:
            logger.error(f"Redis set global search failed: {e}")

    return results
