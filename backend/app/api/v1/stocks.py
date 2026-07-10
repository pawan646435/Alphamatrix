import time
import traceback
from datetime import datetime
import asyncio
import logging
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Response, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, case

from app.core.database import get_db
from app.core.security import check_rate_limit, get_current_user_email
from app.models.stock import StockMaster, StockPriceHistory, WatchlistItem, VerdictSnapshot
from app.schemas.stock_schema import (
    StockGridItem, StockDetailResponse, StockMasterResponse, 
    StockPriceHistoryBase, WatchlistItemResponse, WatchlistAnalyticsResponse,
    SectorDetailsResponse, StockComparisonResponse
)
from app.schemas.ai_schema import AIChatRequest, AIChatResponse, ChatMessage

from app.core.config import settings
from app.core.redis import redis_client
from app.core.cache_ttl import (
    STOCK_SEARCH_TTL,
    STOCK_LIST_TTL,
    STOCK_MASTER_TTL,
    STOCK_HISTORY_TTL,
    AI_ANALYSIS_TTL,
    AI_COMPARISON_TTL,
    WATCHLIST_ANALYTICS_TTL,
    SECTOR_LAB_TTL,
    MARKET_REGIME_TTL,
    OPTIMIZED_METADATA_TTL,
    OPTIMIZED_CHART_TTL,
    OPTIMIZED_METRICS_TTL,
    OPTIMIZED_AI_TTL,
)

router = APIRouter()
logger = logging.getLogger("app.api.v1.stocks")

# ---------------------------------------------------------------------------
# Redis-based distributed ingestion lock
# Replaces the old in-memory `ingesting_tickers = set()` which was BROKEN on
# Vercel: each serverless invocation gets a fresh Python process, so the set
# was always empty — every 3-second poll scheduled a NEW concurrent ingestion,
# creating 10-20 simultaneous pipelines, race conditions, and infinite loading.
# ---------------------------------------------------------------------------
_INGEST_LOCK_TTL = 120   # seconds — lock auto-expires if process crashes
_INGEST_ACTIVE_KEY = "ingest_lock:{}"   # Redis key template

async def _acquire_ingest_lock(symbol: str) -> bool:
    """Atomically acquire the ingestion lock for symbol. Returns True if acquired."""
    try:
        acquired = await redis_client.set_nx(
            _INGEST_ACTIVE_KEY.format(symbol),
            "active",
            ex=_INGEST_LOCK_TTL,
        )
        return acquired
    except Exception as e:
        logger.warning(f"[Lock] Failed to acquire Redis lock for {symbol}: {e} — proceeding anyway")
        return True  # Fail open: if Redis is down, allow ingestion

async def _release_ingest_lock(symbol: str):
    """Release the ingestion lock for symbol."""
    try:
        await redis_client.delete(_INGEST_ACTIVE_KEY.format(symbol))
    except Exception as e:
        logger.warning(f"[Lock] Failed to release Redis lock for {symbol}: {e}")

async def _is_ingesting(symbol: str) -> bool:
    """Check if another Vercel instance is currently ingesting this symbol."""
    try:
        val = await redis_client.get(_INGEST_ACTIVE_KEY.format(symbol))
        return val is not None
    except Exception:
        return False  # Fail open

SECTOR_MAP = {
    "BANKING": ["Financial Services", "Banking"],
    "IT": ["IT", "Technology"],
    "AUTO": ["Auto", "Consumer Cyclical"],
    "ENERGY": ["Energy"],
    "DEFENCE": ["Defence"],
    "FMCG": ["FMCG"],
    "PHARMA": ["Pharma", "Healthcare"],
    "METALS": ["Metals", "Basic Materials"],
    "INFRASTRUCTURE": ["Infrastructure"],
    "CHEMICALS": ["Chemicals"],
    "CONSUMER_DURABLES": ["Consumer Durables"],
    "REALTY": ["Realty", "Real Estate"],
    "TELECOM": ["Telecom", "Communication Services"],
    "PSU": ["PSU"],
    "CAPITAL_GOODS": ["Capital Goods"]
}

SECTOR_LABELS = {
    "BANKING": "Banking",
    "IT": "IT",
    "AUTO": "Auto",
    "ENERGY": "Energy",
    "DEFENCE": "Defence",
    "FMCG": "FMCG",
    "PHARMA": "Pharma",
    "METALS": "Metals",
    "INFRASTRUCTURE": "Infrastructure",
    "CHEMICALS": "Chemicals",
    "CONSUMER_DURABLES": "Consumer Durables",
    "REALTY": "Realty",
    "TELECOM": "Telecom",
    "PSU": "PSU",
    "CAPITAL_GOODS": "Capital Goods"
}

def get_db_sectors_for_key(sector_key: str) -> list:
    if not sector_key:
        return []
    key_upper = sector_key.upper().strip()
    return SECTOR_MAP.get(key_upper, [sector_key])

def get_standardized_label(db_sector: str) -> str:
    if not db_sector:
        return "Unknown"
    db_clean = db_sector.strip().lower()
    for key, db_sectors in SECTOR_MAP.items():
        if any(s.lower() == db_clean for s in db_sectors):
            return SECTOR_LABELS[key]
    return db_sector


def get_alpha_breakdown(stock_obj) -> dict:
    """
    Returns a proprietary multi-factor Alpha Score breakdown based on Institutional Ratings:
    1. Fundamentals - 25%
    2. Quality - 15%
    3. Valuation - 20%
    4. Technical - 15%
    5. Risk - 15%
    6. Sector Relative - 10%
    """
    fundamental_score = getattr(stock_obj, "fundamental_score", None)
    quality_score = getattr(stock_obj, "quality_score", None)
    valuation_score = getattr(stock_obj, "valuation_score", None)
    technical_score = getattr(stock_obj, "technical_score", None)
    risk_score = getattr(stock_obj, "risk_score", None)
    sector_relative_score = getattr(stock_obj, "sector_relative_score", None)
    
    if fundamental_score is None:
        roe = stock_obj.roe if stock_obj.roe is not None else 15.0
        de = stock_obj.debt_equity if stock_obj.debt_equity is not None else 0.5
        roe_score = min(100.0, roe * 3.3)
        de_score = max(0.0, 100.0 - (de * 100.0))
        fundamental_score = 0.6 * roe_score + 0.4 * de_score
        
    if quality_score is None:
        quality_score = fundamental_score
        
    if valuation_score is None:
        pe = stock_obj.pe_ratio if stock_obj.pe_ratio is not None else 20.0
        pb = stock_obj.pb_ratio if stock_obj.pb_ratio is not None else 3.0
        pe_score = max(10.0, min(100.0, 100.0 - (pe - 12) * 2.5))
        pb_score = max(10.0, min(100.0, 100.0 - (pb - 1.5) * 10.0))
        valuation_score = 0.5 * pe_score + 0.5 * pb_score
        
    if technical_score is None:
        cagr_1y_val = stock_obj.cagr_1y if stock_obj.cagr_1y is not None else 0.0
        technical_score = max(0.0, min(100.0, cagr_1y_val * 200.0))
        
    if risk_score is None:
        beta = stock_obj.beta if stock_obj.beta is not None else 1.0
        if beta <= 0.8:
            risk_score = 95.0
        elif beta <= 1.2:
            risk_score = 80.0
        else:
            risk_score = max(20.0, 100.0 - (beta - 1.2) * 150.0)
            
    if sector_relative_score is None:
        sector_relative_score = 70.0
        
    return {
        "fundamental_score": round(fundamental_score, 1),
        "quality_score": round(quality_score, 1),
        "valuation_score": round(valuation_score, 1),
        "technical_score": round(technical_score, 1),
        "risk_score": round(risk_score, 1),
        "sector_relative_score": round(sector_relative_score, 1)
    }

class MockStock:
    def __init__(self, d):
        self.symbol = d.get("symbol")
        self.company_name = d.get("company_name")
        self.isin = d.get("isin")
        self.sector = d.get("sector")
        self.industry = d.get("industry")
        self.market_cap = d.get("market_cap")
        self.roe = d.get("roe")
        self.debt_equity = d.get("debt_equity")
        self.pe_ratio = d.get("pe_ratio")
        self.pb_ratio = d.get("pb_ratio")
        self.dividend_yield = d.get("dividend_yield")
        self.cagr_1y = d.get("cagr_1y")
        self.cagr_3y = d.get("cagr_3y")
        self.cagr_5y = d.get("cagr_5y")
        self.beta = d.get("beta")
        self.alpha_score = d.get("alpha_score")
        
        self.fundamental_score = d.get("fundamental_score")
        self.quality_score = d.get("quality_score")
        self.valuation_score = d.get("valuation_score")
        self.technical_score = d.get("technical_score")
        self.risk_score = d.get("risk_score")
        self.sector_relative_score = d.get("sector_relative_score")
        self.event_score = d.get("event_score")
        self.confidence_score = d.get("confidence_score")
        
        self.investor_verdict = d.get("investor_verdict")
        self.trader_verdict = d.get("trader_verdict")
        self.trend_structure = d.get("trend_structure")
        
        self.bull_case = d.get("bull_case")
        self.bear_case = d.get("bear_case")
        self.verdict_rationale = d.get("verdict_rationale")
        self.ai_summary = d.get("ai_summary")
        self.last_updated = d.get("last_updated")

# Redis client is imported from app.core.redis

