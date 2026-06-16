import logging
import json
from typing import List
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

    if redis_client and results:
        try:
            redis_client.setex(cache_key, 600, json.dumps(results))
        except Exception as e:
            logger.error(f"Redis set global search failed: {e}")

    return results
