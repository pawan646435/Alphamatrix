import logging
import random
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, func

from app.core.config import settings
from app.models.stock import StockMaster, StockPriceHistory
from app.models.fund import NAVHistory

logger = logging.getLogger("app.workers.stock_ingestion")

# Seed stock metadata definition
SEEDED_STOCKS = [
    {
        "symbol": "TCS",
        "company_name": "Tata Consultancy Services Ltd.",
        "isin": "INE467B01029",
        "sector": "IT",
        "industry": "IT Services",
        "market_cap": 1354000.0,
        "pe_ratio": 28.5,
        "pb_ratio": 12.2,
        "roe": 42.1,
        "debt_equity": 0.02,
        "dividend_yield": 1.15,
        "target_beta": 0.75,
        "target_cagr": 0.12,
        "base_price": 2800.0
    },
    {
        "symbol": "INFY",
        "company_name": "Infosys Ltd.",
        "isin": "INE009A01021",
        "sector": "IT",
        "industry": "IT Services",
        "market_cap": 645000.0,
        "pe_ratio": 24.2,
        "pb_ratio": 7.5,
        "roe": 31.4,
        "debt_equity": 0.05,
        "dividend_yield": 2.10,
        "target_beta": 0.90,
        "target_cagr": 0.10,
        "base_price": 1200.0
    },
    {
        "symbol": "HDFCBANK",
        "company_name": "HDFC Bank Ltd.",
        "isin": "INE040A01034",
        "sector": "Banking",
        "industry": "Private Bank",
        "market_cap": 1245000.0,
        "pe_ratio": 18.2,
        "pb_ratio": 2.8,
        "roe": 16.5,
        "debt_equity": 0.85,
        "dividend_yield": 1.10,
        "target_beta": 1.10,
        "target_cagr": 0.08,
        "base_price": 1100.0
    },
    {
        "symbol": "ICICIBANK",
        "company_name": "ICICI Bank Ltd.",
        "isin": "INE090A01021",
        "sector": "Banking",
        "industry": "Private Bank",
        "market_cap": 820000.0,
        "pe_ratio": 19.5,
        "pb_ratio": 3.1,
        "roe": 18.2,
        "debt_equity": 0.80,
        "dividend_yield": 0.90,
        "target_beta": 1.05,
        "target_cagr": 0.15,
        "base_price": 600.0
    },
    {
        "symbol": "TATAMOTORS",
        "company_name": "Tata Motors Ltd.",
        "isin": "INE155A01022",
        "sector": "Auto",
        "industry": "Passenger Cars",
        "market_cap": 352000.0,
        "pe_ratio": 15.4,
        "pb_ratio": 4.5,
        "roe": 24.5,
        "debt_equity": 1.15,
        "dividend_yield": 0.50,
        "target_beta": 1.35,
        "target_cagr": 0.35,
        "base_price": 280.0
    },
    {
        "symbol": "M&M",
        "company_name": "Mahindra & Mahindra Ltd.",
        "isin": "INE101A01026",
        "sector": "Auto",
        "industry": "Utility Vehicles",
        "market_cap": 285000.0,
        "pe_ratio": 17.8,
        "pb_ratio": 3.8,
        "roe": 20.8,
        "debt_equity": 0.90,
        "dividend_yield": 1.00,
        "target_beta": 1.15,
        "target_cagr": 0.28,
        "base_price": 750.0
    },
    {
        "symbol": "RELIANCE",
        "company_name": "Reliance Industries Ltd.",
        "isin": "INE002A01018",
        "sector": "Energy",
        "industry": "Conglomerate",
        "market_cap": 1748000.0,
        "pe_ratio": 25.8,
        "pb_ratio": 2.2,
        "roe": 9.8,
        "debt_equity": 0.38,
        "dividend_yield": 0.35,
        "target_beta": 1.00,
        "target_cagr": 0.14,
        "base_price": 1700.0
    },
    {
        "symbol": "HAL",
        "company_name": "Hindustan Aeronautics Ltd.",
        "isin": "INE066F01012",
        "sector": "Defence",
        "industry": "Aerospace & Defence",
        "market_cap": 320000.0,
        "pe_ratio": 41.5,
        "pb_ratio": 9.0,
        "roe": 28.5,
        "debt_equity": 0.00,
        "dividend_yield": 0.80,
        "target_beta": 1.20,
        "target_cagr": 0.52,
        "base_price": 800.0
    },
    {
        "symbol": "BEL",
        "company_name": "Bharat Electronics Ltd.",
        "isin": "INE263A01024",
        "sector": "Defence",
        "industry": "Aerospace & Defence",
        "market_cap": 212000.0,
        "pe_ratio": 38.2,
        "pb_ratio": 7.2,
        "roe": 24.8,
        "debt_equity": 0.02,
        "dividend_yield": 1.10,
        "target_beta": 1.10,
        "target_cagr": 0.46,
        "base_price": 100.0
    },
    {
        "symbol": "ITC",
        "company_name": "ITC Ltd.",
        "isin": "INE154A01025",
        "sector": "FMCG",
        "industry": "Diversified FMCG",
        "market_cap": 542000.0,
        "pe_ratio": 26.9,
        "pb_ratio": 7.8,
        "roe": 29.2,
        "debt_equity": 0.00,
        "dividend_yield": 3.40,
        "target_beta": 0.55,
        "target_cagr": 0.18,
        "base_price": 190.0
    }
]