async def generate_briefing_background(symbol: str):
    """
    Background worker task to generate the AI briefing for a stock.
    Spawns its own session to avoid sharing session across threads.
    """
    logger.info(f"Background stock briefing task started for symbol {symbol}")
    from app.core.database import async_session_maker
    
    async with async_session_maker() as session:
        # Fetch stock from DB
        stock_check = await session.execute(
            select(StockMaster).where(StockMaster.symbol == symbol)
        )
        stock = stock_check.scalar_one_or_none()
        if not stock:
            logger.warning(f"Background briefing worker could not find symbol {symbol} in DB")
            return
            
        stock_dict = {
            "symbol": stock.symbol,
            "company_name": stock.company_name,
            "sector": stock.sector,
            "industry": stock.industry,
            "market_cap": stock.market_cap,
            "pe_ratio": stock.pe_ratio,
            "pb_ratio": stock.pb_ratio,
            "roe": stock.roe,
            "debt_equity": stock.debt_equity,
            "dividend_yield": stock.dividend_yield,
            "beta": stock.beta,
            "alpha_score": stock.alpha_score,
            "cagr_1y": stock.cagr_1y,
            "cagr_3y": stock.cagr_3y,
            "cagr_5y": stock.cagr_5y
        }
        
        # Fetch live data from yfinance for prompt context
        import yfinance as yf
        news_list = []
        actions_list = []
        calendar_dict = {}
        
        try:
            yf_symbol = f"{symbol}.NS"
            logger.info(f"Fetching news/actions from yfinance for briefing: {yf_symbol}")
            import asyncio

            def _fetch_yf_briefing_data():
                """Synchronous yfinance fetch — runs in thread to avoid blocking event loop."""
                import yfinance as _yf
                _ticker = _yf.Ticker(yf_symbol)
                _news, _actions, _calendar = [], None, None
                try:
                    _news = _ticker.news or []
                except Exception:
                    pass
                try:
                    _actions = _ticker.actions
                except Exception:
                    pass
                try:
                    _calendar = _ticker.calendar
                except Exception:
                    pass
                return _news, _actions, _calendar

            raw_news_data, actions_df, calendar_raw = await asyncio.to_thread(_fetch_yf_briefing_data)

            # News extraction
            for item in (raw_news_data or [])[:5]:
                content = item.get("content", {})
                if content:
                    news_list.append({
                        "title": content.get("title"),
                        "summary": content.get("summary") or "",
                        "pubDate": content.get("pubDate") or content.get("displayTime") or "",
                        "provider": content.get("provider", {}).get("displayName") or "Unknown"
                    })

            # Actions extraction (dividends and splits)
            if actions_df is not None and not actions_df.empty:
                tail_actions = actions_df.tail(5)
                for date_val, row in tail_actions.iterrows():
                    date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)
                    if row.get("Dividends") and row["Dividends"] > 0:
                        actions_list.append({
                            "date": date_str,
                            "type": "Dividend payment",
                            "amount": f"\u20b9{row['Dividends']}"
                        })
                    if row.get("Stock Splits") and row["Stock Splits"] > 0:
                        actions_list.append({
                            "date": date_str,
                            "type": "Stock Split",
                            "amount": f"{row['Stock Splits']}:1 ratio"
                        })

            # Calendar extraction
            if calendar_raw and isinstance(calendar_raw, dict):
                ex_div = calendar_raw.get("Ex-Dividend Date")
                earn_date = calendar_raw.get("Earnings Date")
                calendar_dict = {
                    "ex_dividend_date": ex_div.strftime("%Y-%m-%d") if hasattr(ex_div, "strftime") else str(ex_div or "N/A"),
                    "earnings_date": earn_date[0].strftime("%Y-%m-%d") if (isinstance(earn_date, list) and len(earn_date) > 0 and hasattr(earn_date[0], "strftime")) else str(earn_date or "N/A")
                }
        except Exception as yf_err:
            logger.warning(f"Failed to fetch live yfinance data for briefing {symbol}: {yf_err}")
        
        try:
            from app.services.ai_agent import generate_stock_briefing
            briefing_result = await generate_stock_briefing(
                stock_dict,
                news_list=news_list,
                actions_list=actions_list,
                calendar_dict=calendar_dict
            )
            briefing = briefing_result.get("text") if isinstance(briefing_result, dict) else briefing_result
            from app.workers.stock_ingestion import parse_briefing_sections
            bull_case, bear_case, verdict_rationale = parse_briefing_sections(briefing)
            stock.bull_case = bull_case
            stock.bear_case = bear_case
            stock.verdict_rationale = verdict_rationale
            stock.ai_summary = json.dumps(briefing_result) if isinstance(briefing_result, dict) else briefing
            await session.commit()
            
            # Invalidate Redis cache
            try:
                await redis_client.delete(
                    f"stock_meta_split:{symbol}",
                    f"stock_briefing_split:{symbol}",
                    f"stock_metrics_split:{symbol}",
                    f"stock_chart_split:3y:{symbol}",
                    f"stock_chart_split:5y:{symbol}",
                    f"stock_chart_split:max:{symbol}"
                )
                await redis_client.delete_pattern("stocks_list:*")
                logger.info(f"Invalidated Redis split caches for stock {symbol} after AI briefing completion")
            except Exception as cache_err:
                logger.error(f"Failed to invalidate Redis cache for stock {symbol}: {cache_err}")
            logger.info(f"Background AI briefing generated successfully for stock {symbol}")
        except Exception as e:
            logger.error(f"Error in background briefing task for stock {symbol}: {e}")

@router.get("/search", dependencies=[Depends(check_rate_limit)])
async def search_stocks(query: str = Query(..., min_length=1, max_length=100), db: AsyncSession = Depends(get_db)):
    """
    Search seeded stocks by symbol or company name.
    """
    import time
    start_time = time.perf_counter()
    cache_key = f"stock_search:{query.strip().lower()}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"[PERF] Search resolution for query '{query}' took {elapsed_ms:.2f}ms (Cache: HIT)")
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get search failed: {e}")

    # Query DB
    q_lower = f"%{query.strip().lower()}%"
    result = await db.execute(
        select(StockMaster)
        .where(
            (StockMaster.symbol.ilike(q_lower)) | 
            (StockMaster.company_name.ilike(q_lower))
        )
        .limit(20)
    )
    stocks = result.scalars().all()
    
    response_data = [
        {"symbol": s.symbol, "company_name": s.company_name, "sector": s.sector}
        for s in stocks
    ]
    
    try:
        await redis_client.setex(cache_key, STOCK_SEARCH_TTL, json.dumps(response_data))  # Cache search results for 10 mins
    except Exception as e:
        logger.error(f"Redis set search failed: {e}")
            
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"[PERF] Search resolution for query '{query}' took {elapsed_ms:.2f}ms (Cache: MISS)")
    return response_data

@router.get("/list", response_model=List[StockGridItem], dependencies=[Depends(check_rate_limit)])
async def get_stocks(
    sector: Optional[str] = None,
    min_cagr_3y: Optional[float] = None,
    min_roe: Optional[float] = None,
    max_debt_equity: Optional[float] = None,
    max_pe: Optional[float] = None,
    sort_by: Optional[str] = "alpha_score",
    sort_order: str = "desc",
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    response: Response = None
):
    """
    Get list of seeded stocks applying sector/financial filters.
    """
    cache_key = f"stocks_list:{sector or ''}:{min_cagr_3y or ''}:{min_roe or ''}:{max_debt_equity or ''}:{max_pe or ''}:{sort_by or ''}:{sort_order or ''}:{skip}:{limit}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            if response is not None:
                response.headers["X-Cache"] = "hit"
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get stocks list failed: {e}")

    query = select(StockMaster).where(StockMaster.sector != "Invalid")
    
    # Apply filters
    if sector:
        db_sectors = get_db_sectors_for_key(sector)
        if len(db_sectors) == 1:
            query = query.where(StockMaster.sector == db_sectors[0])
        else:
            query = query.where(StockMaster.sector.in_(db_sectors))
    if min_cagr_3y is not None:
        query = query.where(StockMaster.cagr_3y >= (min_cagr_3y / 100.0))
    if min_roe is not None:
        query = query.where(StockMaster.roe >= min_roe)
    if max_debt_equity is not None:
        query = query.where(StockMaster.debt_equity <= max_debt_equity)
    if max_pe is not None:
        query = query.where(StockMaster.pe_ratio <= max_pe)
        
    # Apply sorting with NULLS LAST (non-null values first)
    if sort_by and hasattr(StockMaster, sort_by):
        sort_attr = getattr(StockMaster, sort_by)
        nulls_expr = case((sort_attr.is_(None), 1), else_=0)
        if sort_order.lower() == "asc":
            query = query.order_by(nulls_expr, sort_attr.asc())
        else:
            query = query.order_by(nulls_expr, sort_attr.desc())
            
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    stocks = result.scalars().all()

    stocks_data = [
        {
            "symbol": s.symbol,
            "company_name": s.company_name,
            "sector": s.sector,
            "cagr_1y": s.cagr_1y,
            "cagr_3y": s.cagr_3y,
            "cagr_5y": s.cagr_5y,
            "pe_ratio": s.pe_ratio,
            "roe": s.roe,
            "alpha_score": s.alpha_score,
            "beta": s.beta
        }
        for s in stocks
    ]

    try:
        await redis_client.setex(cache_key, STOCK_LIST_TTL, json.dumps(stocks_data))
    except Exception as e:
        logger.error(f"Redis set stocks list failed: {e}")

    if response is not None:
        response.headers["X-Cache"] = "miss"

    return stocks_data

