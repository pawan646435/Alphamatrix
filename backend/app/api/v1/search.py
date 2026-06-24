import logging
import json
import asyncio
import difflib
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text

from app.core.database import get_db, is_sqlite
from app.core.security import check_rate_limit
from app.models.stock import StockMaster
from app.api.v1 import funds
from app.core.config import settings
from app.services.cache_service import CacheService

router = APIRouter()
logger = logging.getLogger("app.api.v1.search")


def calculate_relevance_score(query_clean: str, item_type: str, item: dict) -> float:
    """
    Computes a relevance score where:
    Exact Symbol Match (1000) > Exact Name Match (900) > Starts-With Symbol (800)
    > Starts-With Name (700) > Word Starts-With (600) > Substring Symbol (500)
    > Substring Name (400) > Fuzzy similarity ratio (up to 200).
    """
    # Extract symbol and name
    symbol = item.get("symbol", "").strip().lower() if item_type == "stock" else ""
    name = item.get("name", "").strip().lower()
    scheme_code = str(item.get("scheme_code", "")).strip().lower()

    # Rule 1: Exact Symbol / Scheme Code Match
    if item_type == "stock" and query_clean == symbol:
        return 1000.0
    if item_type == "fund" and query_clean == scheme_code:
        return 1000.0

    # Rule 2: Exact Name Match
    if query_clean == name:
        return 900.0

    # Rule 3: Symbol / Scheme Code Starts With Match
    if item_type == "stock" and symbol.startswith(query_clean):
        # Shorter symbols matching query should be ranked higher (e.g. TCS before TCS_SPECIAL)
        return 800.0 + (1.0 / (len(symbol) or 1))
    if item_type == "fund" and scheme_code.startswith(query_clean):
        return 800.0 + (1.0 / (len(scheme_code) or 1))

    # Rule 4: Name Starts With Match
    if name.startswith(query_clean):
        return 700.0 + (1.0 / len(name))

    # Rule 5: Partial Word-Start Match inside Name (e.g., query is "consultancy" in "tata consultancy services")
    words = name.split()
    if any(w.startswith(query_clean) for w in words):
        return 600.0 + (1.0 / len(name))

    # Rule 6: General Substring Match
    if item_type == "stock" and query_clean in symbol:
        return 500.0
    if query_clean in name:
        return 400.0

    # Rule 7: Fuzzy Similarity using difflib
    r_name = difflib.SequenceMatcher(None, query_clean, name).ratio()
    r_symbol = difflib.SequenceMatcher(None, query_clean, symbol).ratio() if item_type == "stock" else 0.0
    
    # Scale fuzzy score between 0 and 200
    return max(r_name, r_symbol) * 200.0


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
        
    # Read search results from CacheService
    cached_results = await CacheService.get_search(query_clean, type)
    if cached_results is not None:
        return cached_results

    stock_results = []
    fund_results = []
    
    search_stocks = (type is None or type == "stock")
    search_funds = (type is None or type == "fund")

    if is_sqlite:
        # Construct prefix FTS5 search query
        escaped_query = query_clean.replace('"', '""')
        words = [w for w in escaped_query.split() if w]
        fts_query = " ".join([f"{w}*" for w in words]) if words else ""

        # 1. Search Stocks via SQLite FTS5
        if search_stocks and fts_query:
            try:
                stock_q = await db.execute(
                    text("""
                        SELECT s.symbol, s.company_name, m.sector
                        FROM stock_search_index s
                        JOIN stock_masters m ON s.symbol = m.symbol
                        WHERE s.stock_search_index MATCH :q
                        LIMIT 100
                    """),
                    {"q": fts_query}
                )
                for s in stock_q.all():
                    stock_results.append({
                        "type": "stock",
                        "symbol": s.symbol,
                        "name": s.company_name,
                        "sector": s.sector
                    })
            except Exception as e:
                logger.error(f"SQLite Stock FTS5 search failed: {e}")

        # 2. Search Mutual Funds via SQLite FTS5
        if search_funds and fts_query:
            try:
                fund_q = await db.execute(
                    text("""
                        SELECT scheme_code, scheme_name 
                        FROM fund_search_index 
                        WHERE fund_search_index MATCH :q
                        LIMIT 100
                    """),
                    {"q": fts_query}
                )
                for f in fund_q.all():
                    fund_results.append({
                        "type": "fund",
                        "scheme_code": int(f.scheme_code),
                        "name": f.scheme_name
                    })
            except Exception as e:
                logger.error(f"SQLite Fund FTS5 search failed: {e}")
    else:
        # PostgreSQL ILIKE search with Trigram indexes
        # 1. Search Stocks
        if search_stocks:
            try:
                q_wild = f"%{query_clean}%"
                stock_q = await db.execute(
                    text("""
                        SELECT s.symbol, s.company_name, m.sector
                        FROM stock_search_index s
                        JOIN stock_masters m ON s.symbol = m.symbol
                        WHERE s.symbol ILIKE :q OR s.company_name ILIKE :q
                        LIMIT 100
                    """),
                    {"q": q_wild}
                )
                for s in stock_q.all():
                    stock_results.append({
                        "type": "stock",
                        "symbol": s.symbol,
                        "name": s.company_name,
                        "sector": s.sector
                    })
            except Exception as e:
                logger.error(f"PostgreSQL Stock search failed: {e}")

        # 2. Search Mutual Funds
        if search_funds:
            try:
                q_wild = f"%{query_clean}%"
                fund_q = await db.execute(
                    text("""
                        SELECT scheme_code, scheme_name 
                        FROM fund_search_index 
                        WHERE scheme_code ILIKE :q OR scheme_name ILIKE :q
                        LIMIT 100
                    """),
                    {"q": q_wild}
                )
                for f in fund_q.all():
                    fund_results.append({
                        "type": "fund",
                        "scheme_code": int(f.scheme_code),
                        "name": f.scheme_name
                    })
            except Exception as e:
                logger.error(f"PostgreSQL Fund search failed: {e}")

    # Compute relevance scores and sort
    for s in stock_results:
        s["score"] = calculate_relevance_score(query_clean, "stock", s)
    stock_results.sort(key=lambda x: x["score"], reverse=True)
    stock_results_sliced = stock_results[:10]

    for f in fund_results:
        f["score"] = calculate_relevance_score(query_clean, "fund", f)
    fund_results.sort(key=lambda x: x["score"], reverse=True)
    fund_results_sliced = fund_results[:15]

    # Clean score property from final response
    for s in stock_results_sliced:
        s.pop("score", None)
    for f in fund_results_sliced:
        f.pop("score", None)

    results = stock_results_sliced + fund_results_sliced

    # 3. Dynamic ticker suggestion for stocks context
    no_stocks = not stock_results_sliced
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

    # Cache results in Redis
    await CacheService.set_search(query_clean, type, results)

    return results