def calculate_alpha_score(stock: Dict[str, Any], cagr_1y: float, cagr_3y: float) -> float:
    """
    Computes a proprietary multi-factor Alpha Score (0-100) based on:
    1. Fundamentals (ROE, Debt/Equity) - 30% weight
    2. Valuation (PE ratio, PB ratio) - 30% weight
    3. Momentum (1Y CAGR, Slope) - 25% weight
    4. Risk (Beta stability) - 15% weight
    """
    # 1. Fundamental score
    roe = stock.get("roe", 15.0)
    de = stock.get("debt_equity", 0.5)
    roe_score = min(100.0, roe * 4.0) # 25% or higher is a perfect 100
    de_score = max(0.0, 100.0 - (de * 100.0)) # 0 Debt/Equity is 100, 1.0 is 0
    fundamental_score = 0.6 * roe_score + 0.4 * de_score

    # 2. Valuation score (lower PE and PB is favored relative to industry standards)
    # We assign scores relative to reasonable benchmarks: PE of 15 is 100, PE of 40 is 30
    pe = stock.get("pe_ratio", 20.0)
    pb = stock.get("pb_ratio", 3.0)
    pe_score = max(10.0, min(100.0, 100.0 - (pe - 12) * 2.5))
    pb_score = max(10.0, min(100.0, 100.0 - (pb - 1.5) * 10.0))
    valuation_score = 0.5 * pe_score + 0.5 * pb_score

    # 3. Momentum score
    cagr_1y_val = cagr_1y if cagr_1y is not None else 0.0
    cagr_3y_val = cagr_3y if cagr_3y is not None else 0.0
    # Higher positive return gets higher score
    mom_return_score = max(0.0, min(100.0, cagr_1y_val * 200.0))
    # Accelerator: 1Y return > 3Y return indicates positive momentum acceleration
    acceleration_bonus = 20.0 if cagr_1y_val > cagr_3y_val else 0.0
    momentum_score = min(100.0, mom_return_score + acceleration_bonus)

    # 4. Risk score (Beta close to 1.0 or lower is favored for stability, high beta is penalized)
    beta = stock.get("target_beta", 1.0)
    if beta <= 0.8:
        risk_score = 95.0 # Stable, low beta
    elif beta <= 1.2:
        risk_score = 80.0 # Standard market beta
    else:
        risk_score = max(20.0, 100.0 - (beta - 1.2) * 150.0) # Penalty for high beta

    # Combine factors
    total_score = (
        0.30 * fundamental_score +
        0.30 * valuation_score +
        0.25 * momentum_score +
        0.15 * risk_score
    )
    return round(float(total_score), 2)