@router.get("/detail/{symbol}", response_model=StockDetailResponse, dependencies=[Depends(check_rate_limit)])
async def get_stock_detail(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    response: Response = None,
    symbol: str = Path(..., min_length=1, max_length=20),
):
    """
    Retrieve stock metadata, fundamentals, return metrics, and daily close history.
    Triggers AI research briefing in the background if not present.
    Splits caching into metadata, history, and briefings for fine-grained invalidation.
    """
    symbol = symbol.upper().strip()
    
    cached_meta = None
    cached_chart = None
    cached_metrics = None
    cached_ai = None
    
    try:
        import asyncio
        cached_meta, cached_chart, cached_metrics, cached_ai = await asyncio.gather(
            redis_client.get(f"stock:{symbol}"),
            redis_client.get(f"stock_chart:{symbol}"),
            redis_client.get(f"stock_metrics:{symbol}"),
            redis_client.get(f"stock_ai:{symbol}")
        )
    except Exception as e:
        logger.error(f"Redis get split detail failed for {symbol}: {e}")
            
    # Reconstruct from cache if all exist and briefing is not generating placeholder
    if cached_meta and cached_chart and cached_metrics and cached_ai:
        meta_dict = json.loads(cached_meta)
        metrics_dict = json.loads(cached_metrics)
        briefing_val = cached_ai
        
        # Merge metadata and metrics
        master_dict = {**meta_dict, **metrics_dict}
        master_dict["ai_summary"] = briefing_val
        master_dict["status"] = "discovering" if master_dict.get("alpha_score") is None else "ready"
        
        if briefing_val != "Generating Equity Intelligence Briefing in the background...":
            logger.info(f"Returning fully split cached stock details for {symbol}")
            return {
                "stock": master_dict,
                "price_history": json.loads(cached_chart),
                "alpha_score_breakdown": get_alpha_breakdown(MockStock(master_dict))
            }

    # Fetch stock metadata from DB
    stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = stock_q.scalar_one_or_none()

    if stock and stock.sector == "Invalid":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {symbol} not found on NSE or BSE exchanges."
        )

    is_new = False
    if not stock:
        # Create a skeleton StockMaster record immediately — include ingestion_status
        # so the new /meta pipeline knows to run quick_discover on the next call
        try:
            stock = StockMaster(
                symbol=symbol,
                company_name=f"Discovering {symbol}...",
                sector="Unknown",
                industry="Unknown",
                ai_summary="Generating Equity Intelligence Briefing in the background...",
                ingestion_status="DISCOVERING",
            )
            db.add(stock)
            await db.commit()
            await db.refresh(stock)
            is_new = True
        except Exception as e:
            await db.rollback()
            stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
            stock = stock_q.scalar_one_or_none()
            if not stock:
                raise HTTPException(status_code=500, detail="Failed to initialize stock metadata.")

    if is_new or (stock.alpha_score is None and stock.sector == "Unknown"):
        if await _acquire_ingest_lock(symbol):
            logger.info(f"Stock {symbol} is in skeleton/discovering state — scheduling background ingestion")
            async def _ingest_and_brief(sym: str):
                from app.core.database import async_session_maker
                from app.workers.stock_ingestion import dynamic_ingest_stock
                try:
                    async with async_session_maker() as ingest_session:
                        result = await dynamic_ingest_stock(sym, ingest_session)
                        if result["status"] == "ingested":
                            await generate_briefing_background(sym)
                finally:
                    await _release_ingest_lock(sym)
            background_tasks.add_task(_ingest_and_brief, symbol)

    # Trigger background AI briefing if missing
    trigger_background = False
    if stock.alpha_score is not None:
        if not stock.ai_summary or stock.ai_summary == "Generating Equity Intelligence Briefing in the background...":
            stock.ai_summary = "Generating Equity Intelligence Briefing in the background..."
            await db.commit()
            await db.refresh(stock)
            trigger_background = True
        
    prices = []
    if cached_chart:
        prices = json.loads(cached_chart)
    else:
        # Fetch historical daily prices (sorted descending)
        prices_q = await db.execute(
            select(StockPriceHistory.date, StockPriceHistory.close)
            .where(StockPriceHistory.symbol == symbol)
            .order_by(StockPriceHistory.date.desc())
        )
        prices = [{"date": row.date.isoformat(), "close": row.close} for row in prices_q.all()]
        try:
            # Cache history for 24h
            await redis_client.setex(f"stock_chart:{symbol}", OPTIMIZED_CHART_TTL, json.dumps(prices))
        except Exception as e:
            logger.error(f"Redis set history failed: {e}")
                
    meta_dict = {
        "symbol": stock.symbol,
        "company_name": stock.company_name,
        "isin": stock.isin,
        "sector": stock.sector,
        "industry": stock.industry,
        "market_cap": stock.market_cap,
    }
    metrics_dict = {
        "pe_ratio": stock.pe_ratio,
        "pb_ratio": stock.pb_ratio,
        "roe": stock.roe,
        "debt_equity": stock.debt_equity,
        "dividend_yield": stock.dividend_yield,
        "beta": stock.beta,
        "cagr_1y": stock.cagr_1y,
        "cagr_3y": stock.cagr_3y,
        "cagr_5y": stock.cagr_5y,
        "alpha_score": stock.alpha_score,
        "fundamental_score": stock.fundamental_score,
        "valuation_score": stock.valuation_score,
        "technical_score": stock.technical_score,
        "risk_score": stock.risk_score,
        "sector_relative_score": stock.sector_relative_score,
        "confidence_score": stock.confidence_score,
        "investor_verdict": stock.investor_verdict,
        "trader_verdict": stock.trader_verdict,
        "last_updated": stock.last_updated.isoformat() if stock.last_updated else None,
    }
    
    if trigger_background:
        # Delete briefing and master cache to reflect "Generating..." state
        try:
            await redis_client.delete(
                f"stock:{symbol}",
                f"stock_metrics:{symbol}",
                f"stock_ai:{symbol}"
            )
        except Exception as e:
            logger.error(f"Failed to clear Redis keys for briefing status: {e}")
        background_tasks.add_task(generate_briefing_background, symbol)
        
    # Set cache for metadata, metrics and AI briefing
    try:
        await redis_client.setex(f"stock:{symbol}", OPTIMIZED_METADATA_TTL, json.dumps(meta_dict))
        await redis_client.setex(f"stock_metrics:{symbol}", OPTIMIZED_METRICS_TTL, json.dumps(metrics_dict))
        
        # Cache briefing (TTL OPTIMIZED_AI_TTL if real, 5s if generating)
        briefing_ttl = 5 if trigger_background else OPTIMIZED_AI_TTL
        await redis_client.setex(f"stock_ai:{symbol}", briefing_ttl, stock.ai_summary or "Generating Equity Intelligence Briefing in the background...")
    except Exception as e:
        logger.error(f"Redis set split cache failed: {e}")
            
    # Return response including ai_summary
    master_response = {**meta_dict, **metrics_dict}
    master_response["ai_summary"] = stock.ai_summary
    master_response["status"] = "discovering" if stock.alpha_score is None else "ready"
    
    if (trigger_background or stock.ai_summary == "Generating Equity Intelligence Briefing in the background...") and response is not None:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        
    return {
        "stock": master_response,
        "price_history": prices,
        "alpha_score_breakdown": get_alpha_breakdown(stock)
    }

@router.get("/detail/{symbol}/meta", dependencies=[Depends(check_rate_limit)])
async def get_stock_meta_split(
    db: AsyncSession = Depends(get_db),
    symbol: str = Path(..., min_length=1, max_length=20),
    response: Response = None,
):
    """
    Progressive Discovery Pipeline v3 — Hobby-safe.

    For stocks already READY: return instantly from cache/DB (< 500ms).
    For DISCOVERED/INGESTING/ANALYTICS_RUNNING: return partial data immediately.
    For new stocks: run quick_discover_stock() inline (< 5s) and return DISCOVERED.

    The frontend drives the background pipeline by calling POST /ingest/{symbol}.
    """
    import time as _time
    t0 = _time.perf_counter()
    def _ms(): return round((_time.perf_counter() - t0) * 1000, 1)

    symbol = symbol.upper().strip()
    cache_key = f"stock_meta_split:{symbol}"

    # ── Stage 1: Redis cache (READY stocks only) ──────────────────────────────
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            logger.info(f"[META] {symbol} cache HIT ({_ms()}ms)")
            return json.loads(cached)
    except Exception as e:
        logger.error(f"[META] {symbol} cache error: {e}")

    # ── Stage 2: DB lookup ────────────────────────────────────────────────────
    stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = stock_q.scalar_one_or_none()

    # ── Stage 3: Invalid / not on any exchange ────────────────────────────────
    if stock and (stock.sector == "Invalid" or getattr(stock, "ingestion_status", None) == "FAILED"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {symbol} not found on NSE or BSE exchanges."
        )

    # ── Stage 4: Stock is READY — return and cache ───────────────────────────
    ingestion_status = getattr(stock, "ingestion_status", "READY") if stock else None
    is_ready = (
        stock is not None
        and stock.alpha_score is not None
        and stock.sector not in ("Unknown", None, "")
        and ingestion_status in ("READY", None)  # None = old row without the column
    )

    if is_ready:
        res_data = {
            "symbol": stock.symbol,
            "company_name": stock.company_name,
            "isin": stock.isin,
            "sector": stock.sector,
            "industry": stock.industry,
            "market_cap": stock.market_cap,
            "current_price": getattr(stock, "current_price", None),
            "exchange": getattr(stock, "exchange", "NSE"),
            "status": "READY",
        }
        try:
            await redis_client.setex(cache_key, 86400, json.dumps(res_data))
        except Exception:
            pass
        logger.info(f"[META] {symbol} READY ({_ms()}ms)")
        return res_data

    # ── Stage 5: Partial data available (DISCOVERED / INGESTING / ANALYTICS_RUNNING) ──
    if stock and ingestion_status in ("DISCOVERED", "INGESTING", "ANALYTICS_RUNNING"):
        partial = {
            "symbol": stock.symbol,
            "company_name": stock.company_name,
            "isin": stock.isin,
            "sector": stock.sector,
            "industry": stock.industry,
            "market_cap": stock.market_cap,
            "current_price": getattr(stock, "current_price", None),
            "exchange": getattr(stock, "exchange", "NSE"),
            "status": ingestion_status,
            "stage_message": (
                "Downloading historical price data..." if ingestion_status == "DISCOVERED" else
                "Computing analytics and Alpha Score..." if ingestion_status == "INGESTING" else
                "Generating AI Equity Intelligence Briefing..."
            ),
        }
        logger.info(f"[META] {symbol} partial ({ingestion_status}) ({_ms()}ms)")
        if response is not None:
            response.status_code = 202
        return partial

    # ── Stage 6: New stock OR legacy skeleton ────────────────────────────────
    # Path A (QStash configured): insert stub → fire QStash async → return <300ms
    # Path B (QStash not configured): synchronous quick_discover_stock fallback
    needs_discover = (
        stock is None
        or ingestion_status is None
        or ingestion_status == "DISCOVERING"
        or (stock.sector in ("Unknown", None, "") and stock.alpha_score is None)
    )
    if needs_discover:
        logger.info(f"[META] {symbol} needs discovery (status={ingestion_status})")

        # Log cold miss (non-blocking)
        if stock is None:
            try:
                await redis_client.zincrby("cold_misses", 1, symbol)
                await redis_client.expire("cold_misses", 86400 * 30)
            except Exception:
                pass

        # ── Path A: QStash async ─ return <300ms ─────────────────────────────
        from app.services.qstash import is_qstash_configured, publish_ingestion_job
        if is_qstash_configured() and ingestion_status not in ("DISCOVERING",):
            if stock is None:
                stub = StockMaster(
                    symbol=symbol,
                    company_name=f"Discovering {symbol}...",
                    sector="Unknown",
                    industry="Unknown",
                    exchange="NSE",
                    ingestion_status="DISCOVERING",
                )
                db.add(stub)
                await db.commit()
                logger.info(f"[META] {symbol} stub record created ({_ms()}ms)")
            else:
                stock.ingestion_status = "DISCOVERING"
                await db.commit()

            # Write initial progress so /status returns something immediately
            try:
                progress = json.dumps({
                    "stage": "DISCOVERING", "progress": 5,
                    "available_sections": ["meta"],
                    "pending_sections": ["chart", "metrics", "briefing", "news"],
                    "stage_message": "Fetching company information...",
                })
                await redis_client.setex(f"ingest_progress:{symbol}", 3600, progress)
            except Exception:
                pass

            # Publish QStash job — must be awaited, not fire-and-forget: Vercel
            # freezes the function as soon as the response is sent, so a
            # detached asyncio task here can be killed before it runs.
            published = await publish_ingestion_job(symbol)
            if not published:
                # QStash publish failed — fall back to synchronous discover so
                # the stock isn't left stuck in DISCOVERING forever.
                from app.workers.stock_ingestion import quick_discover_stock
                try:
                    await quick_discover_stock(symbol, db)
                except Exception as exc:
                    logger.error(f"[META] {symbol} fallback discover after QStash publish failure crashed: {exc}")
            logger.info(f"[META] {symbol} QStash job queued ({_ms()}ms)")

            if response is not None:
                response.status_code = 202
            return {
                "symbol": symbol,
                "company_name": f"Discovering {symbol}...",
                "isin": None,
                "sector": None,
                "industry": None,
                "market_cap": None,
                "current_price": None,
                "exchange": "NSE",
                "status": "DISCOVERING",
                "stage_message": "Fetching company information...",
            }

        # ── Path B: Synchronous discover (fallback without QStash) ───────────
        from app.workers.stock_ingestion import quick_discover_stock
        try:
            result = await quick_discover_stock(symbol, db)
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"[META] quick_discover_stock crashed for {symbol}: {exc}\n{tb}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={
                    "symbol": symbol,
                    "status": "error",
                    "error": str(exc),
                    "traceback": tb[-1000:],
                    "stage_message": "Discovery temporarily unavailable. Please retry.",
                }
            )

        if result.get("status") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock {symbol} not found on NSE or BSE exchanges."
            )
        if result.get("status") == "error":
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={
                    "symbol": symbol,
                    "status": "error",
                    "error": result.get("reason", "unknown"),
                    "stage_message": "Discovery failed. Please retry.",
                }
            )

        logger.info(f"[META] {symbol} sync-discovered ({_ms()}ms)")
        if response is not None:
            response.status_code = 202
        return {
            "symbol": symbol,
            "company_name": result.get("company_name", f"Discovering {symbol}..."),
            "isin": result.get("isin"),
            "sector": result.get("sector", "Unknown"),
            "industry": result.get("industry", "Unknown"),
            "market_cap": result.get("market_cap"),
            "current_price": result.get("current_price"),
            "exchange": result.get("exchange", "NSE"),
            "status": "DISCOVERED",
            "stage_message": "Downloading historical price data...",
        }

    # ── Fallback: stock exists but state is unclear — return what we have ─────
    logger.warning(f"[META] {symbol} fallback — status={ingestion_status} sector={getattr(stock,'sector',None)}")
    if response is not None:
        response.status_code = 202
    return {
        "symbol": symbol,
        "company_name": getattr(stock, "company_name", symbol),
        "isin": getattr(stock, "isin", None),
        "sector": getattr(stock, "sector", "Unknown"),
        "industry": getattr(stock, "industry", "Unknown"),
        "market_cap": getattr(stock, "market_cap", None),
        "current_price": getattr(stock, "current_price", None),
        "exchange": getattr(stock, "exchange", "NSE"),
        "status": ingestion_status or "DISCOVERED",
        "stage_message": "Resolving analytics...",
    }


