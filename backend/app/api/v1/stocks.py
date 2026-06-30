import logging
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Response, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, case

from app.core.database import get_db
from app.core.security import check_rate_limit, get_current_user_email
from app.models.stock import StockMaster, StockPriceHistory, WatchlistItem
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
ingesting_tickers = set()

SECTOR_MAP = {
    "BANKING": ["Financial Services", "Banking"],
    "IT": ["IT", "Technology"],
    "AUTO": ["Auto", "Consumer Cyclical"],
    "ENERGY": ["Energy"],
    "DEFENCE": ["Defence", "Industrials"],
    "FMCG": ["FMCG", "Consumer Defensive"]
}

SECTOR_LABELS = {
    "BANKING": "Banking",
    "IT": "IT",
    "AUTO": "Auto",
    "ENERGY": "Energy",
    "DEFENCE": "Defence",
    "FMCG": "FMCG"
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
    Computes a proprietary multi-factor Alpha Score breakdown based on:
    1. Fundamentals (ROE, Debt/Equity) - 30% weight
    2. Valuation (PE ratio, PB ratio) - 30% weight
    3. Momentum (1Y CAGR, Slope) - 25% weight
    4. Risk (Beta stability) - 15% weight
    5. Sentiment (Alpha-inferred)
    6. Macro (Beta-inferred)
    """
    # 1. Fundamental score
    roe = stock_obj.roe if stock_obj.roe is not None else 15.0
    de = stock_obj.debt_equity if stock_obj.debt_equity is not None else 0.5
    roe_score = min(100.0, roe * 4.0)
    de_score = max(0.0, 100.0 - (de * 100.0))
    fundamental_score = 0.6 * roe_score + 0.4 * de_score

    # 2. Valuation score
    pe = stock_obj.pe_ratio if stock_obj.pe_ratio is not None else 20.0
    pb = stock_obj.pb_ratio if stock_obj.pb_ratio is not None else 3.0
    pe_score = max(10.0, min(100.0, 100.0 - (pe - 12) * 2.5))
    pb_score = max(10.0, min(100.0, 100.0 - (pb - 1.5) * 10.0))
    valuation_score = 0.5 * pe_score + 0.5 * pb_score

    # 3. Momentum score
    cagr_1y_val = stock_obj.cagr_1y if stock_obj.cagr_1y is not None else 0.0
    cagr_3y_val = stock_obj.cagr_3y if stock_obj.cagr_3y is not None else 0.0
    mom_return_score = max(0.0, min(100.0, cagr_1y_val * 200.0))
    acceleration_bonus = 20.0 if cagr_1y_val > cagr_3y_val else 0.0
    momentum_score = min(100.0, mom_return_score + acceleration_bonus)

    # 4. Risk score
    beta = stock_obj.beta if stock_obj.beta is not None else 1.0
    if beta <= 0.8:
        risk_score = 95.0
    elif beta <= 1.2:
        risk_score = 80.0
    else:
        risk_score = max(20.0, 100.0 - (beta - 1.2) * 150.0)

    # 5. Sentiment score
    score = getattr(stock_obj, "alpha_score", 50.0)
    if score is None:
        score = 50.0
    sentiment_score = 85.0 if score >= 70.0 else 70.0 if score >= 50.0 else 45.0

    # 6. Macro score
    macro_score = 80.0 if beta <= 0.9 else 55.0 if beta > 1.2 else 70.0

    return {
        "fundamentals": round(fundamental_score, 1),
        "valuation": round(valuation_score, 1),
        "momentum": round(momentum_score, 1),
        "risk": round(risk_score, 1),
        "sentiment": round(sentiment_score, 1),
        "macro": round(macro_score, 1)
    }

class MockStock:
    def __init__(self, d):
        self.roe = d.get("roe")
        self.debt_equity = d.get("debt_equity")
        self.pe_ratio = d.get("pe_ratio")
        self.pb_ratio = d.get("pb_ratio")
        self.cagr_1y = d.get("cagr_1y")
        self.cagr_3y = d.get("cagr_3y")
        self.beta = d.get("beta")
        self.alpha_score = d.get("alpha_score", 50)

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
            ticker = yf.Ticker(yf_symbol)
            
            # News extraction
            raw_news = ticker.news
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
            
            # Actions extraction (dividends and splits)
            actions_df = ticker.actions
            if actions_df is not None and not actions_df.empty:
                # Get the last 5 corporate actions
                tail_actions = actions_df.tail(5)
                for date_val, row in tail_actions.iterrows():
                    date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)
                    if row.get("Dividends") and row["Dividends"] > 0:
                        actions_list.append({
                            "date": date_str,
                            "type": "Dividend payment",
                            "amount": f"₹{row['Dividends']}"
                        })
                    if row.get("Stock Splits") and row["Stock Splits"] > 0:
                        actions_list.append({
                            "date": date_str,
                            "type": "Stock Split",
                            "amount": f"{row['Stock Splits']}:1 ratio"
                        })
            
            # Calendar extraction
            calendar = ticker.calendar
            if calendar and isinstance(calendar, dict):
                ex_div = calendar.get("Ex-Dividend Date")
                earn_date = calendar.get("Earnings Date")
                calendar_dict = {
                    "ex_dividend_date": ex_div.strftime("%Y-%m-%d") if hasattr(ex_div, "strftime") else str(ex_div or "N/A"),
                    "earnings_date": earn_date[0].strftime("%Y-%m-%d") if (isinstance(earn_date, list) and len(earn_date) > 0 and hasattr(earn_date[0], "strftime")) else str(earn_date or "N/A")
                }
        except Exception as yf_err:
            logger.warning(f"Failed to fetch live yfinance data for briefing {symbol}: {yf_err}")
        
        try:
            from app.services.ai_agent import generate_stock_briefing
            briefing = await generate_stock_briefing(
                stock_dict,
                news_list=news_list,
                actions_list=actions_list,
                calendar_dict=calendar_dict
            )
            stock.ai_summary = briefing
            await session.commit()
            
            # Invalidate Redis cache
            try:
                await redis_client.delete(
                    f"stock:{symbol}",
                    f"stock_chart:{symbol}",
                    f"stock_metrics:{symbol}",
                    f"stock_ai:{symbol}"
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
    cache_key = f"stock_search:{query.strip().lower()}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
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
        # Create a skeleton StockMaster record immediately to allow instant rendering
        try:
            stock = StockMaster(
                symbol=symbol,
                company_name=f"Discovering {symbol}...",
                sector="Unknown",
                industry="Unknown",
                ai_summary="Generating Equity Intelligence Briefing in the background..."
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
        if symbol not in ingesting_tickers:
            ingesting_tickers.add(symbol)
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
                    ingesting_tickers.discard(sym)
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sector '{sector_label}' has no seeded companies in our store."
        )
        
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
    Poll whether a dynamically ingested stock is ready.
    Returns status: 'ready' | 'discovering'
    """
    symbol = symbol.upper().strip()
    stock_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = stock_q.scalar_one_or_none()

    if stock:
        if stock.sector == "Invalid":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock {symbol} not found on NSE or BSE exchanges."
            )
        return {
            "status": "ready",
            "symbol": symbol,
            "company_name": stock.company_name,
            "sector": stock.sector,
            "alpha_score": stock.alpha_score,
        }
    return {
        "status": "discovering",
        "symbol": symbol,
        "message": "Market data ingestion is in progress. Please wait..."
    }