def fetch_ticker_data_yfinance(symbol: str) -> Tuple[Optional[pd.DataFrame], Optional[Dict[str, Any]]]:
    """
    Downloads historical close prices and stock metadata from Yahoo Finance.
    Handles NSE suffix (.NS) for Indian equities.
    Tries multiple period lengths to handle newer listings that don't have 6Y history.
    """
    import yfinance as yf
    try:
        yf_symbol = f"{symbol}.NS"
        logger.info(f"Querying yfinance for symbol {yf_symbol}...")
        ticker = yf.Ticker(yf_symbol)
        
        # Try progressively shorter periods to accommodate newer listings
        hist = pd.DataFrame()
        for period in ("6y", "max", "3y", "2y", "1y"):
            hist = ticker.history(period=period)
            if not hist.empty:
                logger.info(f"Got {len(hist)} rows for {yf_symbol} with period={period}")
                break
            logger.debug(f"No data for {yf_symbol} with period={period}, trying shorter period...")
        
        if hist.empty:
            logger.warning(f"No history returned from yfinance for {yf_symbol} across all tried periods.")
            return None, None
            
        try:
            info = ticker.info
        except Exception as info_err:
            logger.warning(f"Could not retrieve ticker info for {yf_symbol}: {info_err}")
            info = {}
            
        return hist, info
    except Exception as e:
        logger.error(f"yfinance query failed for symbol {symbol}: {e}")
        return None, None