@router.get("/detail/{symbol}/metrics", dependencies=[Depends(check_rate_limit)])
async def get_stock_metrics_split(
    db: AsyncSession = Depends(get_db),
    symbol: str = Path(..., min_length=1, max_length=20),
):
    """
    Split endpoint: returns only fundamental ratios, scores and alpha breakdown
    TTL: 24h (86400s)
    """
    import time
    start_time = time.perf_counter()
    symbol = symbol.upper().strip()
    cache_key = f"stock_metrics_split:{symbol}"
    
    # 1. Try Redis cache
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"[PERF] Metrics fetch for {symbol} took {elapsed_ms:.2f}ms (Cache: HIT)")
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get stock_metrics_split failed: {e}")
        
    # 2. Fetch from DB
    stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = stock_q.scalar_one_or_none()
    
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
        
    res_data = {
        "pe_ratio": stock.pe_ratio,
        "pb_ratio": stock.pb_ratio,
        "roe": stock.roe,
        "debt_equity": stock.debt_equity,
        "dividend_yield": stock.dividend_yield,
        "beta": stock.beta,
        "cagr_1y": stock.cagr_1y,
        "cagr_3y": stock.cagr_3y,
        "cagr_5y": stock.cagr_5y,
        "alpha_score": stock.alpha_score,
        "fundamental_score": stock.fundamental_score,
        "valuation_score": stock.valuation_score,
        "technical_score": stock.technical_score,
        "risk_score": stock.risk_score,
        "sector_relative_score": stock.sector_relative_score,
        "confidence_score": stock.confidence_score,
        "investor_verdict": stock.investor_verdict,
        "trader_verdict": stock.trader_verdict,
        "last_updated": stock.last_updated.isoformat() if stock.last_updated else None,
        "alpha_score_breakdown": get_alpha_breakdown(stock)
    }
    
    # 3. Cache results for 24h
    try:
        ttl = 5 if stock.alpha_score is None else 86400
        await redis_client.setex(cache_key, ttl, json.dumps(res_data))
    except Exception as e:
        logger.error(f"Redis set stock_metrics_split failed: {e}")
        
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"[PERF] Metrics fetch for {symbol} took {elapsed_ms:.2f}ms (Cache: MISS)")
    return res_data


@router.get("/detail/{symbol}/chart", dependencies=[Depends(check_rate_limit)])
async def get_stock_chart_split(
    db: AsyncSession = Depends(get_db),
    symbol: str = Path(..., min_length=1, max_length=20),
    period: str = Query("3y", min_length=1, max_length=10),
):
    """
    Split endpoint: returns only historical price series (date, close) for the requested period.
    TTL: 1h (3600s)
    """
    import time
    start_time = time.perf_counter()
    symbol = symbol.upper().strip()
    period = period.lower().strip()
    cache_key = f"stock_chart_split:{period}:{symbol}"
    
    # 1. Try Redis cache — but skip empty arrays (means history not ingested yet)
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            parsed = json.loads(cached)
            if isinstance(parsed, list) and len(parsed) > 0:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"[PERF] Historical data fetch for {symbol} ({period}) took {elapsed_ms:.2f}ms (Cache: HIT)")
                return parsed
            elif isinstance(parsed, list) and len(parsed) == 0:
                # Empty cache — delete and re-fetch (ingestion may have completed since)
                await redis_client.delete(cache_key)
                logger.info(f"[Chart] Stale empty cache for {symbol}/{period} — deleting and re-fetching")
    except Exception as e:
        logger.error(f"Redis get stock_chart_split failed for {symbol}:{period}: {e}")
        
    prices = []
    
    # 2. Fetch from DB if 3y, else fetch from yfinance
    if period in ("3y", "3years"):
        prices_q = await db.execute(
            select(StockPriceHistory.date, StockPriceHistory.close)
            .where(StockPriceHistory.symbol == symbol)
            .order_by(StockPriceHistory.date.desc())
        )
        prices = [{"date": row.date.isoformat(), "close": row.close} for row in prices_q.all()]
    else:
        # Fetch dynamically from yfinance for 5y / max
        import yfinance as yf
        import pandas as pd
        import requests
        import asyncio
        
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        class TimeoutHTTPAdapter(requests.adapters.HTTPAdapter):
            def __init__(self, timeout_val=3.0, *args, **kwargs):
                self.timeout_val = timeout_val
                super().__init__(*args, **kwargs)
            def send(self, request, **kwargs):
                kwargs['timeout'] = self.timeout_val
                return super().send(request, **kwargs)
        adapter = TimeoutHTTPAdapter(timeout_val=4.0)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        try:
            yf_symbol = f"{symbol}.NS"
            ticker = yf.Ticker(yf_symbol, session=session)
            
            def fetch_history():
                p_val = "5y" if period == "5y" else "max"
                return ticker.history(period=p_val)
                
            hist = await asyncio.to_thread(fetch_history)
            if hist.empty and period == "5y":
                # BO fallback
                ticker_bo = yf.Ticker(f"{symbol}.BO", session=session)
                hist = await asyncio.to_thread(lambda: ticker_bo.history(period="5y"))
                
            if not hist.empty:
                prices = []
                for timestamp, row in hist.iterrows():
                    import numpy as np
                    close_val = float(row["Close"])
                    if not np.isnan(close_val):
                        prices.append({"date": timestamp.date().isoformat(), "close": round(close_val, 2)})
                prices.sort(key=lambda x: x["date"], reverse=True)
        except Exception as e:
            logger.error(f"yfinance dynamic historical fetch failed for {symbol} ({period}): {e}")
            
    # 3. Cache results for 1h (3600 seconds)
    try:
        await redis_client.setex(cache_key, 3600, json.dumps(prices))
    except Exception as e:
        logger.error(f"Redis set stock_chart_split failed: {e}")
        
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"[PERF] Historical data fetch for {symbol} ({period}) took {elapsed_ms:.2f}ms (Cache: MISS)")
    return prices


