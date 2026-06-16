import logging
import json
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

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
async def global_search(query: str, db: AsyncSession = Depends(get_db)):
    """
    Unified search endpoint. Returns matches from both Stocks and Mutual Funds.
    For ticker-like queries with no local results, does a quick Yahoo Finance lookup
    and returns a 'discover' candidate so the frontend can offer auto-ingestion.
    """
    query_clean = query.strip().lower()
    if not query_clean or len(query_clean) < 2:
        return []
        
    cache_key = f"global_search:{query_clean}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Redis get global search failed: {e}")

    results = []

    # 1. Search Stocks in DB
    try:
        q_wild = f"%{query_clean}%"
        stock_q = await db.execute(
            select(StockMaster)
            .where(
                (StockMaster.symbol.ilike(q_wild)) |
                (StockMaster.company_name.ilike(q_wild))
            )
            .limit(10)
        )
        stocks = stock_q.scalars().all()
        for s in stocks:
            results.append({
                "type": "stock",
                "symbol": s.symbol,
                "name": s.company_name,
                "sector": s.sector
            })
    except Exception as e:
        logger.error(f"Stock search in global search failed: {e}")

    # 2. Search Mutual Funds in-memory
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
                    if count >= 15:  # Limit funds to top 15 matches to keep payload lightweight
                        break
    except Exception as e:
        logger.error(f"Fund search in global search failed: {e}")

    # 3. Dynamic ticker suggestion:
    #    If no stock results and query looks like a ticker, do a fast yfinance
    #    check to see if the symbol exists on NSE.  Return a 'discover' candidate.
    no_stocks = not any(r["type"] == "stock" for r in results)
    looks_like_ticker = len(query_clean) <= 15 and " " not in query_clean

    if no_stocks and looks_like_ticker:
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
                timeout=4.0  # Fast timeout so search stays snappy
            )
            if yf_result:
                results.append({
                    "type": "stock",
                    "symbol": yf_result["symbol"],
                    "name": yf_result["name"],
                    "sector": "Unknown",
                    "discover": True  # Frontend uses this flag to show a special "Discover" badge
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
