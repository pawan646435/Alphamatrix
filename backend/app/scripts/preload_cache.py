import asyncio
import json
import logging
from sqlalchemy.future import select
from app.core.database import async_session_maker
from app.models.stock import StockMaster, StockPriceHistory
from app.models.fund import FundMaster, NAVHistory
from app.core.redis import redis_client
from app.core.cache_ttl import (
    OPTIMIZED_METADATA_TTL,
    OPTIMIZED_METRICS_TTL,
    OPTIMIZED_CHART_TTL,
    OPTIMIZED_AI_TTL
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.scripts.preload_cache")

# Target symbols and scheme codes to preload
POPULAR_STOCKS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "KOTAKBANK"]
POPULAR_FUNDS = [119063, 120716, 143269, 101745]

async def preload_stock(session, symbol: str):
    logger.info(f"Pre-warming cache for stock: {symbol}")
    res = await session.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = res.scalar_one_or_none()
    if not stock:
        logger.warning(f"Stock {symbol} not found in DB. Skipping preheat.")
        return
        
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
    
    # Fetch price history
    prices_q = await session.execute(
        select(StockPriceHistory.date, StockPriceHistory.close)
        .where(StockPriceHistory.symbol == symbol)
        .order_by(StockPriceHistory.date.desc())
    )
    prices = [{"date": row.date.isoformat(), "close": row.close} for row in prices_q.all()]
    
    # Write to Redis
    try:
        await redis_client.setex(f"stock:{symbol}", OPTIMIZED_METADATA_TTL, json.dumps(meta_dict))
        await redis_client.setex(f"stock_metrics:{symbol}", OPTIMIZED_METRICS_TTL, json.dumps(metrics_dict))
        await redis_client.setex(f"stock_chart:{symbol}", OPTIMIZED_CHART_TTL, json.dumps(prices))
        
        briefing_ttl = 5 if stock.ai_summary == "Generating Equity Intelligence Briefing in the background..." else OPTIMIZED_AI_TTL
        await redis_client.setex(f"stock_ai:{symbol}", briefing_ttl, stock.ai_summary or "Generating Equity Intelligence Briefing in the background...")
        logger.info(f"Successfully cached stock details for {symbol}")
    except Exception as e:
        logger.error(f"Failed to cache stock {symbol}: {e}")

async def preload_fund(session, scheme_code: int):
    logger.info(f"Pre-warming cache for mutual fund: {scheme_code}")
    res = await session.execute(select(FundMaster).where(FundMaster.scheme_code == scheme_code))
    fund = res.scalar_one_or_none()
    if not fund:
        logger.warning(f"Fund {scheme_code} not found in DB. Skipping preheat.")
        return
        
    meta_dict = {
        "scheme_code": fund.scheme_code,
        "isin": fund.isin,
        "fund_name": fund.fund_name,
        "category": fund.category,
        "sub_category": fund.sub_category,
    }
    metrics_dict = {
        "pe_ratio": fund.pe_ratio,
        "expense_ratio": fund.expense_ratio,
        "cagr_1y": fund.cagr_1y,
        "cagr_3y": fund.cagr_3y,
        "cagr_5y": fund.cagr_5y,
        "sharpe_ratio": fund.sharpe_ratio,
        "sortino_ratio": fund.sortino_ratio,
        "alpha": fund.alpha,
        "beta": fund.beta,
        "last_updated": fund.last_updated.isoformat() if fund.last_updated else None,
    }
    
    # Fetch NAV History
    nav_check = await session.execute(
        select(NAVHistory.date, NAVHistory.nav)
        .where(NAVHistory.scheme_code == scheme_code)
        .order_by(NAVHistory.date.desc())
    )
    navs = [{"date": row.date.isoformat(), "nav": row.nav} for row in nav_check.all()]
    
    # Write to Redis
    try:
        await redis_client.setex(f"fund:{scheme_code}", OPTIMIZED_METADATA_TTL, json.dumps(meta_dict))
        await redis_client.setex(f"fund_metrics:{scheme_code}", OPTIMIZED_METRICS_TTL, json.dumps(metrics_dict))
        await redis_client.setex(f"fund_chart:{scheme_code}", OPTIMIZED_CHART_TTL, json.dumps(navs))
        
        ai_ttl = 5 if fund.ai_summary == "Generating AI Analysis in the background..." else OPTIMIZED_AI_TTL
        await redis_client.setex(f"fund_ai:{scheme_code}", ai_ttl, fund.ai_summary or "Generating AI Analysis in the background...")
        logger.info(f"Successfully cached fund details for {scheme_code}")
    except Exception as e:
        logger.error(f"Failed to cache fund {scheme_code}: {e}")

async def main():
    logger.info("Initializing preheat database session...")
    async with async_session_maker() as session:
        for symbol in POPULAR_STOCKS:
            await preload_stock(session, symbol)
            
        for code in POPULAR_FUNDS:
            await preload_fund(session, code)
    logger.info("Cache preheating successfully completed!")

if __name__ == '__main__':
    asyncio.run(main())