@router.get("/detail/{symbol}/briefing", dependencies=[Depends(check_rate_limit)])
async def get_stock_briefing_split(
    db: AsyncSession = Depends(get_db),
    symbol: str = Path(..., min_length=1, max_length=20),
):
    """
    Split endpoint: returns only AI summary/briefing sections.
    Generates AI briefing SYNCHRONOUSLY (not as background task — Vercel kills background tasks).
    Uses asyncio.wait_for with a 7s timeout to stay within Vercel's 10s limit.
    """
    import time
    start_time = time.perf_counter()
    symbol = symbol.upper().strip()
    cache_key = f"stock_briefing_split:{symbol}"

    # Placeholder strings that mean briefing is not yet generated
    PLACEHOLDER_STRINGS = {
        "Generating Equity Intelligence Briefing in the background...",
        "Analytics are being computed...",
        "AI briefing not yet generated.",
        "",
    }

    # 1. Try Redis cache — skip if it's a placeholder
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            parsed = json.loads(cached)
            ai_text = parsed.get("ai_summary", "")
            if ai_text not in PLACEHOLDER_STRINGS and len(ai_text) > 100:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"[PERF] AI briefing fetch for {symbol} took {elapsed_ms:.2f}ms (Cache: HIT)")
                return parsed
            else:
                # Stale placeholder in cache — delete and regenerate
                await redis_client.delete(cache_key)
    except Exception as e:
        logger.error(f"Redis get stock_briefing_split failed: {e}")

    # 2. Fetch from DB
    stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = stock_q.scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Check if stock has analytics (alpha_score) — briefing requires analytics
    if stock.alpha_score is None:
        res_data = {
            "ai_summary": "Analytics are still being computed. Please wait...",
            "bull_case": None,
            "bear_case": None,
            "verdict_rationale": None,
            "status": "generating"
        }
        try:
            await redis_client.setex(cache_key, 5, json.dumps(res_data))
        except Exception:
            pass
        return res_data

    current_ai = stock.ai_summary or ""
    needs_generation = current_ai in PLACEHOLDER_STRINGS or len(current_ai) < 100

    if needs_generation:
        # Generate synchronously with 7s timeout (Vercel Hobby 10s limit)
        # BackgroundTasks are killed when the request completes on Vercel.
        logger.info(f"[Briefing] Generating AI briefing for {symbol} synchronously")
        try:
            stock_dict = {
                "symbol": stock.symbol,
                "company_name": stock.company_name,
                "sector": stock.sector,
                "industry": stock.industry,
                "market_cap": stock.market_cap,
                "pe_ratio": stock.pe_ratio,
                "pb_ratio": stock.pb_ratio,
                "roe": stock.roe,
                "debt_equity": stock.debt_equity,
                "dividend_yield": stock.dividend_yield,
                "beta": stock.beta,
                "alpha_score": stock.alpha_score,
                "cagr_1y": stock.cagr_1y,
                "cagr_3y": stock.cagr_3y,
                "cagr_5y": stock.cagr_5y,
                "fundamental_score": stock.fundamental_score,
                "quality_score": stock.quality_score,
                "valuation_score": stock.valuation_score,
                "technical_score": stock.technical_score,
                "risk_score": stock.risk_score,
                "sector_relative_score": stock.sector_relative_score,
                "investor_verdict": stock.investor_verdict,
                "trader_verdict": stock.trader_verdict,
                "trend_structure": stock.trend_structure,
                "confidence_score": stock.confidence_score,
            }
            from app.services.ai_agent import generate_stock_briefing
            from app.workers.stock_ingestion import parse_briefing_sections

            # 7s timeout — leaves 3s margin for Vercel's 10s limit
            briefing_result = await asyncio.wait_for(
                generate_stock_briefing(stock_dict, news_list=[], actions_list=[], calendar_dict={}),
                timeout=7.0
            )
            briefing = briefing_result.get("text") if isinstance(briefing_result, dict) else briefing_result

            if briefing and len(briefing) > 100:
                bull_case, bear_case, verdict_rationale = parse_briefing_sections(briefing)
                stock.ai_summary = json.dumps(briefing_result) if isinstance(briefing_result, dict) else briefing
                stock.bull_case = bull_case
                stock.bear_case = bear_case
                stock.verdict_rationale = verdict_rationale
                await db.commit()
                await db.refresh(stock)
                logger.info(f"[Briefing] Generated and saved briefing for {symbol} ({len(briefing)} chars)")
            else:
                logger.warning(f"[Briefing] Briefing too short for {symbol}: {len(briefing) if briefing else 0} chars")

        except asyncio.TimeoutError:
            logger.warning(f"[Briefing] Timed out generating briefing for {symbol} — will retry on next poll")
        except Exception as gen_err:
            logger.error(f"[Briefing] Generation failed for {symbol}: {gen_err}")

    # Re-read from DB after potential generation
    await db.refresh(stock)
    current_ai = stock.ai_summary or ""
    is_ready = current_ai not in PLACEHOLDER_STRINGS and len(current_ai) > 100

    res_data = {
        "ai_summary": current_ai if is_ready else "Generating AI Equity Briefing — polling in 3s...",
        "bull_case": stock.bull_case if is_ready else None,
        "bear_case": stock.bear_case if is_ready else None,
        "verdict_rationale": stock.verdict_rationale if is_ready else None,
        "status": "completed" if is_ready else "generating"
    }

    # Cache: 5s TTL if still generating (so frontend re-polls quickly), 24h if done
    try:
        ttl = 86400 if is_ready else 5
        await redis_client.setex(cache_key, ttl, json.dumps(res_data))
    except Exception as e:
        logger.error(f"Redis set stock_briefing_split failed: {e}")

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"[PERF] AI briefing for {symbol}: {elapsed_ms:.0f}ms (ready={is_ready})")
    return res_data


@router.get("/detail/{symbol}/news", dependencies=[Depends(check_rate_limit)])
async def get_stock_news_split(
    symbol: str = Path(..., min_length=1, max_length=20),
):
    """
    Split endpoint: returns recent news for the stock from yfinance
    TTL: 15 min (900s)
    """
    import time
    start_time = time.perf_counter()
    symbol = symbol.upper().strip()
    cache_key = f"stock_news_split:{symbol}"
    
    # 1. Try Redis cache
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"[PERF] News fetch for {symbol} took {elapsed_ms:.2f}ms (Cache: HIT)")
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get stock_news_split failed: {e}")
        
    # 2. Fetch from yfinance
    import yfinance as yf
    import asyncio
    news_list = []
    
    try:
        yf_symbol = f"{symbol}.NS"
        ticker = yf.Ticker(yf_symbol)
        
        def fetch_news():
            return ticker.news or []
            
        raw_news = await asyncio.to_thread(fetch_news)
        if raw_news:
            for item in raw_news[:5]:
                content = item.get("content", {})
                if content:
                    news_list.append({
                        "title": content.get("title"),
                        "summary": content.get("summary") or "",
                        "pubDate": content.get("pubDate") or content.get("displayTime") or "",
                        "provider": content.get("provider", {}).get("displayName") or "Unknown"
                    })
    except Exception as e:
        logger.warning(f"Failed to fetch live yfinance news for {symbol}: {e}")
        
    # 3. Cache results for 15 min (900 seconds)
    try:
        await redis_client.setex(cache_key, 900, json.dumps(news_list))
    except Exception as e:
        logger.error(f"Redis set stock_news_split failed: {e}")
        
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"[PERF] News fetch for {symbol} took {elapsed_ms:.2f}ms (Cache: MISS)")
    return news_list