async def dynamic_ingest_stock(symbol: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Dynamically fetches, computes, and persists a stock record for any NSE-listed symbol.
    Called when a user searches or navigates to a stock not in the local database.

    Returns a dict with status: 'ingested' | 'already_exists' | 'not_found' | 'error'
    """
    symbol = symbol.upper().strip()
    logger.info(f"[DynamicIngest] Starting dynamic ingestion for symbol: {symbol}")

    # 1. Check if already exists with history (safety check — if fully ingested, skip)
    check_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    existing = check_q.scalar_one_or_none()
    
    has_history = False
    if existing:
        prices_check = await db.execute(
            select(StockPriceHistory.id)
            .where(StockPriceHistory.symbol == symbol)
            .limit(1)
        )
        if prices_check.scalar():
            has_history = True

    if existing and has_history:
        logger.info(f"[DynamicIngest] {symbol} already exists in DB with history. Skipping ingestion.")
        return {"status": "already_exists", "symbol": symbol}

    # 2. Fetch data from Yahoo Finance (blocking IO in thread to avoid blocking event loop)
    import asyncio
    loop = asyncio.get_event_loop()
    hist, info = await loop.run_in_executor(None, lambda: fetch_ticker_data_yfinance(symbol))

    if hist is None or hist.empty:
        # Try BSE suffix as fallback
        logger.warning(f"[DynamicIngest] NSE lookup failed for {symbol}. Trying BSE suffix (.BO)...")
        def fetch_bse():
            import yfinance as yf
            try:
                ticker = yf.Ticker(f"{symbol}.BO")
                h = pd.DataFrame()
                for period in ("6y", "max", "3y", "2y", "1y"):
                    h = ticker.history(period=period)
                    if not h.empty:
                        break
                if h.empty:
                    return None, None
                try:
                    i = ticker.info
                except Exception:
                    i = {}
                return h, i
            except Exception as e:
                logger.error(f"[DynamicIngest] BSE fallback failed for {symbol}: {e}")
                return None, None


        hist, info = await loop.run_in_executor(None, fetch_bse)

    if hist is None or hist.empty:
        logger.warning(f"[DynamicIngest] No market data found for symbol {symbol} on NSE or BSE.")
        # Persist as invalid so that future requests return 404 instead of infinite discovery loops
        if existing:
            existing.sector = "Invalid"
            existing.company_name = f"Invalid Stock ({symbol})"
            existing.ai_summary = "This symbol could not be found on NSE or BSE exchanges."
            await db.commit()
        else:
            invalid_stock = StockMaster(
                symbol=symbol,
                company_name=f"Invalid Stock ({symbol})",
                isin="",
                sector="Invalid",
                industry="Unknown",
                ai_summary="This symbol could not be found on NSE or BSE exchanges."
            )
            db.add(invalid_stock)
            await db.commit()
        return {"status": "not_found", "symbol": symbol}

    # 3. Extract metadata from yfinance info
    info = info or {}
    company_name = (
        info.get("longName") or
        info.get("shortName") or
        symbol
    )
    sector = info.get("sector") or "Unknown"
    industry = info.get("industry") or "Unknown"
    isin = info.get("isin")

    mc = info.get("marketCap")
    market_cap = round(mc / 10_000_000.0, 2) if mc else None

    pe_raw = info.get("trailingPE") or info.get("forwardPE")
    pe_ratio = round(float(pe_raw), 2) if pe_raw else None

    pb_raw = info.get("priceToBook")
    pb_ratio = round(float(pb_raw), 2) if pb_raw else None

    roe_raw = info.get("returnOnEquity")
    roe = round(float(roe_raw) * 100.0, 2) if roe_raw is not None else None

    de_raw = info.get("debtToEquity")
    if de_raw is not None:
        debt_equity = round(de_raw / 100.0 if de_raw > 3.0 else de_raw, 2)
    else:
        debt_equity = None

    dy_raw = info.get("dividendYield")
    dividend_yield = round(float(dy_raw) * 100.0, 2) if dy_raw is not None else None

    beta_raw = info.get("beta")
    beta = round(float(beta_raw), 2) if beta_raw is not None else 1.0

    # 4. Build price history from historical data
    end_date = date.today()
    start_date = end_date - timedelta(days=int(5.5 * 365.25))

    prices_to_insert = []
    for timestamp, row in hist.iterrows():
        try:
            close_val = float(row["Close"])
        except Exception:
            continue
        if np.isnan(close_val):
            continue
        p_date = timestamp.date()
        if p_date < start_date:
            continue
        prices_to_insert.append(
            StockPriceHistory(symbol=symbol, date=p_date, close=round(close_val, 2))
        )

    # 5. Compute CAGR metrics from historical series
    cagr_1y = cagr_3y = cagr_5y = None
    computed_beta = beta

    if len(prices_to_insert) >= 30:
        prices_df = pd.DataFrame(
            [{"date": p.date, "close": p.close} for p in prices_to_insert]
        )
        prices_df["date"] = pd.to_datetime(prices_df["date"])
        prices_df = prices_df.sort_values("date").reset_index(drop=True)

        def get_cagr(years: int) -> float:
            latest_row = prices_df.iloc[-1]
            target_d = latest_row["date"] - pd.DateOffset(years=years)
            prices_df["diff"] = (prices_df["date"] - target_d).abs()
            idx = prices_df["diff"].idxmin()
            best_row = prices_df.loc[idx]
            if best_row["diff"].days > 30:
                return 0.0
            days = (latest_row["date"] - best_row["date"]).days
            years_act = days / 365.25
            if years_act < (years * 0.9):
                return 0.0
            return (latest_row["close"] / best_row["close"]) ** (1.0 / years_act) - 1.0

        cagr_1y = get_cagr(1)
        cagr_3y = get_cagr(3)
        cagr_5y = get_cagr(5)

    # 6. Calculate Alpha Score
    stock_meta = {
        "roe": roe or 15.0,
        "debt_equity": debt_equity or 0.5,
        "pe_ratio": pe_ratio or 20.0,
        "pb_ratio": pb_ratio or 3.0,
        "target_beta": computed_beta,
    }
    alpha_score = calculate_alpha_score(stock_meta, cagr_1y or 0.0, cagr_3y or 0.0)

    # 7. Insert or Update StockMaster record
    if existing:
        existing.company_name = company_name
        existing.isin = isin
        existing.sector = sector
        existing.industry = industry
        existing.market_cap = market_cap
        existing.pe_ratio = pe_ratio
        existing.pb_ratio = pb_ratio
        existing.roe = roe
        existing.debt_equity = debt_equity
        existing.dividend_yield = dividend_yield
        existing.beta = round(computed_beta, 2)
        existing.cagr_1y = cagr_1y
        existing.cagr_3y = cagr_3y
        existing.cagr_5y = cagr_5y
        existing.alpha_score = alpha_score
        existing.ai_summary = "Generating Equity Intelligence Briefing in the background..."
    else:
        stock_master = StockMaster(
            symbol=symbol,
            company_name=company_name,
            isin=isin,
            sector=sector,
            industry=industry,
            market_cap=market_cap,
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            roe=roe,
            debt_equity=debt_equity,
            dividend_yield=dividend_yield,
            beta=round(computed_beta, 2),
            cagr_1y=cagr_1y,
            cagr_3y=cagr_3y,
            cagr_5y=cagr_5y,
            alpha_score=alpha_score,
            ai_summary="Generating Equity Intelligence Briefing in the background..."
        )
        db.add(stock_master)

    # Sync to search index
    from app.core.database import is_sqlite
    from sqlalchemy import text
    try:
        await db.execute(text("DELETE FROM stock_search_index WHERE symbol = :symbol"), {"symbol": symbol})
        if is_sqlite:
            await db.execute(
                text("INSERT INTO stock_search_index (symbol, company_name, exchange) VALUES (:symbol, :name, 'NSE')"),
                {"symbol": symbol, "name": company_name}
            )
        else:
            await db.execute(
                text("INSERT INTO stock_search_index (symbol, company_name, exchange) VALUES (:symbol, :name, 'NSE') ON CONFLICT (symbol) DO NOTHING"),
                {"symbol": symbol, "name": company_name}
            )
    except Exception as e:
        logger.error(f"Failed to sync stock {symbol} to search index: {e}")

    if prices_to_insert:
        db.add_all(prices_to_insert)

    await db.commit()
    logger.info(
        f"[DynamicIngest] Successfully ingested {symbol} ({company_name}) "
        f"with {len(prices_to_insert)} price records. Alpha Score: {alpha_score}"
    )

    return {
        "status": "ingested",
        "symbol": symbol,
        "company_name": company_name,
        "sector": sector,
        "alpha_score": alpha_score
    }


async def seed_stocks_data(db: AsyncSession):
    """
    Main background process to seed stocks metadata and generate
    deterministic daily close price timeseries in the database.
    """
    logger.info("Initializing stock table verification & seeding...")
    
    # 5.5 years historical price range
    end_date = date.today()
    start_date = end_date - timedelta(days=int(5.5 * 365.25))
    
    # Fetch benchmark NIFTY NAVs for Beta calculations
    logger.info("Fetching Nifty index NAVs for stock Beta alignment...")
    nifty_query = await db.execute(
        select(NAVHistory.date, NAVHistory.nav)
        .where(NAVHistory.scheme_code == settings.BENCHMARK_SCHEME_CODE)
        .order_by(NAVHistory.date.asc())
    )
    nifty_navs = {row.date: row.nav for row in nifty_query.all()}
    
    for s_info in SEEDED_STOCKS:
        symbol = s_info["symbol"]
        
        # Check if already seeded
        check_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
        existing_stock = check_q.scalar_one_or_none()
        
        if existing_stock:
            logger.info(f"Stock {symbol} already exists. Skipping database seeding.")
            continue
            
        logger.info(f"Seeding stock data for symbol: {symbol}...")
        
        # Try fetching real data from Yahoo Finance
        hist, info = fetch_ticker_data_yfinance(symbol)
        
        prices_to_insert = []
        cagr_1y = None
        cagr_3y = None
        cagr_5y = None
        computed_beta = s_info["target_beta"]
        
        # Extract stock metrics from yfinance info or fall back to defaults
        real_info = {
            "company_name": s_info["company_name"],
            "isin": s_info["isin"],
            "sector": s_info["sector"],
            "industry": s_info["industry"],
            "market_cap": s_info["market_cap"],
            "pe_ratio": s_info["pe_ratio"],
            "pb_ratio": s_info["pb_ratio"],
            "roe": s_info["roe"],
            "debt_equity": s_info["debt_equity"],
            "dividend_yield": s_info["dividend_yield"],
            "beta": s_info["target_beta"]
        }
        
        if info:
            real_info["company_name"] = info.get("longName") or real_info["company_name"]
            real_info["isin"] = info.get("isin") or real_info["isin"]
            real_info["sector"] = info.get("sector") or real_info["sector"]
            real_info["industry"] = info.get("industry") or real_info["industry"]
            
            # Market Cap: convert to Crores (value / 10,000,000)
            mc = info.get("marketCap")
            if mc:
                real_info["market_cap"] = round(mc / 10000000.0, 2)
                
            # PE Ratio
            pe = info.get("trailingPE") or info.get("forwardPE")
            if pe:
                real_info["pe_ratio"] = round(pe, 2)
                
            # PB Ratio
            pb = info.get("priceToBook")
            if pb:
                real_info["pb_ratio"] = round(pb, 2)
                
            # ROE
            roe_val = info.get("returnOnEquity")
            if roe_val is not None:
                real_info["roe"] = round(roe_val * 100.0, 2)
                
            # Debt/Equity
            de_val = info.get("debtToEquity")
            if de_val is not None:
                # Yahoo Finance sometimes represents debtToEquity as percentage (e.g. 85.0 means 0.85)
                # If it's > 3, it's a percentage, otherwise it's absolute.
                real_info["debt_equity"] = round(de_val / 100.0 if de_val > 3.0 else de_val, 2)
                
            # Dividend Yield
            dy_val = info.get("dividendYield")
            if dy_val is not None:
                real_info["dividend_yield"] = round(dy_val * 100.0, 2)
                
            # Beta
            beta_val = info.get("beta")
            if beta_val is not None:
                real_info["beta"] = round(beta_val, 2)
                computed_beta = real_info["beta"]

        if hist is not None and not hist.empty:
            logger.info(f"Successfully loaded real market prices for {symbol}. Mapping historical price series...")
            # Map index (DatetimeIndex) and Close column
            for timestamp, row in hist.iterrows():
                close_val = row["Close"]
                if np.isnan(close_val):
                    continue
                # Skip prices older than 5.5 years cutoff
                p_date = timestamp.date()
                if p_date < start_date:
                    continue
                prices_to_insert.append(
                    StockPriceHistory(
                        symbol=symbol,
                        date=p_date,
                        close=round(float(close_val), 2)
                    )
                )
        else:
            logger.warning(f"Using fallback deterministic random walk generator for {symbol}.")
            # Fallback generator
            # 1. Generate price history deterministically using random seed based on symbol
            seed_value = sum(ord(c) for c in symbol)
            rng = random.Random(seed_value)
            
            # Generate trading dates (excluding weekends)
            curr_date = start_date
            trading_dates = []
            while curr_date <= end_date:
                if curr_date.weekday() < 5:  # Mon to Fri
                    trading_dates.append(curr_date)
                curr_date += timedelta(days=1)
                
            # Geometric brownian simulation parameters matching target returns
            target_cagr = s_info["target_cagr"]
            daily_drift = (1.0 + target_cagr) ** (1.0 / 252.0) - 1.0
            daily_vol = 0.015 * s_info["target_beta"] # Volatility scales with Beta
            
            price = s_info["base_price"]
            for d in trading_dates:
                change = rng.normalvariate(daily_drift, daily_vol)
                price = max(1.0, price * (1.0 + change))
                prices_to_insert.append(
                    StockPriceHistory(
                        symbol=symbol,
                        date=d,
                        close=round(price, 2)
                    )
                )

        # 2. Compute accurate Returns and Beta against the Nifty 50 benchmark
        if len(prices_to_insert) >= 30:
            prices_df = pd.DataFrame(
                [{"date": p.date, "close": p.close} for p in prices_to_insert]
            )
            prices_df["date"] = pd.to_datetime(prices_df["date"])
            prices_df = prices_df.sort_values("date").reset_index(drop=True)
            
            # Helper to calculate CAGR
            def get_cagr(years: int) -> float:
                latest_row = prices_df.iloc[-1]
                target_d = latest_row["date"] - pd.DateOffset(years=years)
                
                prices_df["diff"] = (prices_df["date"] - target_d).abs()
                idx = prices_df["diff"].idxmin()
                best_row = prices_df.loc[idx]
                
                if best_row["diff"].days > 30:
                    return 0.0
                    
                days = (latest_row["date"] - best_row["date"]).days
                years_act = days / 365.25
                if years_act < (years * 0.9):
                    return 0.0
                return (latest_row["close"] / best_row["close"]) ** (1.0 / years_act) - 1.0
                
            cagr_1y = get_cagr(1)
            cagr_3y = get_cagr(3)
            cagr_5y = get_cagr(5)
            
            # Compute Beta covariance against actual Nifty fund values
            if nifty_navs:
                prices_df["returns"] = prices_df["close"].pct_change()
                
                nifty_df = pd.DataFrame(
                    [{"date": d, "nav": n} for d, n in nifty_navs.items()]
                )
                nifty_df["date"] = pd.to_datetime(nifty_df["date"])
                nifty_df = nifty_df.sort_values("date").reset_index(drop=True)
                nifty_df["nifty_returns"] = nifty_df["nav"].pct_change()
                
                merged = pd.merge(
                    prices_df[["date", "returns"]],
                    nifty_df[["date", "nifty_returns"]],
                    on="date"
                ).dropna()
                
                if len(merged) >= 20:
                    cov = merged["returns"].cov(merged["nifty_returns"])
                    var = merged["nifty_returns"].var()
                    if var > 0:
                        computed_beta = float(cov / var)
                        
        # 3. Calculate Alpha Score
        alpha_score = calculate_alpha_score(real_info, cagr_1y, cagr_3y)
        
        # 4. Insert StockMaster record first
        stock_master = StockMaster(
            symbol=symbol,
            company_name=real_info["company_name"],
            isin=real_info["isin"],
            sector=real_info["sector"],
            industry=real_info["industry"],
            market_cap=real_info["market_cap"],
            pe_ratio=real_info["pe_ratio"],
            pb_ratio=real_info["pb_ratio"],
            roe=real_info["roe"],
            debt_equity=real_info["debt_equity"],
            dividend_yield=real_info["dividend_yield"],
            beta=round(computed_beta, 2),
            cagr_1y=cagr_1y,
            cagr_3y=cagr_3y,
            cagr_5y=cagr_5y,
            alpha_score=alpha_score,
            ai_summary="Generating Equity Intelligence Briefing in the background..."
        )
        db.add(stock_master)
        await db.flush()

        # 5. Batch insert price histories
        db.add_all(prices_to_insert)
        await db.flush()
        logger.info(f"Inserted {len(prices_to_insert)} price records for {symbol}.")
        
        # Sync to search index
        from app.core.database import is_sqlite
        from sqlalchemy import text
        try:
            await db.execute(text("DELETE FROM stock_search_index WHERE symbol = :symbol"), {"symbol": symbol})
            if is_sqlite:
                await db.execute(
                    text("INSERT INTO stock_search_index (symbol, company_name, exchange) VALUES (:symbol, :name, 'NSE')"),
                    {"symbol": symbol, "name": real_info["company_name"]}
                )
            else:
                await db.execute(
                    text("INSERT INTO stock_search_index (symbol, company_name, exchange) VALUES (:symbol, :name, 'NSE') ON CONFLICT (symbol) DO NOTHING"),
                    {"symbol": symbol, "name": real_info["company_name"]}
                )
        except Exception as e:
            logger.error(f"Failed to sync stock {symbol} to search index: {e}")
        
    await db.commit()
    logger.info("Stock seeding background task finished successfully.")

async def populate_search_indices(db: AsyncSession):
    """
    Seeds mutual fund and stock search index tables (both SQLite and PostgreSQL) and stock_masters skeleton records.
    """
    from sqlalchemy import text
    import json
    import os
    import csv
    import httpx
    from app.core.database import is_sqlite
    
    # 1. Populate Mutual Funds Index if below threshold
    check_funds = await db.execute(text("SELECT COUNT(*) FROM fund_search_index"))
    funds_count = check_funds.scalar() or 0
    if funds_count < 30000:
        logger.info(f"Fund search index has only {funds_count} records. Seeding fund_search_index table...")
        try:
            await db.execute(text("DELETE FROM fund_search_index"))
        except Exception as e:
            logger.warning(f"Failed to clear fund_search_index table: {e}")
            
        CACHE_FILE = "mf_master_list.json"
        mf_list = []
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    mf_list = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read disk cache for seeding: {e}")
                
        if not mf_list:
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get("https://api.mfapi.in/mf", timeout=15.0)
                    if res.status_code == 200:
                        mf_list = res.json()
                        with open(CACHE_FILE, "w", encoding="utf-8") as f:
                            json.dump(mf_list, f)
            except Exception as e:
                logger.error(f"Failed to fetch master fund list for seeding: {e}")
                
        if mf_list:
            logger.info(f"Inserting {len(mf_list)} mutual funds into search index...")
            if is_sqlite:
                stmt = "INSERT INTO fund_search_index (scheme_code, scheme_name) VALUES (:code, :name)"
            else:
                stmt = "INSERT INTO fund_search_index (scheme_code, scheme_name) VALUES (:code, :name) ON CONFLICT (scheme_code) DO NOTHING"
            batch_size = 5000
            for i in range(0, len(mf_list), batch_size):
                batch = mf_list[i:i+batch_size]
                params = [{"code": str(item["schemeCode"]), "name": item["schemeName"]} for item in batch]
                await db.execute(text(stmt), params)
            await db.commit()
            logger.info("Fund search index successfully seeded.")

    # 2. Populate stock_masters skeleton records and search index if below threshold
    check_stocks = await db.execute(text("SELECT COUNT(*) FROM stock_masters"))
    stocks_count = check_stocks.scalar() or 0
    if stocks_count < 2000:
        logger.info(f"Stock masters table has only {stocks_count} records. Seeding stock_masters from NSE...")
        if is_sqlite:
            try:
                await db.execute(text("DELETE FROM stock_search_index"))
            except Exception as e:
                logger.warning(f"Failed to clear stock_search_index FTS5 table: {e}")
                
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get("https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv", headers=headers, timeout=20.0)
                if res.status_code == 200:
                    lines = res.text.strip().split("\n")
                    reader = csv.reader(lines)
                    header = next(reader)
                    
                    stocks_to_insert = []
                    for row in reader:
                        if len(row) >= 7:
                            symbol = row[0].strip()
                            name = row[1].strip()
                            isin = row[6].strip()
                            if symbol == "SYMBOL" or not symbol:
                                continue
                            stocks_to_insert.append({"symbol": symbol, "name": name, "isin": isin})
                            
                    if stocks_to_insert:
                        logger.info(f"Inserting {len(stocks_to_insert)} NSE tickers into DB...")
                        if is_sqlite:
                            stmt_master = """
                                INSERT OR IGNORE INTO stock_masters (symbol, company_name, isin, sector)
                                VALUES (:symbol, :name, :isin, 'Unknown')
                            """
                            stmt_fts = """
                                INSERT INTO stock_search_index (symbol, company_name, exchange)
                                VALUES (:symbol, :name, 'NSE')
                            """
                        else:
                            stmt_master = """
                                INSERT INTO stock_masters (symbol, company_name, isin, sector)
                                VALUES (:symbol, :name, :isin, 'Unknown')
                                ON CONFLICT (symbol) DO NOTHING
                            """
                            stmt_fts = """
                                INSERT INTO stock_search_index (symbol, company_name, exchange)
                                VALUES (:symbol, :name, 'NSE')
                                ON CONFLICT (symbol) DO NOTHING
                            """
                            
                        batch_size = 1000
                        for i in range(0, len(stocks_to_insert), batch_size):
                            batch = stocks_to_insert[i:i+batch_size]
                            await db.execute(text(stmt_master), batch)
                            if stmt_fts:
                                await db.execute(text(stmt_fts), batch)
                        await db.commit()
                        logger.info("Stock masters (and search index) successfully seeded.")
        except Exception as e:
            logger.error(f"Failed to fetch and seed stock list: {e}")

    # 3. Ensure stock_search_index is populated from stock_masters if empty
    check_stocks_idx = await db.execute(text("SELECT COUNT(*) FROM stock_search_index"))
    stocks_idx_count = check_stocks_idx.scalar() or 0
    if stocks_idx_count < 2000:
        logger.info(f"Stock search index has only {stocks_idx_count} records. Syncing with stock_masters...")
        try:
            if is_sqlite:
                await db.execute(text("DELETE FROM stock_search_index"))
                await db.execute(text("""
                    INSERT INTO stock_search_index (symbol, company_name, exchange)
                    SELECT symbol, company_name, 'NSE' FROM stock_masters
                """))
            else:
                await db.execute(text("""
                    INSERT INTO stock_search_index (symbol, company_name, exchange)
                    SELECT symbol, company_name, 'NSE' FROM stock_masters
                    ON CONFLICT (symbol) DO NOTHING
                """))
            await db.commit()
            logger.info("Stock search index successfully synced from stock_masters.")
        except Exception as e:
            logger.error(f"Failed to sync stock search index from stock_masters: {e}")