@router.post("/chat", response_model=AIChatResponse, dependencies=[Depends(check_rate_limit)])
async def ai_stock_chat(payload: AIChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Chat with the AI Analyst specifically configured for equities and stocks.
    """
    stock_dict = None
    sources = []
    
    if payload.scheme_code: # We will use scheme_code field in the request payload to pass stock ID/symbol for convenience
        symbol = str(payload.scheme_code).upper().strip() # Or pass symbol
    else:
        symbol = None
        
    # Let's inspect the message query to see if a symbol is mentioned
    if not symbol:
        for word in payload.message.split():
            clean_word = word.replace("$", "").upper().strip()
            # Check if this matches a seeded symbol
            q = await db.execute(select(StockMaster.symbol).where(StockMaster.symbol == clean_word))
            if q.scalar_one_or_none():
                symbol = clean_word
                break

    if symbol:
        stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
        stock = stock_q.scalar_one_or_none()
        if stock:
            stock_dict = {
                "symbol": stock.symbol,
                "company_name": stock.company_name,
                "sector": stock.sector,
                "market_cap": stock.market_cap,
                "pe_ratio": stock.pe_ratio,
                "pb_ratio": stock.pb_ratio,
                "roe": stock.roe,
                "debt_equity": stock.debt_equity,
                "dividend_yield": stock.dividend_yield,
                "beta": stock.beta,
                "alpha_score": stock.alpha_score,
                "cagr_1y": stock.cagr_1y,
                "cagr_3y": stock.cagr_3y,
                "cagr_5y": stock.cagr_5y
            }
            sources.append(stock.company_name)
            
    try:
        from app.services.ai_agent import run_stock_chat
        ai_response = await run_stock_chat(payload.message, payload.history, stock_dict)
        return {
            "response": ai_response,
            "scheme_code": 0, # Return placeholder integer
            "sources": sources
        }
    except Exception as e:
        logger.error(f"Stock AI Chat failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stock chat analysis failed: {str(e)}"
        )

# Watchlist Management Endpoints

@router.get("/watchlist", response_model=List[StockGridItem])
async def get_watchlist(email: str = Depends(get_current_user_email), db: AsyncSession = Depends(get_db)):
    """
    Get user saved watchlisted stocks.
    """
    query = (
        select(StockMaster)
        .join(WatchlistItem, WatchlistItem.symbol == StockMaster.symbol)
        .where(WatchlistItem.email == email)
    )
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/watchlist")
async def add_to_watchlist(symbol: str = Query(..., min_length=1, max_length=20), email: str = Depends(get_current_user_email), db: AsyncSession = Depends(get_db)):
    """
    Add a stock symbol to user's watchlist.
    """
    symbol = symbol.upper().strip()
    # Check if stock exists
    check_stock = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = check_stock.scalar_one_or_none()
    if not stock or stock.sector == "Invalid":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {symbol} does not exist in our index."
        )
        
    # Check if already added
    check_item = await db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.email == email)
        .where(WatchlistItem.symbol == symbol)
    )
    if check_item.scalar_one_or_none():
        return {"status": "already_added", "message": f"{symbol} is already in your watchlist."}
        
    new_item = WatchlistItem(email=email, symbol=symbol)
    db.add(new_item)
    await db.commit()
    
    # Invalidate watchlist analytics cache
    try:
        await redis_client.delete(f"watchlist_analytics:{email}")
    except Exception as e:
        logger.error(f"Failed to clear watchlist cache: {e}")
            
    return {"status": "success", "message": f"Successfully added {symbol} to watchlist."}

@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str = Path(..., min_length=1, max_length=20), email: str = Depends(get_current_user_email), db: AsyncSession = Depends(get_db)):
    """
    Remove stock symbol from user's watchlist.
    """
    symbol = symbol.upper().strip()
    
    # Check if item exists
    check_item = await db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.email == email)
        .where(WatchlistItem.symbol == symbol)
    )
    item = check_item.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol} is not present in your watchlist."
        )
        
    await db.delete(item)
    await db.commit()
    
    # Invalidate cache
    try:
        await redis_client.delete(f"watchlist_analytics:{email}")
    except Exception as e:
        logger.error(f"Failed to clear watchlist cache: {e}")
            
    return {"status": "success", "message": f"Successfully removed {symbol} from watchlist."}

@router.get("/watchlist/analytics", response_model=WatchlistAnalyticsResponse, dependencies=[Depends(check_rate_limit)])
async def get_watchlist_diagnostics(email: str = Depends(get_current_user_email), db: AsyncSession = Depends(get_db)):
    """
    Analyze watchlist stocks and return portfolio diagnostics.
    """
    cache_key = f"watchlist_analytics:{email}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get diagnostics failed: {e}")

    # Fetch all stocks in watchlist
    query = (
        select(StockMaster)
        .join(WatchlistItem, WatchlistItem.symbol == StockMaster.symbol)
        .where(WatchlistItem.email == email)
    )
    result = await db.execute(query)
    stocks = result.scalars().all()
    
    if not stocks:
        return {
            "health_score": 0.0,
            "ai_summary": "Your watchlist is empty. Add stocks to compile diagnostics.",
            "strongest_position": "None",
            "weakest_position": "None",
            "risk_concentration": "None",
            "sector_exposure": "None"
        }
        
    # Serialize stocks for AI consumption
    stocks_list = []
    for s in stocks:
        stocks_list.append({
            "symbol": s.symbol,
            "company_name": s.company_name,
            "sector": s.sector,
            "pe_ratio": s.pe_ratio,
            "roe": s.roe,
            "debt_equity": s.debt_equity,
            "beta": s.beta,
            "alpha_score": s.alpha_score,
            "cagr_1y": s.cagr_1y,
            "cagr_3y": s.cagr_3y
        })
        
    from app.services.ai_agent import generate_watchlist_analytics
    diagnostics = await generate_watchlist_analytics(stocks_list)
    
    try:
        await redis_client.setex(cache_key, WATCHLIST_ANALYTICS_TTL, json.dumps(diagnostics))  # Cache diagnostics for 30 mins
    except Exception as e:
        logger.error(f"Redis set diagnostics failed: {e}")
            
    return diagnostics

# Sector Lab Outlook Endpoints

@router.get("/sector/{sector}", response_model=SectorDetailsResponse, dependencies=[Depends(check_rate_limit)])
async def get_sector_lab(sector: str = Path(..., min_length=1, max_length=30), db: AsyncSession = Depends(get_db)):
    """
    Get sector details, score, drivers, risks, top companies, and AI sector outlook.
    """
    sector_key = sector.upper().strip()
    if sector_key not in SECTOR_MAP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sector '{sector}' has no seeded companies in our store."
        )
    sector_label = SECTOR_LABELS.get(sector_key, sector)
    cache_key = f"sector_details:{sector_key.lower()}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get sector failed: {e}")

    # Query all seeded stocks in this sector
    db_sectors = get_db_sectors_for_key(sector_key)
    from sqlalchemy import func
    db_sectors_lower = [s.lower() for s in db_sectors]
    query = select(StockMaster).where(func.lower(StockMaster.sector).in_(db_sectors_lower))
    query = query.where(StockMaster.sector != "Invalid")

    result = await db.execute(query.order_by(StockMaster.alpha_score.desc()))
    stocks = result.scalars().all()
    
    if not stocks:
        return {
            "sector": sector_label,
            "sector_score": 0.0,
            "growth_drivers": ["No growth drivers available yet."],
            "major_risks": ["No risk assessment available yet."],
            "top_stocks": [],
            "ai_outlook": "No companies available yet for this sector."
        }
        
    stocks_list = []
    for s in stocks:
        stocks_list.append({
            "symbol": s.symbol,
            "company_name": s.company_name,
            "sector": s.sector,
            "pe_ratio": s.pe_ratio,
            "roe": s.roe,
            "debt_equity": s.debt_equity,
            "alpha_score": s.alpha_score,
            "cagr_1y": s.cagr_1y,
            "cagr_3y": s.cagr_3y
        })
        
    from app.services.ai_agent import generate_sector_outlook
    outlook = await generate_sector_outlook(sector_label, stocks_list)
    
    # Format response mapping top stocks
    response_data = {
        "sector": sector_label,
        "sector_score": outlook.get("sector_score", 70.0),
        "growth_drivers": outlook.get("growth_drivers", []),
        "major_risks": outlook.get("major_risks", []),
        "top_stocks": stocks_list, # Return serializable dictionaries matching StockGridItem
        "ai_outlook": outlook.get("ai_outlook", "")
    }
    
    try:
        await redis_client.setex(cache_key, SECTOR_LAB_TTL, json.dumps(response_data, default=str))  # Cache for 24 hours
    except Exception as e:
        logger.error(f"Redis set sector failed: {e}")
            
    return response_data

@router.get("/compare", response_model=StockComparisonResponse, dependencies=[Depends(check_rate_limit)])
async def compare_stocks(
    s1: str = Query(..., min_length=1, max_length=20),
    s2: str = Query(..., min_length=1, max_length=20),
    db: AsyncSession = Depends(get_db)
):
    """
    Compare side-by-side returns, valuation, risk metrics, and AI verdict for two equities.
    """
    s1 = s1.upper().strip()
    s2 = s2.upper().strip()
    
    # Fetch stocks
    s1_q = await db.execute(select(StockMaster).where(StockMaster.symbol == s1))
    stock1 = s1_q.scalar_one_or_none()
    
    s2_q = await db.execute(select(StockMaster).where(StockMaster.symbol == s2))
    stock2 = s2_q.scalar_one_or_none()
    
    if not stock1 or stock1.sector == "Invalid" or not stock2 or stock2.sector == "Invalid":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"One or both symbols ({s1}, {s2}) not found in database."
        )
        
    # Fetch price histories
    p1_q = await db.execute(
        select(StockPriceHistory.date, StockPriceHistory.close)
        .where(StockPriceHistory.symbol == s1)
        .order_by(StockPriceHistory.date.desc())
    )
    prices1 = [{"date": row.date.isoformat(), "close": row.close} for row in p1_q.all()]
    
    p2_q = await db.execute(
        select(StockPriceHistory.date, StockPriceHistory.close)
        .where(StockPriceHistory.symbol == s2)
        .order_by(StockPriceHistory.date.desc())
    )
    prices2 = [{"date": row.date.isoformat(), "close": row.close} for row in p2_q.all()]
    
    # Check cache for comparison verdict
    cache_key = f"stock_compare_verdict:{s1}:{s2}"
    comparison_verdict = None
    if redis_client:
        try:
            comparison_verdict = await redis_client.get(cache_key)
        except Exception as e:
            logger.error(f"Redis get comparison verdict failed: {e}")
            
    if not comparison_verdict:
        s1_dict = {
            "symbol": stock1.symbol,
            "company_name": stock1.company_name,
            "sector": stock1.sector,
            "market_cap": stock1.market_cap,
            "pe_ratio": stock1.pe_ratio,
            "pb_ratio": stock1.pb_ratio,
            "roe": stock1.roe,
            "debt_equity": stock1.debt_equity,
            "beta": stock1.beta,
            "alpha_score": stock1.alpha_score,
            "cagr_1y": stock1.cagr_1y,
            "cagr_3y": stock1.cagr_3y
        }
        s2_dict = {
            "symbol": stock2.symbol,
            "company_name": stock2.company_name,
            "sector": stock2.sector,
            "market_cap": stock2.market_cap,
            "pe_ratio": stock2.pe_ratio,
            "pb_ratio": stock2.pb_ratio,
            "roe": stock2.roe,
            "debt_equity": stock2.debt_equity,
            "beta": stock2.beta,
            "alpha_score": stock2.alpha_score,
            "cagr_1y": stock2.cagr_1y,
            "cagr_3y": stock2.cagr_3y
        }
        from app.services.ai_agent import generate_stock_comparison
        comparison_verdict = await generate_stock_comparison(s1_dict, s2_dict)
        if redis_client:
            try:
                await redis_client.setex(cache_key, AI_COMPARISON_TTL, comparison_verdict)
            except Exception as e:
                logger.error(f"Redis set comparison verdict failed: {e}")
                
    return {
        "stock1": stock1,
        "stock2": stock2,
        "comparison_verdict": comparison_verdict,
        "price_history1": prices1,
        "price_history2": prices2,
        "alpha_score_breakdown1": get_alpha_breakdown(stock1),
        "alpha_score_breakdown2": get_alpha_breakdown(stock2)
    }

from pydantic import BaseModel

class MarketRegimeResponse(BaseModel):
    regime: str
    confidence: float
    explanation: str

@router.get("/market-regime", response_model=MarketRegimeResponse, dependencies=[Depends(check_rate_limit)])
async def get_market_regime():
    """
    Retrieves the macro AI market regime diagnosis, cached for 24 hours.
    """
    cache_key = "market_regime_analytics"
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.info("Returning cached market regime diagnostics")
                return json.loads(cached)
           
        except Exception as e:
            logger.error(f"Redis get market regime failed: {e}")

    from app.services.ai_agent import get_market_regime_diagnostics
    diagnostics = await get_market_regime_diagnostics()

    if redis_client:
        try:
            await redis_client.setex(cache_key, MARKET_REGIME_TTL, json.dumps(diagnostics))
        except Exception as e:
            logger.error(f"Redis set market regime failed: {e}")

    return diagnostics


@router.get("/status/{symbol}", dependencies=[Depends(check_rate_limit)])
async def get_stock_status(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Progressive discovery status endpoint.
    Returns current ingestion state, progress %, available_sections list,
    and partial stock data (company_name, current_price, sector) even
    while analytics are still computing.
    """
    import json
    symbol = symbol.upper().strip()

    stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = stock_q.scalar_one_or_none()

    if not stock:
        return {
            "status": "NOT_FOUND",
            "symbol": symbol,
            "available_sections": [],
            "pending_sections": ["meta", "chart", "metrics", "briefing", "news"],
            "progress": 0,
            "stage_message": "Stock not yet discovered.",
        }

    if stock.sector == "Invalid" or getattr(stock, "ingestion_status", None) == "FAILED":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {symbol} not found on NSE or BSE exchanges."
        )

    ingestion_status = getattr(stock, "ingestion_status", None) or "READY"

    # Read progress from Redis (written by each step function)
    available_sections = ["meta"]
    pending_sections = ["chart", "metrics", "briefing", "news"]
    progress_pct = 10
    stage_message = "Discovery in progress..."

    try:
        prog_raw = await redis_client.get(f"ingest_progress:{symbol}")
        if prog_raw:
            prog = json.loads(prog_raw)
            available_sections = prog.get("available_sections", available_sections)
            pending_sections = prog.get("pending_sections", pending_sections)
            progress_pct = prog.get("progress", progress_pct)
            stage_message = prog.get("stage_message", stage_message)
    except Exception:
        pass

    # For READY stocks without Redis progress entry, return full sections
    if ingestion_status == "READY" or (
        stock.alpha_score is not None and stock.sector not in ("Unknown", None, "")
    ):
        ingestion_status = "READY"
        available_sections = ["meta", "chart", "metrics", "briefing", "news"]
        pending_sections = []
        progress_pct = 100
        stage_message = "All analytics ready."

    return {
        "symbol": symbol,
        "status": ingestion_status,
        "company_name": stock.company_name,
        "isin": stock.isin,
        "sector": stock.sector,
        "industry": stock.industry,
        "market_cap": stock.market_cap,
        "current_price": getattr(stock, "current_price", None),
        "exchange": getattr(stock, "exchange", "NSE"),
        "alpha_score": stock.alpha_score,
        "available_sections": available_sections,
        "pending_sections": pending_sections,
        "progress": progress_pct,
        "stage_message": stage_message,
    }


@router.post("/ingest/{symbol}", dependencies=[Depends(check_rate_limit)])
async def advance_ingestion_pipeline(
    symbol: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Frontend-driven pipeline advancement — QStash-not-configured fallback
    (e.g. Vercel Hobby without QSTASH_TOKEN set).

    Runs ALL remaining pipeline steps from the stock's current
    ingestion_status through to READY in a single invocation:
      DISCOVERED        → step1_history → step2_analytics → step3_briefing → READY
      INGESTING         → step2_analytics → step3_briefing → READY
      ANALYTICS_RUNNING → step3_briefing → READY
      READY             → no-op, return immediately

    Previously this advanced exactly one step per call (bounded to fit
    Vercel's pre-Fluid ~10s Hobby limit), requiring up to 3 separate
    frontend polling round-trips to reach READY. With Fluid Compute enabled
    (maxDuration up to 300s on Hobby — see backend/vercel.json), running the
    full remaining chain in one call is safely within budget (~15-25s worst
    case for all three steps) and meaningfully cuts time-to-READY. This does
    NOT change the frontend contract: /status and this endpoint's response
    shape are unchanged, and the frontend's poll-then-call-if-not-READY loop
    works identically whether it takes 1 or 3 round-trips to resolve — it
    will just observe fewer, larger jumps in ingestion_status.

    Stops early (without raising) if any step reports "failed"/"error", so a
    mid-chain failure doesn't cascade into calling the next stage on bad data.
    Redis lock is held for the whole multi-step run, not released between
    steps, so a duplicate concurrent call can't interleave with a run in progress.
    """
    symbol = symbol.upper().strip()

    stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = stock_q.scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=404, detail=f"{symbol} not found. Call /meta first.")

    if stock.sector == "Invalid" or getattr(stock, "ingestion_status", None) == "FAILED":
        raise HTTPException(status_code=404, detail=f"{symbol} is invalid (not on NSE/BSE).")

    ingestion_status = getattr(stock, "ingestion_status", "READY")

    if ingestion_status == "READY":
        return {"symbol": symbol, "status": "READY", "message": "Already fully ingested."}

    # Check Redis lock — prevent duplicate concurrent pipeline runs.
    # TTL bumped from 60s to 90s to cover the full multi-step chain (up to
    # ~25s worst case) with headroom, rather than just a single step.
    lock_key = f"pipeline_lock:{symbol}"
    try:
        lock_acquired = await redis_client.set_nx(lock_key, "1", ex=90)
    except Exception:
        lock_acquired = True  # Proceed if Redis is unavailable

    if not lock_acquired:
        return {
            "symbol": symbol,
            "status": ingestion_status,
            "message": "Pipeline step already in progress. Poll /status for updates."
        }

    try:
        from app.workers.stock_ingestion import (
            ingest_step1_history, ingest_step2_analytics, ingest_step3_briefing
        )
        from app.core.database import async_session_maker

        STEP_CHAIN = {
            "DISCOVERED": (ingest_step1_history, ingest_step2_analytics, ingest_step3_briefing),
            "INGESTING": (ingest_step2_analytics, ingest_step3_briefing),
            "ANALYTICS_RUNNING": (ingest_step3_briefing,),
        }
        steps_to_run = STEP_CHAIN.get(ingestion_status, ())
        result = {"status": ingestion_status, "message": "Unknown state"}

        async with async_session_maker() as step_db:
            for step_fn in steps_to_run:
                result = await step_fn(symbol, step_db)
                # Stop early on failure — don't cascade into the next stage on bad data.
                if result.get("status") in ("failed", "error"):
                    break

        return {"symbol": symbol, **result}

    except Exception as exc:
        logger.error(f"[IngestEndpoint] {symbol} pipeline step failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Pipeline step failed: {str(exc)[:200]}")
    finally:
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass


@router.post("/admin/prewarm", dependencies=[Depends(check_rate_limit)])
async def prewarm_nifty50(db: AsyncSession = Depends(get_db)):
    """
    Prewarm common stocks (NIFTY 50 + NIFTY NEXT 50).
    Triggers quick_discover for any stocks not yet in DB or marked stale (> 24h).
    Call daily via Vercel cron or external scheduler.
    """
    from datetime import datetime, timedelta
    from app.workers.stock_ingestion import quick_discover_stock

    NIFTY50 = [
        "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR",
        "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", "MARUTI",
        "HCLTECH", "SUNPHARMA", "TITAN", "WIPRO", "NESTLEIND", "POWERGRID",
        "ULTRACEMCO", "NTPC", "BAJAJFINSV", "ONGC", "HDFCLIFE", "TATASTEEL",
        "M&M", "JSWSTEEL", "ADANIENT", "SBILIFE", "CIPLA", "DRREDDY",
        "COALINDIA", "TATAMOTORS", "INDUSINDBK", "APOLLOHOSP", "ASIANPAINT",
        "EICHERMOT", "GRASIM", "HEROMOTOCO", "HINDALCO", "BPCL",
        "BRITANNIA", "DIVISLAB", "TATACONSUM", "TECHM", "SHREECEM",
        "LTIM", "HAL", "BEL", "ADANIPORTS", "BAJAJ-AUTO",
    ]

    queued = []
    skipped = []
    stale_cutoff = datetime.utcnow() - timedelta(hours=24)

    for sym in NIFTY50:
        try:
            q = await db.execute(select(StockMaster).where(StockMaster.symbol == sym))
            existing = q.scalar_one_or_none()
            ingestion_status = getattr(existing, "ingestion_status", None)

            if existing and ingestion_status == "READY" and existing.last_updated > stale_cutoff:
                skipped.append(sym)
                continue

            # Quick discover to seed/refresh basic info
            result = await quick_discover_stock(sym, db)
            queued.append({"symbol": sym, "result": result.get("status")})
            logger.info(f"[Prewarm] {sym}: {result.get('status')}")
        except Exception as e:
            logger.error(f"[Prewarm] {sym} failed: {e}")
            queued.append({"symbol": sym, "result": "error"})

    return {
        "queued": len(queued),
        "skipped": len(skipped),
        "details": queued,
    }


# ═══════════════════════════════════════════════════════════════
# BACKTESTING ENGINE v3 ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/backtest/summary", dependencies=[Depends(check_rate_limit)])
async def get_backtest_summary(db: AsyncSession = Depends(get_db)):
    """
    Returns aggregate backtesting accuracy across all stocks in the system.
    Shows BUY/HOLD/AVOID accuracy, win rate, and benchmark comparison.
    Cached for 24 hours.
    """
    CACHE_KEY = "backtest:summary:v3"
    try:
        cached = await redis_client.get(CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get backtest summary failed: {e}")

    from app.services.backtesting import backtest_stock, aggregate_backtest_summary

    # Fetch all stocks with price history
    stocks_q = await db.execute(
        select(StockMaster.symbol, StockMaster.investor_verdict, StockMaster.alpha_score)
        .where(StockMaster.sector != "Invalid")
        .limit(50)
    )
    stocks = stocks_q.all()

    results = []
    for stock in stocks:
        symbol = stock.symbol
        prices_q = await db.execute(
            select(StockPriceHistory.date, StockPriceHistory.close)
            .where(StockPriceHistory.symbol == symbol)
            .order_by(StockPriceHistory.date.asc())
        )
        price_rows = prices_q.all()
        if len(price_rows) < 90:
            continue
        prices = [{"date": r.date, "close": r.close} for r in price_rows]
        result = backtest_stock(
            symbol=symbol,
            prices=prices,
            current_verdict=stock.investor_verdict,
            current_score=stock.alpha_score
        )
        results.append(result)

    summary = aggregate_backtest_summary(results)

    try:
        await redis_client.setex(CACHE_KEY, 86400, json.dumps(summary))  # 24hr TTL
    except Exception as e:
        logger.error(f"Redis set backtest summary failed: {e}")

    return summary


@router.get("/backtest/{symbol}", dependencies=[Depends(check_rate_limit)])
async def get_stock_backtest(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Returns per-stock backtest results: historical verdict, actual returns at
    T+30, T+90, T+180, T+365, vs NIFTY 50 benchmark.
    """
    symbol = symbol.upper().strip()
    CACHE_KEY = f"backtest:stock:{symbol}:v3"
    try:
        cached = await redis_client.get(CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get stock backtest failed for {symbol}: {e}")

    stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = stock_q.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found.")

    prices_q = await db.execute(
        select(StockPriceHistory.date, StockPriceHistory.close)
        .where(StockPriceHistory.symbol == symbol)
        .order_by(StockPriceHistory.date.asc())
    )
    price_rows = prices_q.all()
    if len(price_rows) < 90:
        raise HTTPException(status_code=422, detail=f"Insufficient price history for {symbol}. Need 90+ days.")

    from app.services.backtesting import backtest_stock
    prices = [{"date": r.date, "close": r.close} for r in price_rows]
    result = backtest_stock(
        symbol=symbol,
        prices=prices,
        current_verdict=stock.investor_verdict,
        current_score=stock.alpha_score
    )

    try:
        await redis_client.setex(CACHE_KEY, 43200, json.dumps(result))  # 12hr TTL
    except Exception as e:
        logger.error(f"Redis set stock backtest failed for {symbol}: {e}")

    return result


@router.get("/backtest-v2/{symbol}", dependencies=[Depends(check_rate_limit)])
async def get_stock_backtest_v2(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Phase 4 Track 2 — snapshot-based backtest (services/backtesting_v2.py).

    Backtests the Alpha Score model's own real past verdicts (VerdictSnapshot
    rows written on every ingestion, see workers/stock_ingestion.py) against
    actual subsequent price returns — NOT the price-only proxy model behind
    GET /backtest/{symbol} above (services/backtesting.py).

    Deliberately NOT wired into GET /backtest/summary yet: verdict_snapshots
    only starts accumulating from this feature's rollout date, so results
    here will read "insufficient_data" for most/all symbols for months. This
    route exists so it can be compared against the old engine over time
    before switching the live summary/UI over — see Phase 4 summary for the
    approximate date the first real comparison becomes possible.
    """
    symbol = symbol.upper().strip()
    CACHE_KEY = f"backtest_v2:stock:{symbol}"
    try:
        cached = await redis_client.get(CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get stock backtest-v2 failed for {symbol}: {e}")

    stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = stock_q.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found.")

    snapshots_q = await db.execute(
        select(VerdictSnapshot.snapshot_date, VerdictSnapshot.verdict, VerdictSnapshot.score, VerdictSnapshot.model_version)
        .where(VerdictSnapshot.symbol == symbol)
        .order_by(VerdictSnapshot.snapshot_date.asc())
    )
    snapshots = [
        {"snapshot_date": r.snapshot_date, "verdict": r.verdict, "score": r.score, "model_version": r.model_version}
        for r in snapshots_q.all()
    ]

    prices_q = await db.execute(
        select(StockPriceHistory.date, StockPriceHistory.close)
        .where(StockPriceHistory.symbol == symbol)
        .order_by(StockPriceHistory.date.asc())
    )
    prices = [{"date": r.date, "close": r.close} for r in prices_q.all()]

    from app.services.backtesting_v2 import backtest_stock_from_snapshots
    result = backtest_stock_from_snapshots(symbol=symbol, snapshots=snapshots, prices=prices)

    try:
        await redis_client.setex(CACHE_KEY, 43200, json.dumps(result))  # 12hr TTL — matches v1's cache lifetime
    except Exception as e:
        logger.error(f"Redis set stock backtest-v2 failed for {symbol}: {e}")

    return result


# ═══════════════════════════════════════════════════════════════
# PRE-WARM CRON + COLD-MISS ANALYTICS
# ═══════════════════════════════════════════════════════════════

# NSE Top 200 universe for daily pre-warming
_NSE_TOP_200 = [
    # Nifty 50
    "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFOSYS","SBIN",
    "HINDUNILVR","KOTAKBANK","ITC","LT","AXISBANK","ASIANPAINT","MARUTI",
    "BAJFINANCE","HCLTECH","TITAN","SUNPHARMA","WIPRO","NTPC","POWERGRID",
    "ULTRACEMCO","ADANIENT","ADANIPORTS","BAJAJFINSV","NESTLEIND","HINDALCO",
    "TATASTEEL","TECHM","COALINDIA","BPCL","DIVISLAB","ONGC","GRASIM",
    "JSWSTEEL","CIPLA","EICHERMOT","BRITANNIA","DRREDDY","SHREECEM",
    "TATACONSUM","HEROMOTOCO","APOLLOHOSP","BAJAJ-AUTO","TATAMOTORS",
    "SBILIFE","HDFCLIFE","INDUSINDBK","M&M","UPL",
    # Nifty Next 50
    "ADANIGREEN","AMBUJACEM","AUROPHARMA","BANDHANBNK","BERGEPAINT",
    "BIOCON","BOSCHLTD","COLPAL","DALBHARAT","DABUR","DLF","GAIL",
    "GODREJCP","HAVELLS","HINDPETRO","IDFCFIRSTB","INDIGO","IOC",
    "IRCTC","JINDALSTEL","LICI","LUPIN","MARICO","MUTHOOTFIN","NAUKRI",
    "NMDC","OFSS","PAGEIND","PETRONET","PIIND","PIDILITIND","PNB",
    "RECLTD","SAIL","SIEMENS","SRF","SUNTV","TORNTPHARM","TRENT",
    "TVSMOTOR","VBL","VEDL","VOLTAS","ZYDUSLIFE",
    # Popular new-age / mid-cap frequently searched
    "ZOMATO","PAYTM","NYKAA","POLICYBZR","DELHIVERY","IRFC","RVNL",
    "MAZAGON","HAL","BEL","MOTHERSON","MPHASIS","COFORGE","LTIM",
    "PERSISTENT","KPITTECH","TATAELXSI","KAYNES","APARINDS",
    "APOLLOMICRO","TITAGARH","RAILVIKAS","COCHINSHIP",
]


@router.get("/prewarm")
async def prewarm_stock_universe(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(25, ge=1, le=50, description="Max new symbols to ingest per cron run"),
):
    """
    Daily pre-warm cron endpoint — called by Vercel cron at 9:30 PM UTC (3 AM IST).
    Ingests NSE Top 200 stocks that are not yet READY in the DB.
    Runs in chunks of 3 (yfinance-rate-limit friendly), respects Vercel 60s maxDuration.
    Idempotent: skips already-READY stocks.
    """
    from app.workers.stock_ingestion import quick_discover_stock, ingest_step1_history, ingest_step2_analytics
    start_t = time.perf_counter()

    logger.info(f"[Prewarm] Starting daily pre-warm for up to {limit} symbols")

    # Find which symbols are already READY
    existing_q = await db.execute(
        select(StockMaster.symbol, StockMaster.ingestion_status, StockMaster.alpha_score)
        .where(StockMaster.symbol.in_(_NSE_TOP_200))
    )
    existing = {
        row.symbol: row.ingestion_status
        for row in existing_q.all()
    }

    # Symbols to ingest: not in DB, or not READY
    ready_statuses = {"READY"}
    to_ingest = [
        sym for sym in _NSE_TOP_200
        if sym not in existing or existing.get(sym) not in ready_statuses
    ][:limit]

    if not to_ingest:
        logger.info("[Prewarm] All pre-warm symbols already READY.")
        return {
            "status": "noop",
            "message": "All pre-warm symbols are already READY.",
            "duration_s": round(time.perf_counter() - start_t, 2),
        }

    processed, skipped_list, failed = [], [], []
    CHUNK = 3  # parallel batch size — safe for yfinance rate limits

    for i in range(0, len(to_ingest), CHUNK):
        # Stop if approaching Vercel 60s maxDuration (leave 10s buffer)
        if time.perf_counter() - start_t > 50:
            logger.warning(f"[Prewarm] Time limit approaching — stopping after {len(processed)} symbols")
            break

        chunk = to_ingest[i : i + CHUNK]

        async def _ingest_one(sym: str):
            lock_key = f"ingest_lock:{sym}"
            try:
                lock_ok = await redis_client.set_nx(lock_key, "prewarm", ex=120)
            except Exception:
                lock_ok = True

            if not lock_ok:
                return {"symbol": sym, "status": "locked"}

            try:
                # Step 0: Quick discover (basic meta + current price)
                disc = await quick_discover_stock(sym, db)
                if disc.get("status") == "not_found":
                    return {"symbol": sym, "status": "not_found"}

                # Step 1: Download price history
                step1 = await ingest_step1_history(sym, db)
                if step1.get("status") == "failed":
                    return {"symbol": sym, "status": "failed"}

                # Step 2: Compute analytics
                step2 = await ingest_step2_analytics(sym, db)
                return {"symbol": sym, "status": step2.get("status", "done")}

            except Exception as e:
                logger.error(f"[Prewarm] {sym} failed: {e}")
                return {"symbol": sym, "status": "error", "error": str(e)[:200]}
            finally:
                try:
                    await redis_client.delete(lock_key)
                except Exception:
                    pass

        results = await asyncio.gather(*[_ingest_one(s) for s in chunk], return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                failed.append(str(r)[:100])
            elif r.get("status") in ("done", "analytics_running", "ingesting", "READY"):
                processed.append(r["symbol"])
            elif r.get("status") == "not_found":
                skipped_list.append(r["symbol"])
            elif r.get("status") == "locked":
                skipped_list.append(r["symbol"])  # another instance is handling it
            else:
                failed.append(r.get("symbol", "?"))

        await asyncio.sleep(0.5)  # Rate-limit pause between chunks

    duration = round(time.perf_counter() - start_t, 2)
    logger.info(f"[Prewarm] Done — processed={len(processed)}, skipped={len(skipped_list)}, failed={len(failed)}, duration={duration}s")

    return {
        "status": "completed",
        "processed": processed,
        "skipped": skipped_list,
        "failed": failed,
        "remaining": to_ingest[limit:],
        "duration_s": duration,
    }


@router.get("/cold-misses", dependencies=[Depends(check_rate_limit)])
async def get_cold_misses():
    """
    Returns the top 50 most-searched new symbols (cold misses) with search counts.
    Used to decide which symbols to add to the pre-warm universe.
    """
    try:
        raw = await redis_client.zrevrange("cold_misses", 0, 49, withscores=True)
        return [
            {
                "symbol": (item[0].decode() if isinstance(item[0], bytes) else item[0]),
                "searches": int(item[1]),
            }
            for item in (raw or [])
        ]
    except Exception as e:
        logger.error(f"[ColdMiss] Fetch failed: {e}")
        return []


