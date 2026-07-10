# PEP 563: defer evaluation of annotations to strings so the pd.DataFrame /
# np.* type hints below don't require pandas/numpy to be imported at module
# load time — they're only needed inside the specific functions that use them
# (see lazy `import pandas as pd` / `import numpy as np` in those functions).
from __future__ import annotations

import asyncio
import os
import re
import json
import logging
import random
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, func

from app.core.config import settings
from app.models.stock import StockMaster, StockPriceHistory
from app.models.fund import NAVHistory

logger = logging.getLogger("app.workers.stock_ingestion")

SECTOR_OVERRIDES = {
    # IT
    "TCS": "IT", "INFY": "IT",
    # Banking
    "HDFCBANK": "Banking", "ICICIBANK": "Banking",
    # Auto
    "TATAMOTORS": "Auto", "M&M": "Auto",
    # Energy
    "RELIANCE": "Energy",
    # Defence
    "HAL": "Defence", "BEL": "Defence", "BDL": "Defence", 
    "MAZDOCK": "Defence", "COCHINSHIP": "Defence", 
    "DATAPATTNS": "Defence", "PARAS": "Defence", 
    "GRSE": "Defence", "SOLARINDS": "Defence", "ASTRAMICRO": "Defence",
    # FMCG
    "ITC": "FMCG", "HINDUNILVR": "FMCG", "NESTLEIND": "FMCG", 
    "BRITANNIA": "FMCG", "DABUR": "FMCG", "GODREJCP": "FMCG", 
    "MARICO": "FMCG", "COLPAL": "FMCG", "TATACONSUM": "FMCG", "EMAMILTD": "FMCG",
    # Pharma
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma",
    # Metals
    "TATASTEEL": "Metals", "JSWSTEEL": "Metals",
    # Infrastructure
    "LT": "Infrastructure",
    # Chemicals
    "PIDILITIND": "Chemicals",
    # Consumer Durables
    "TITAN": "Consumer Durables", "VOLTAS": "Consumer Durables",
    # Realty
    "DLF": "Realty",
    # Telecom
    "BHARTIARTL": "Telecom",
    # PSU
    "ONGC": "PSU", "NTPC": "PSU",
    # Capital Goods
    "BHEL": "Capital Goods"
}

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
        "symbol": "BDL",
        "company_name": "Bharat Dynamics Limited",
        "isin": "INE171Z01018",
        "sector": "Defence",
        "industry": "Aerospace & Defence",
        "market_cap": 35000.0,
        "pe_ratio": 65.4,
        "pb_ratio": 15.2,
        "roe": 22.8,
        "debt_equity": 0.05,
        "dividend_yield": 1.20,
        "target_beta": 1.15,
        "target_cagr": 0.40,
        "base_price": 600.0
    },
    {
        "symbol": "MAZDOCK",
        "company_name": "Mazagon Dock Shipbuilders Limited",
        "isin": "INE249Z01012",
        "sector": "Defence",
        "industry": "Aerospace & Defence",
        "market_cap": 42000.0,
        "pe_ratio": 45.8,
        "pb_ratio": 12.5,
        "roe": 25.4,
        "debt_equity": 0.01,
        "dividend_yield": 0.90,
        "target_beta": 1.25,
        "target_cagr": 0.55,
        "base_price": 1800.0
    },
    {
        "symbol": "COCHINSHIP",
        "company_name": "Cochin Shipyard Limited",
        "isin": "INE704P01017",
        "sector": "Defence",
        "industry": "Aerospace & Defence",
        "market_cap": 22000.0,
        "pe_ratio": 42.1,
        "pb_ratio": 10.8,
        "roe": 23.5,
        "debt_equity": 0.12,
        "dividend_yield": 1.40,
        "target_beta": 1.20,
        "target_cagr": 0.48,
        "base_price": 1200.0
    },
    {
        "symbol": "DATAPATTNS",
        "company_name": "Data Patterns (India) Limited",
        "isin": "INE0IXN01010",
        "sector": "Defence",
        "industry": "Aerospace & Defence",
        "market_cap": 11000.0,
        "pe_ratio": 55.6,
        "pb_ratio": 9.4,
        "roe": 18.9,
        "debt_equity": 0.08,
        "dividend_yield": 0.50,
        "target_beta": 1.10,
        "target_cagr": 0.38,
        "base_price": 1500.0
    },
    {
        "symbol": "PARAS",
        "company_name": "Paras Defence and Space Technologies Limited",
        "isin": "INE045601015",
        "sector": "Defence",
        "industry": "Aerospace & Defence",
        "market_cap": 2800.0,
        "pe_ratio": 72.3,
        "pb_ratio": 6.8,
        "roe": 9.5,
        "debt_equity": 0.15,
        "dividend_yield": 0.20,
        "target_beta": 1.30,
        "target_cagr": 0.28,
        "base_price": 600.0
    },
    {
        "symbol": "GRSE",
        "company_name": "Garden Reach Shipbuilders & Engineers Limited",
        "isin": "INE265D01015",
        "sector": "Defence",
        "industry": "Aerospace & Defence",
        "market_cap": 18000.0,
        "pe_ratio": 38.5,
        "pb_ratio": 8.2,
        "roe": 21.3,
        "debt_equity": 0.04,
        "dividend_yield": 1.50,
        "target_beta": 1.22,
        "target_cagr": 0.42,
        "base_price": 1000.0
    },
    {
        "symbol": "SOLARINDS",
        "company_name": "Solar Industries India Limited",
        "isin": "INE343H01029",
        "sector": "Defence",
        "industry": "Aerospace & Defence",
        "market_cap": 65000.0,
        "pe_ratio": 55.4,
        "pb_ratio": 14.6,
        "roe": 28.9,
        "debt_equity": 0.22,
        "dividend_yield": 0.40,
        "target_beta": 0.95,
        "target_cagr": 0.32,
        "base_price": 7000.0
    },
    {
        "symbol": "ASTRAMICRO",
        "company_name": "Astra Microwave Products Limited",
        "isin": "INE386C01029",
        "sector": "Defence",
        "industry": "Aerospace & Defence",
        "market_cap": 5800.0,
        "pe_ratio": 48.9,
        "pb_ratio": 7.3,
        "roe": 15.6,
        "debt_equity": 0.18,
        "dividend_yield": 0.60,
        "target_beta": 1.18,
        "target_cagr": 0.30,
        "base_price": 600.0
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
    },
    {
        "symbol": "HINDUNILVR",
        "company_name": "Hindustan Unilever Limited",
        "isin": "INE030A01027",
        "sector": "FMCG",
        "industry": "Household & Personal Products",
        "market_cap": 580000.0,
        "pe_ratio": 62.4,
        "pb_ratio": 18.5,
        "roe": 29.5,
        "debt_equity": 0.03,
        "dividend_yield": 1.65,
        "target_beta": 0.60,
        "target_cagr": 0.12,
        "base_price": 2400.0
    },
    {
        "symbol": "NESTLEIND",
        "company_name": "Nestle India Limited",
        "isin": "INE239A01016",
        "sector": "FMCG",
        "industry": "Packaged Foods",
        "market_cap": 240000.0,
        "pe_ratio": 78.3,
        "pb_ratio": 22.4,
        "roe": 105.4,
        "debt_equity": 0.02,
        "dividend_yield": 1.25,
        "target_beta": 0.55,
        "target_cagr": 0.14,
        "base_price": 2400.0
    },
    {
        "symbol": "BRITANNIA",
        "company_name": "Britannia Industries Limited",
        "isin": "INE216A01030",
        "sector": "FMCG",
        "industry": "Packaged Foods",
        "market_cap": 110000.0,
        "pe_ratio": 55.4,
        "pb_ratio": 16.8,
        "roe": 48.9,
        "debt_equity": 0.45,
        "dividend_yield": 1.55,
        "target_beta": 0.62,
        "target_cagr": 0.15,
        "base_price": 4500.0
    },
    {
        "symbol": "DABUR",
        "company_name": "Dabur India Limited",
        "isin": "INE016A01026",
        "sector": "FMCG",
        "industry": "Household & Personal Products",
        "market_cap": 95000.0,
        "pe_ratio": 52.4,
        "pb_ratio": 9.8,
        "roe": 19.5,
        "debt_equity": 0.05,
        "dividend_yield": 1.10,
        "target_beta": 0.65,
        "target_cagr": 0.10,
        "base_price": 520.0
    },
    {
        "symbol": "GODREJCP",
        "company_name": "Godrej Consumer Products Limited",
        "isin": "INE102D01028",
        "sector": "FMCG",
        "industry": "Household & Personal Products",
        "market_cap": 105000.0,
        "pe_ratio": 58.2,
        "pb_ratio": 11.2,
        "roe": 18.5,
        "debt_equity": 0.12,
        "dividend_yield": 1.00,
        "target_beta": 0.68,
        "target_cagr": 0.13,
        "base_price": 1000.0
    },
    {
        "symbol": "MARICO",
        "company_name": "Marico Limited",
        "isin": "INE196A01026",
        "sector": "FMCG",
        "industry": "Household & Personal Products",
        "market_cap": 68000.0,
        "pe_ratio": 48.5,
        "pb_ratio": 12.3,
        "roe": 35.4,
        "debt_equity": 0.02,
        "dividend_yield": 1.80,
        "target_beta": 0.63,
        "target_cagr": 0.11,
        "base_price": 500.0
    },
    {
        "symbol": "COLPAL",
        "company_name": "Colgate Palmolive India Limited",
        "isin": "INE259A01022",
        "sector": "FMCG",
        "industry": "Household & Personal Products",
        "market_cap": 62000.0,
        "pe_ratio": 42.8,
        "pb_ratio": 15.6,
        "roe": 72.3,
        "debt_equity": 0.00,
        "dividend_yield": 2.10,
        "target_beta": 0.58,
        "target_cagr": 0.13,
        "base_price": 2000.0
    },
    {
        "symbol": "TATACONSUM",
        "company_name": "Tata Consumer Products Limited",
        "isin": "INE192A01025",
        "sector": "FMCG",
        "industry": "Packaged Foods",
        "market_cap": 92000.0,
        "pe_ratio": 68.4,
        "pb_ratio": 8.5,
        "roe": 12.8,
        "debt_equity": 0.18,
        "dividend_yield": 0.95,
        "target_beta": 0.70,
        "target_cagr": 0.16,
        "base_price": 850.0
    },
    {
        "symbol": "EMAMILTD",
        "company_name": "Emami Limited",
        "isin": "INE273H01015",
        "sector": "FMCG",
        "industry": "Household & Personal Products",
        "market_cap": 22000.0,
        "pe_ratio": 28.4,
        "pb_ratio": 6.5,
        "roe": 22.8,
        "debt_equity": 0.05,
        "dividend_yield": 2.00,
        "target_beta": 0.72,
        "target_cagr": 0.09,
        "base_price": 450.0
    },
    {
        "symbol": "SUNPHARMA",
        "company_name": "Sun Pharmaceutical Industries Limited",
        "isin": "INE044A01037",
        "sector": "Pharma",
        "industry": "Pharmaceuticals",
        "market_cap": 360000.0,
        "pe_ratio": 35.0,
        "pb_ratio": 4.5,
        "roe": 14.5,
        "debt_equity": 0.05,
        "dividend_yield": 0.85,
        "target_beta": 0.70,
        "target_cagr": 0.15,
        "base_price": 1500.0
    },
    {
        "symbol": "DRREDDY",
        "company_name": "Dr. Reddy's Laboratories Limited",
        "isin": "INE089A01023",
        "sector": "Pharma",
        "industry": "Pharmaceuticals",
        "market_cap": 100000.0,
        "pe_ratio": 20.0,
        "pb_ratio": 3.2,
        "roe": 16.0,
        "debt_equity": 0.08,
        "dividend_yield": 1.20,
        "target_beta": 0.65,
        "target_cagr": 0.11,
        "base_price": 5000.0
    },
    {
        "symbol": "TATASTEEL",
        "company_name": "Tata Steel Limited",
        "isin": "INE081A01020",
        "sector": "Metals",
        "industry": "Steel",
        "market_cap": 18000.0,
        "pe_ratio": 15.0,
        "pb_ratio": 1.8,
        "roe": 12.0,
        "debt_equity": 0.95,
        "dividend_yield": 2.50,
        "target_beta": 1.20,
        "target_cagr": 0.08,
        "base_price": 150.0
    },
    {
        "symbol": "JSWSTEEL",
        "company_name": "JSW Steel Limited",
        "isin": "INE019A01030",
        "sector": "Metals",
        "industry": "Steel",
        "market_cap": 200000.0,
        "pe_ratio": 22.0,
        "pb_ratio": 2.5,
        "roe": 11.5,
        "debt_equity": 1.20,
        "dividend_yield": 1.10,
        "target_beta": 1.25,
        "target_cagr": 0.10,
        "base_price": 800.0
    },
    {
        "symbol": "LT",
        "company_name": "Larsen & Toubro Limited",
        "isin": "INE018A01030",
        "sector": "Infrastructure",
        "industry": "Engineering & Construction",
        "market_cap": 480000.0,
        "pe_ratio": 32.0,
        "pb_ratio": 4.8,
        "roe": 15.0,
        "debt_equity": 1.50,
        "dividend_yield": 0.80,
        "target_beta": 1.10,
        "target_cagr": 0.18,
        "base_price": 3500.0
    },
    {
        "symbol": "PIDILITIND",
        "company_name": "Pidilite Industries Limited",
        "isin": "INE318A01026",
        "sector": "Chemicals",
        "industry": "Specialty Chemicals",
        "market_cap": 150000.0,
        "pe_ratio": 65.0,
        "pb_ratio": 18.0,
        "roe": 28.0,
        "debt_equity": 0.02,
        "dividend_yield": 0.40,
        "target_beta": 0.60,
        "target_cagr": 0.16,
        "base_price": 2800.0
    },
    {
        "symbol": "TITAN",
        "company_name": "Titan Company Limited",
        "isin": "INE280A01028",
        "sector": "Consumer Durables",
        "industry": "Consumer Durables",
        "market_cap": 310000.0,
        "pe_ratio": 85.0,
        "pb_ratio": 22.0,
        "roe": 26.0,
        "debt_equity": 0.15,
        "dividend_yield": 0.30,
        "target_beta": 0.85,
        "target_cagr": 0.22,
        "base_price": 3500.0
    },
    {
        "symbol": "VOLTAS",
        "company_name": "Voltas Limited",
        "isin": "INE226A01021",
        "sector": "Consumer Durables",
        "industry": "Consumer Durables",
        "market_cap": 50000.0,
        "pe_ratio": 45.0,
        "pb_ratio": 5.5,
        "roe": 12.0,
        "debt_equity": 0.10,
        "dividend_yield": 0.90,
        "target_beta": 1.05,
        "target_cagr": 0.14,
        "base_price": 1500.0
    },
    {
        "symbol": "DLF",
        "company_name": "DLF Limited",
        "isin": "INE271C01023",
        "sector": "Realty",
        "industry": "Real Estate",
        "market_cap": 220000.0,
        "pe_ratio": 55.0,
        "pb_ratio": 4.2,
        "roe": 8.5,
        "debt_equity": 0.35,
        "dividend_yield": 0.45,
        "target_beta": 1.30,
        "target_cagr": 0.25,
        "base_price": 900.0
    },
    {
        "symbol": "BHARTIARTL",
        "company_name": "Bharti Airtel Limited",
        "isin": "INE397D01024",
        "sector": "Telecom",
        "industry": "Telecommunications",
        "market_cap": 850000.0,
        "pe_ratio": 50.0,
        "pb_ratio": 6.8,
        "roe": 13.5,
        "debt_equity": 1.80,
        "dividend_yield": 0.60,
        "target_beta": 0.90,
        "target_cagr": 0.20,
        "base_price": 1400.0
    },
    {
        "symbol": "ONGC",
        "company_name": "Oil & Natural Gas Corporation Limited",
        "isin": "INE213A01029",
        "sector": "PSU",
        "industry": "Oil & Gas Exploration",
        "market_cap": 320000.0,
        "pe_ratio": 8.5,
        "pb_ratio": 1.1,
        "roe": 14.0,
        "debt_equity": 0.45,
        "dividend_yield": 4.50,
        "target_beta": 1.15,
        "target_cagr": 0.12,
        "base_price": 260.0
    },
    {
        "symbol": "NTPC",
        "company_name": "NTPC Limited",
        "isin": "INE733E01010",
        "sector": "PSU",
        "industry": "Power Generation",
        "market_cap": 350000.0,
        "pe_ratio": 16.5,
        "pb_ratio": 2.1,
        "roe": 13.0,
        "debt_equity": 1.60,
        "dividend_yield": 3.25,
        "target_beta": 0.95,
        "target_cagr": 0.24,
        "base_price": 360.0
    },
    {
        "symbol": "BHEL",
        "company_name": "Bharat Heavy Electricals Limited",
        "isin": "INE257A01026",
        "sector": "Capital Goods",
        "industry": "Heavy Electrical Equipment",
        "market_cap": 100000.0,
        "pe_ratio": 120.0,
        "pb_ratio": 4.5,
        "roe": 3.5,
        "debt_equity": 0.30,
        "dividend_yield": 0.40,
        "target_beta": 1.40,
        "target_cagr": 0.38,
        "base_price": 280.0
    }
]

async def get_sector_averages(sector: str, db) -> Dict[str, float]:
    """
    Fetch sector averages from database with Redis caching.
    """
    import json
    from app.core.redis import redis_client
    cache_key = f"sector_averages:{sector.lower()}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get sector averages failed: {e}")
        
    try:
        from app.models.stock import StockMaster
        from sqlalchemy import select, func
        res = await db.execute(
            select(
                func.avg(StockMaster.pe_ratio).label("avg_pe"),
                func.avg(StockMaster.pb_ratio).label("avg_pb"),
                func.avg(StockMaster.roe).label("avg_roe"),
                func.avg(StockMaster.debt_equity).label("avg_de"),
                func.avg(StockMaster.cagr_3y).label("avg_cagr_3y")
            )
            .where(StockMaster.sector == sector)
            .where(StockMaster.pe_ratio != None)
        )
        row = res.one_or_none()
        avgs = {
            "pe": round(float(row.avg_pe), 2) if row and row.avg_pe else 22.0,
            "pb": round(float(row.avg_pb), 2) if row and row.avg_pb else 3.0,
            "roe": round(float(row.avg_roe), 2) if row and row.avg_roe else 15.0,
            "de": round(float(row.avg_de), 2) if row and row.avg_de else 0.5,
            "cagr_3y": round(float(row.avg_cagr_3y), 2) if row and row.avg_cagr_3y else 0.15
        }
        
        try:
            await redis_client.setex(cache_key, 86400, json.dumps(avgs))
        except Exception as e:
            logger.error(f"Redis set sector averages failed: {e}")
            
        return avgs
    except Exception as e:
        logger.error(f"Database query for sector averages failed: {e}")
        return {"pe": 22.0, "pb": 3.0, "roe": 15.0, "de": 0.5, "cagr_3y": 0.15}

def calculate_technical_indicators(prices: List[float]) -> Dict[str, Any]:
    """
    Calculate RSI, MACD, 50 DMA, 200 DMA from price list.
    """
    if len(prices) < 20:
        return {"rsi": 50.0, "macd_bullish": True, "dma_50": None, "dma_200": None, "latest": prices[-1] if prices else 100.0}

    import pandas as pd
    s = pd.Series(prices)
    latest = prices[-1]
    dma_50 = float(s.rolling(window=min(50, len(prices))).mean().iloc[-1])
    dma_200 = float(s.rolling(window=min(200, len(prices))).mean().iloc[-1]) if len(prices) >= 200 else dma_50
    
    # RSI Calculation
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean().iloc[-1]
    avg_loss = loss.rolling(window=14).mean().iloc[-1]
    
    if pd.isna(avg_gain) or pd.isna(avg_loss) or avg_loss == 0:
        rsi = 50.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
    # MACD Calculation
    ema_12 = s.ewm(span=12, adjust=False).mean()
    ema_26 = s.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    
    macd_bullish = bool(macd_line.iloc[-1] > signal_line.iloc[-1])
    
    return {
        "rsi": float(rsi) if not pd.isna(rsi) else 50.0,
        "macd_bullish": macd_bullish,
        "dma_50": dma_50,
        "dma_200": dma_200,
        "latest": latest
    }

def detect_trend_structure(prices_list: List[float]) -> str:
    if len(prices_list) < 40:
        return "SIDEWAYS"
    try:
        import pandas as pd
        s = pd.Series(prices_list)
        smoothed = s.rolling(window=15, min_periods=1).mean().tolist()
        
        peaks = []
        troughs = []
        window = 10
        
        for i in range(window, len(smoothed) - window):
            seg = smoothed[i - window : i + window + 1]
            val = smoothed[i]
            if val == max(seg):
                peaks.append(val)
            elif val == min(seg):
                troughs.append(val)
                
        if len(peaks) >= 2 and len(troughs) >= 2:
            last_peaks = peaks[-3:]
            last_troughs = troughs[-3:]
            
            hh = all(last_peaks[j] > last_peaks[j-1] for j in range(1, len(last_peaks)))
            hl = all(last_troughs[j] > last_troughs[j-1] for j in range(1, len(last_troughs)))
            
            lh = all(last_peaks[j] < last_peaks[j-1] for j in range(1, len(last_peaks)))
            ll = all(last_troughs[j] < last_troughs[j-1] for j in range(1, len(last_troughs)))
            
            if hh and hl:
                return "BULLISH"
            elif lh and ll:
                return "BEARISH"
                
        # Fallback to SMA slopes
        dma_50 = s.rolling(window=min(50, len(s))).mean().iloc[-1]
        dma_200 = s.rolling(window=min(200, len(s))).mean().iloc[-1]
        if dma_50 > dma_200 * 1.03:
            return "BULLISH"
        elif dma_50 < dma_200 * 0.97:
            return "BEARISH"
    except Exception:
        pass
    return "SIDEWAYS"

def calculate_event_score(news_list: List[Dict[str, Any]]) -> float:
    if not news_list:
        return 80.0
    import re
    pos_count = 0
    neg_count = 0
    
    pos_pat = re.compile(
        r'\b(new order|bags contract|secured contract|secured order|capacity expansion|expansion plan|margin expansion|regulatory approval|fda approval|approved|product launch|unveils|launches|jv|joint venture|acquisition|order win)\b', 
        re.IGNORECASE
    )
    neg_pat = re.compile(
        r'\b(promoter sells|promoter selling|insider sale|pledge|earnings miss|profit falls|loss widens|misses estimate|debt rises|debt increase|investigation|probe|sebi|fraud|irregularity|governance|audit concern|downgrade|lowers rating|cut target|default|penalty|fine)\b', 
        re.IGNORECASE
    )
    
    for item in news_list:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        if pos_pat.search(text):
            pos_count += 1
        if neg_pat.search(text):
            neg_count += 1
            
    score = 80.0 + (pos_count * 5.0) - (neg_count * 15.0)
    return max(0.0, min(100.0, score))

# ─────────────────────────────────────────────────────────────
# ALPHA SCORE WEIGHT PROFILES
# ─────────────────────────────────────────────────────────────
# Both profiles are weighted sums over the same six pillar scores
# (fundamental/quality/valuation/technical/risk/sector_relative) — same
# inputs, different emphasis, so investor_verdict and trader_verdict are
# genuinely distinct outputs rather than both being map_verdict(final_score)
# on the same number (the bug this profile split fixes).
#
# INVESTOR profile: fundamentals-led, for buy-and-hold / long-horizon framing.
INVESTOR_WEIGHTS = {
    "fundamental": 0.25,
    "quality": 0.15,
    "valuation": 0.20,
    "technical": 0.15,
    "risk": 0.15,
    "sector_relative": 0.10,
}
# TRADER profile: momentum-biased — technical weighted up ~2x (15%→30%),
# fundamental/quality weighted down (they lag price action), risk (which
# includes beta/volatility) weighted up slightly (17%), valuation and
# sector-relative left unchanged. Sums to 1.0, same as INVESTOR_WEIGHTS.
TRADER_WEIGHTS = {
    "fundamental": 0.15,
    "quality": 0.08,
    "valuation": 0.20,
    "technical": 0.30,
    "risk": 0.17,
    "sector_relative": 0.10,
}


def calculate_institutional_ratings(
    stock: Dict[str, Any], 
    prices_list: List[float], 
    sector_avgs: Dict[str, float],
    news_list: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Harden Institutional Stock Rating Engine v2 with Quality, Trend, and Event scores.
    """
    roe = stock.get("roe") if stock.get("roe") is not None else 15.0
    roce = stock.get("roce") if stock.get("roce") is not None else roe * 0.9
    de = stock.get("debt_equity") if stock.get("debt_equity") is not None else 0.5
    pe = stock.get("pe_ratio") if stock.get("pe_ratio") is not None else 20.0
    pb = stock.get("pb_ratio") if stock.get("pb_ratio") is not None else 3.0
    
    peg = stock.get("peg_ratio") if stock.get("peg_ratio") is not None else 1.5
    ev_ebitda = stock.get("ev_ebitda") if stock.get("ev_ebitda") is not None else 15.0
    op_margin = stock.get("operating_margin") if stock.get("operating_margin") is not None else 0.15
    net_margin = stock.get("net_margin") if stock.get("net_margin") is not None else 0.10
    rev_growth = stock.get("revenue_growth") if stock.get("revenue_growth") is not None else 0.12
    profit_growth = stock.get("profit_growth") if stock.get("profit_growth") is not None else 0.10
    fcf = stock.get("free_cashflow") if stock.get("free_cashflow") is not None else 100_000_000.0
    held_promoters = stock.get("held_promoters") if stock.get("held_promoters") is not None else 0.50
    interest_coverage = stock.get("interest_coverage") if stock.get("interest_coverage") is not None else 4.0
    
    cagr_1 = stock.get("cagr_1y") or 0.15
    cagr_3 = stock.get("cagr_3y") or 0.15
    
    # ─── A. FUNDAMENTAL SCORE (0-100) ───
    # Calibrated strictness: 15% ROE yields 49.5 pts. Negative profit growth directly penalizes.
    roe_score = min(100.0, max(0.0, roe * 3.3))
    roce_score = min(100.0, max(0.0, roce * 4.0))
    op_margin_score = min(100.0, max(0.0, op_margin * 333.0))
    net_margin_score = min(100.0, max(0.0, net_margin * 500.0))
    rev_growth_score = min(100.0, max(0.0, rev_growth * 400.0))
    profit_growth_score = min(100.0, max(0.0, profit_growth * 400.0)) if profit_growth >= 0 else max(0.0, 30.0 + profit_growth * 100.0)
    fcf_score = 100.0 if fcf > 0 else 10.0
    consistency_score = 100.0 - min(50.0, abs(cagr_1 - cagr_3) * 200.0)
    
    fundamental_score = (
        0.15 * roe_score +
        0.15 * roce_score +
        0.15 * op_margin_score +
        0.10 * net_margin_score +
        0.15 * rev_growth_score +
        0.15 * profit_growth_score +
        0.10 * fcf_score +
        0.05 * consistency_score
    )
    fundamental_score = round(max(0.0, min(100.0, fundamental_score)), 1)
    
    # ─── B. QUALITY SCORE (0-100) [NEW] ───
    # Evaluates consistency, cash generation efficiency, and leverage sustainability
    margin_stability = min(100.0, max(0.0, op_margin * 400.0))
    cash_conversion = 100.0 if (fcf > 0 and rev_growth > 0) else (40.0 if fcf > 0 else 10.0)
    debt_quality = max(0.0, 100.0 - de * 60.0)
    returns_stability = max(20.0, 100.0 - abs(cagr_1 - cagr_3) * 150.0)
    
    quality_score = 0.30 * margin_stability + 0.30 * cash_conversion + 0.20 * debt_quality + 0.20 * returns_stability
    quality_score = round(max(0.0, min(100.0, quality_score)), 1)
    
    # ─── C. VALUATION SCORE (0-100) ───
    # Massive penalty for loss-makers (PE<=0 gets 0). More sensitive relative deviations.
    sect_pe = sector_avgs.get("pe", 22.0)
    sect_pb = sector_avgs.get("pb", 3.0)
    
    if pe <= 0:
        pe_score = 0.0
    elif pe <= sect_pe:
        pe_score = 100.0 - (pe / sect_pe) * 35.0
    else:
        pe_score = max(5.0, 65.0 - ((pe - sect_pe) / sect_pe) * 60.0)
        if pe > sect_pe * 1.8:
            pe_score = max(0.0, pe_score - 25.0)
            
    if pb <= 0:
        pb_score = 0.0
    elif pb <= sect_pb:
        pb_score = 100.0 - (pb / sect_pb) * 35.0
    else:
        pb_score = max(5.0, 65.0 - ((pb - sect_pb) / sect_pb) * 60.0)
        if pb > sect_pb * 1.8:
            pb_score = max(0.0, pb_score - 25.0)
            
    if ev_ebitda <= 10.0:
        ev_score = 90.0
    elif ev_ebitda >= 25.0:
        ev_score = 15.0
    else:
        ev_score = 90.0 - (ev_ebitda - 10.0) * 5.0
        
    if peg <= 1.0:
        peg_score = 95.0
    elif peg >= 2.0:
        peg_score = 15.0
    else:
        peg_score = 95.0 - (peg - 1.0) * 80.0
        
    valuation_score = 0.40 * pe_score + 0.20 * pb_score + 0.20 * ev_score + 0.20 * peg_score
    valuation_score = round(max(0.0, min(100.0, valuation_score)), 1)
    
    # ─── D. TECHNICAL SCORE (0-100) & TREND STRUCTURE ───
    # Cap technical score for BEARISH swing structure
    trend_structure = detect_trend_structure(prices_list)
    tech = calculate_technical_indicators(prices_list)
    rsi = tech["rsi"]
    macd_bullish = tech["macd_bullish"]
    dma_50 = tech["dma_50"]
    dma_200 = tech["dma_200"]
    latest_price = tech["latest"]
    
    if 45 <= rsi <= 60:
        rsi_score = 95.0
    elif rsi > 70:
        rsi_score = max(5.0, 95.0 - (rsi - 70.0) * 5.0)
    else:
        rsi_score = max(10.0, 30.0 + (rsi - 20.0) * 2.0)
        
    macd_score = 100.0 if macd_bullish else 20.0
    dma_50_score = 100.0 if (dma_50 and latest_price >= dma_50) else 25.0
    dma_200_score = 100.0 if (dma_200 and latest_price >= dma_200) else 15.0
    trend_align = 100.0 if (dma_50 and dma_200 and dma_50 > dma_200) else 20.0
    
    technical_score = 0.20 * rsi_score + 0.20 * macd_score + 0.20 * dma_50_score + 0.20 * dma_200_score + 0.20 * trend_align
    if trend_structure == "BEARISH":
        technical_score = min(45.0, technical_score)
    technical_score = round(max(0.0, min(100.0, technical_score)), 1)
    
    # ─── E. RISK SCORE (0-100) & EVENT SCORE ───
    # Incorporates promoter risk, vol risk (beta), and dynamic news event classification
    if de <= 0.4:
        de_risk = 100.0
    elif de >= 1.5:
        de_risk = 10.0
    else:
        de_risk = 100.0 - (de - 0.4) * 82.0
        
    if interest_coverage >= 5.0:
        ic_risk = 100.0
    elif interest_coverage <= 1.5:
        ic_risk = 5.0
    else:
        ic_risk = 100.0 - (5.0 - interest_coverage) * 27.0
        
    promoter_risk = 100.0 if held_promoters >= 0.45 else 40.0
    
    # Beta volatility risk
    vol_risk = max(10.0, 100.0 - min(90.0, (stock.get("target_beta") or 1.0) * 45.0))
    event_score = calculate_event_score(news_list)
    
    risk_score = 0.30 * de_risk + 0.20 * ic_risk + 0.20 * promoter_risk + 0.15 * vol_risk + 0.15 * event_score
    risk_score = round(max(0.0, min(100.0, risk_score)), 1)
    
    # ─── F. SECTOR RELATIVE SCORE (0-100) ───
    sect_roe = sector_avgs.get("roe", 15.0)
    sect_de = sector_avgs.get("de", 0.5)
    sect_cagr = sector_avgs.get("cagr_3y", 0.15)
    
    if roe >= sect_roe:
        roe_rel = min(100.0, 70.0 + (roe - sect_roe) * 2.5)
    else:
        roe_rel = max(5.0, 70.0 - (sect_roe - roe) * 2.5)
        
    if de <= sect_de:
        de_rel = min(100.0, 70.0 + (sect_de - de) * 35.0)
    else:
        de_rel = max(5.0, 70.0 - (de - sect_de) * 35.0)
        
    stock_cagr = stock.get("cagr_3y") or 0.15
    if stock_cagr >= sect_cagr:
        growth_rel = min(100.0, 70.0 + (stock_cagr - sect_cagr) * 120.0)
    else:
        growth_rel = max(5.0, 70.0 - (sect_cagr - stock_cagr) * 120.0)
        
    sector_relative_score = (roe_rel + de_rel + growth_rel) / 3.0
    sector_relative_score = round(max(0.0, min(100.0, sector_relative_score)), 1)
    
    # ─── FINAL ALPHA SCORE (INVESTOR-WEIGHTED MODEL) ───
    pillars = {
        "fundamental": fundamental_score,
        "quality": quality_score,
        "valuation": valuation_score,
        "technical": technical_score,
        "risk": risk_score,
        "sector_relative": sector_relative_score,
    }

    def _weighted_sum(weights: Dict[str, float]) -> float:
        return sum(pillars[k] * w for k, w in weights.items())

    # OVERHEAT PENALTIES — same signals apply to both profiles (RSI/PE/DMA
    # blow-off risk isn't investor-vs-trader specific, it's just risk).
    def _apply_overheat_penalty(score: float) -> float:
        if rsi > 75.0:
            score -= 10.0
        if pe > sect_pe * 1.8:
            score -= 15.0
        if dma_200 and latest_price > dma_200 * 1.30:
            score -= 10.0
        return round(max(0.0, min(100.0, score)), 1)

    final_score = _apply_overheat_penalty(_weighted_sum(INVESTOR_WEIGHTS))
    trader_final_score = _apply_overheat_penalty(_weighted_sum(TRADER_WEIGHTS))
    
    # ─── CONFIDENCE ENGINE CALIBRATION ───
    filled_fields = sum(1 for v in [stock.get("roe"), stock.get("pe_ratio"), stock.get("debt_equity"), stock.get("pb_ratio")] if v is not None)
    completeness = (filled_fields / 4.0) * 100.0
    
    divergence_penalty = 0.0
    divergence = abs(fundamental_score - technical_score)
    if divergence > 40.0:
        divergence_penalty = 25.0
    elif divergence > 25.0:
        divergence_penalty = 10.0
        
    sector_penalty = 0.0 if sector_avgs.get("is_real", True) else 15.0
    
    # News conflict check
    news_penalty = 0.0
    if news_list:
        import re
        pos_pat = re.compile(r'\b(new order|bags contract|secured contract|secured order|capacity expansion|expansion plan|approved|product launch|launches)\b', re.IGNORECASE)
        neg_pat = re.compile(r'\b(promoter sells|promoter selling|insider sale|earnings miss|profit falls|debt rises|debt increase|investigation|probe|downgrade|governance)\b', re.IGNORECASE)
        pos_f = any(pos_pat.search(f"{n.get('title','')} {n.get('summary','')}".lower()) for n in news_list)
        neg_f = any(neg_pat.search(f"{n.get('title','')} {n.get('summary','')}".lower()) for n in news_list)
        if pos_f and neg_f:
            news_penalty = 15.0
            
    confidence_score = completeness - divergence_penalty - sector_penalty - news_penalty
    confidence_score = round(max(10.0, min(100.0, confidence_score)), 0)
    
    # Verdict Mappings
    def map_verdict(val: float) -> str:
        if val >= 74.0: return "STRONG BUY"
        if val >= 66.0: return "BUY"
        if val >= 56.0: return "HOLD"
        if val >= 46.0: return "REDUCE"
        return "AVOID"
        
    # investor_verdict and trader_verdict are now genuinely distinct: same
    # map_verdict() thresholds, but computed from two differently-weighted
    # sums over the same six pillars (INVESTOR_WEIGHTS vs TRADER_WEIGHTS
    # above) rather than both reading the same final_score.
    investor_verdict = map_verdict(final_score)
    trader_verdict = map_verdict(trader_final_score)

    return {
        "fundamental_score": fundamental_score,
        "quality_score": quality_score,
        "valuation_score": valuation_score,
        "technical_score": technical_score,
        "risk_score": risk_score,
        "sector_relative_score": sector_relative_score,
        "event_score": event_score,
        "final_score": final_score,
        "trader_score": trader_final_score,
        "confidence_score": confidence_score,
        "investor_verdict": investor_verdict,
        "trader_verdict": trader_verdict,
        "trend_structure": trend_structure
    }

def calculate_alpha_score(stock: Dict[str, Any], cagr_1y: float, cagr_3y: float) -> float:
    """
    Backward-compatible legacy wrapper for calculate_alpha_score.
    """
    prices = [100.0] * 50
    sector_avgs = {"pe": 22.0, "pb": 3.0, "roe": 15.0, "de": 0.5, "cagr_3y": 0.15}
    stock_dict = {**stock, "cagr_1y": cagr_1y, "cagr_3y": cagr_3y}
    ratings = calculate_institutional_ratings(stock_dict, prices, sector_avgs)
    return ratings["final_score"]

def fetch_ticker_data_yfinance(symbol: str) -> Tuple[Optional[pd.DataFrame], Optional[Dict[str, Any]], Optional[List[Any]]]:
    """
    Downloads historical close prices and stock metadata from Yahoo Finance.
    Handles NSE suffix (.NS) for Indian equities.
    Parallelizes calls using ThreadPoolExecutor and enforces a strict 4.0s timeout.
    """
    import pandas as pd
    import yfinance as yf
    import requests
    import concurrent.futures

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    
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
        logger.info(f"Querying yfinance for symbol {yf_symbol}...")
        ticker = yf.Ticker(yf_symbol, session=session)
        
        # Parallel fetch using concurrent.futures to fetch hist (3y max), info, and news concurrently!
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            def get_hist():
                for period in ("3y", "2y", "1y"):
                    h = ticker.history(period=period)
                    if not h.empty:
                        logger.info(f"Got {len(h)} rows for {yf_symbol} with period={period}")
                        return h
                return pd.DataFrame()
            
            def get_info():
                try:
                    return ticker.info
                except Exception as info_err:
                    logger.warning(f"Could not retrieve ticker info for {yf_symbol}: {info_err}")
                    return {}
            
            def get_news():
                try:
                    return ticker.news or []
                except Exception as news_err:
                    logger.warning(f"Could not retrieve ticker news for {yf_symbol}: {news_err}")
                    return []
                    
            future_hist = executor.submit(get_hist)
            future_info = executor.submit(get_info)
            future_news = executor.submit(get_news)
            
            hist = future_hist.result()
            info = future_info.result()
            news = future_news.result()
            
        return hist, info, news
    except Exception as e:
        logger.error(f"yfinance query failed for symbol {symbol}: {e}")
        return None, None, None


def parse_briefing_sections(briefing: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not briefing:
        return None, None, None
    def extract_section(text: str, heading: str) -> Optional[str]:
        parts = text.split(f"### {heading}")
        if len(parts) < 2:
            return None
        return parts[1].split("###")[0].strip()
        
    bull = extract_section(briefing, "Investment Thesis") or extract_section(briefing, "Bull Case")
    bear = extract_section(briefing, "Risk Factors") or extract_section(briefing, "Bear Case")
    rat = extract_section(briefing, "Final Verdict") or extract_section(briefing, "Verdict Rationale")
    
    return bull, bear, rat

# Distributed ingestion lock — an in-memory set doesn't work across separate
# Vercel invocations (each gets a fresh process), so single-flight dedup must
# live in Redis instead.
_DYNAMIC_INGEST_LOCK_TTL = 120
_DYNAMIC_INGEST_LOCK_KEY = "ingesting:{}"

async def dynamic_ingest_stock(symbol: str, db: AsyncSession) -> Dict[str, Any]:
    import asyncio
    symbol = symbol.upper().strip()

    from app.core.redis import redis_client
    lock_key = _DYNAMIC_INGEST_LOCK_KEY.format(symbol)

    try:
        acquired = await redis_client.set_nx(lock_key, "1", ex=_DYNAMIC_INGEST_LOCK_TTL)
    except Exception as e:
        logger.warning(f"[DynamicIngest] Redis lock check failed for {symbol}: {e} — proceeding anyway")
        acquired = True

    if not acquired:
        logger.info(f"[DynamicIngest] {symbol} is already being ingested elsewhere — skipping duplicate trigger")
        return {"status": "already_exists", "symbol": symbol}

    # Write initial progress to Redis so the frontend can poll status
    try:
        await redis_client.setex(
            f"ingest_progress:{symbol}", 120,
            '{"stage": "starting", "progress": 0}'
        )
    except Exception:
        pass

    try:
        # Hard 55-second timeout — keeps us well within Vercel's 60s limit
        result = await asyncio.wait_for(
            _dynamic_ingest_stock_internal(symbol, db),
            timeout=55.0
        )
        # Write completion progress
        try:
            await redis_client.setex(
                f"ingest_progress:{symbol}", 120,
                '{"stage": "completed", "progress": 100}'
            )
            if result.get("status") in ("ingested", "already_exists"):
                await redis_client.setex(f"stock_ready:{symbol}", 3600, "1")
        except Exception:
            pass
        return result
    except asyncio.TimeoutError:
        logger.error(f"[DynamicIngest] Ingestion for {symbol} timed out after 55s")
        try:
            await redis_client.setex(
                f"ingest_progress:{symbol}", 60,
                '{"stage": "timeout", "progress": -1}'
            )
        except Exception:
            pass
        return {"status": "error", "symbol": symbol, "reason": "timeout"}
    except Exception as exc:
        logger.error(f"[DynamicIngest] Ingestion for {symbol} failed: {exc}")
        return {"status": "error", "symbol": symbol, "reason": str(exc)}
    finally:
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass

async def _dynamic_ingest_stock_internal(symbol: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Dynamically fetches, computes, and persists a stock record for any NSE-listed symbol.
    Called when a user searches or navigates to a stock not in the local database.

    Returns a dict with status: 'ingested' | 'already_exists' | 'not_found' | 'error'
    """
    import numpy as np
    import pandas as pd

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
    hist, info, news = await loop.run_in_executor(None, lambda: fetch_ticker_data_yfinance(symbol))

    if hist is None or hist.empty:
        # Try BSE suffix as fallback
        logger.warning(f"[DynamicIngest] NSE lookup failed for {symbol}. Trying BSE suffix (.BO)...")
        def fetch_bse():
            import yfinance as yf
            import requests
            import concurrent.futures
            
            session = requests.Session()
            session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            
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
                ticker = yf.Ticker(f"{symbol}.BO", session=session)
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    def get_hist_bse():
                        for period in ("3y", "2y", "1y"):
                            h = ticker.history(period=period)
                            if not h.empty:
                                return h
                        return pd.DataFrame()
                    def get_info_bse():
                        try: return ticker.info
                        except Exception: return {}
                    def get_news_bse():
                        try: return ticker.news or []
                        except Exception: return []
                    
                    fut_h = executor.submit(get_hist_bse)
                    fut_i = executor.submit(get_info_bse)
                    fut_n = executor.submit(get_news_bse)
                    
                    h = fut_h.result()
                    i = fut_i.result()
                    n = fut_n.result()
                return h, i, n
            except Exception as e:
                logger.error(f"[DynamicIngest] BSE fallback failed for {symbol}: {e}")
                return None, None, None

        hist, info, news = await loop.run_in_executor(None, fetch_bse)

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
    sector = SECTOR_OVERRIDES.get(symbol, info.get("sector") or "Unknown")
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

    peg_raw = info.get("trailingPegRatio") or info.get("pegRatio")
    peg_ratio = round(float(peg_raw), 2) if peg_raw is not None else None
    
    ev_raw = info.get("enterpriseToEbitda")
    ev_ebitda = round(float(ev_raw), 2) if ev_raw is not None else None
    
    op_raw = info.get("operatingMargins")
    operating_margin = round(float(op_raw), 4) if op_raw is not None else None
    
    net_raw = info.get("profitMargins")
    net_margin = round(float(net_raw), 4) if net_raw is not None else None
    
    rev_raw = info.get("revenueGrowth")
    revenue_growth = round(float(rev_raw), 4) if rev_raw is not None else None
    
    profit_raw = info.get("earningsGrowth")
    profit_growth = round(float(profit_raw), 4) if profit_raw is not None else None
    
    fcf_raw = info.get("freeCashflow")
    free_cashflow = round(float(fcf_raw), 2) if fcf_raw is not None else None
    
    prom_raw = info.get("heldPercentPromoters")
    held_promoters = round(float(prom_raw), 4) if prom_raw is not None else None

    # 4. Build price history from historical data
    end_date = date.today()
    start_date = end_date - timedelta(days=int(3.0 * 365.25))

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

    # 6. Calculate Alpha Score and ratings
    stock_meta = {
        "roe": roe or 15.0,
        "debt_equity": debt_equity or 0.5,
        "pe_ratio": pe_ratio or 20.0,
        "pb_ratio": pb_ratio or 3.0,
        "target_beta": computed_beta,
        "peg_ratio": peg_ratio,
        "ev_ebitda": ev_ebitda,
        "operating_margin": operating_margin,
        "net_margin": net_margin,
        "revenue_growth": revenue_growth,
        "profit_growth": profit_growth,
        "free_cashflow": free_cashflow,
        "held_promoters": held_promoters,
        "cagr_1y": cagr_1y,
        "cagr_3y": cagr_3y
    }
    sector_avgs = await get_sector_averages(sector, db)
    ratings = calculate_institutional_ratings(
        stock_meta, 
        [p.close for p in prices_to_insert] if prices_to_insert else [100.0] * 50, 
        sector_avgs,
        news_list=news
    )
    alpha_score = ratings["final_score"]

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
        
        # Populate ratings columns
        existing.fundamental_score = ratings["fundamental_score"]
        existing.valuation_score = ratings["valuation_score"]
        existing.technical_score = ratings["technical_score"]
        existing.risk_score = ratings["risk_score"]
        existing.sector_relative_score = ratings["sector_relative_score"]
        existing.confidence_score = ratings["confidence_score"]
        existing.investor_verdict = ratings["investor_verdict"]
        existing.trader_verdict = ratings["trader_verdict"]
        existing.quality_score = ratings["quality_score"]
        existing.event_score = ratings["event_score"]
        existing.trend_structure = ratings["trend_structure"]
        
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
            
            # Populate ratings columns
            fundamental_score = ratings["fundamental_score"],
            valuation_score = ratings["valuation_score"],
            technical_score = ratings["technical_score"],
            risk_score = ratings["risk_score"],
            sector_relative_score = ratings["sector_relative_score"],
            confidence_score = ratings["confidence_score"],
            investor_verdict = ratings["investor_verdict"],
            trader_verdict = ratings["trader_verdict"],
            quality_score = ratings["quality_score"],
            event_score = ratings["event_score"],
            trend_structure = ratings["trend_structure"],
            
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
        await db.execute(delete(StockPriceHistory).where(StockPriceHistory.symbol == symbol))
        db.add_all(prices_to_insert)

    await db.commit()
    
    # Invalidate Redis cache for this stock after dynamic ingestion
    try:
        from app.core.redis import redis_client
        await redis_client.delete(
            f"stock_detail:{symbol}",
            f"stock_master:{symbol}",
            f"stock_history:{symbol}",
            f"stock_briefing:{symbol}",
            f"stock_search:{symbol.lower()}",
        )
        await redis_client.delete_pattern("stocks_list:*")
    except Exception as e:
        logger.warning(f"Failed to invalidate Redis cache for {symbol}: {e}")
    
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


# ═══════════════════════════════════════════════════════════════════════════
# PROGRESSIVE DISCOVERY PIPELINE v3 — Hobby-plan-safe step functions
# Each function completes within 8s (Vercel Hobby 10s limit).
# Flow: quick_discover → step1_history → step2_analytics → step3_briefing
# ═══════════════════════════════════════════════════════════════════════════

async def quick_discover_stock(symbol: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Stage 0 — Quick Discovery (< 5s):
    Fetches only yfinance .info (no history), extracts company name, sector,
    current price, exchange, and writes a DISCOVERED record to DB.
    Returns immediately so the frontend can render a real header/price badge.
    """
    import asyncio
    import json
    from app.core.redis import redis_client

    symbol = symbol.upper().strip()
    logger.info(f"[QuickDiscover] Starting quick discovery for {symbol}")

    loop = asyncio.get_event_loop()

    def _fetch_info(ticker_symbol: str) -> Dict:
        import yfinance as yf
        import requests

        sess = requests.Session()
        sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

        class _TimeoutAdapter(requests.adapters.HTTPAdapter):
            def send(self, request, **kwargs):
                kwargs["timeout"] = 5.0
                return super().send(request, **kwargs)

        a = _TimeoutAdapter()
        sess.mount("https://", a)
        sess.mount("http://", a)
        try:
            return yf.Ticker(ticker_symbol, session=sess).info or {}
        except Exception as e:
            logger.warning(f"[QuickDiscover] .info failed for {ticker_symbol}: {e}")
            return {}

    info = await loop.run_in_executor(None, lambda: _fetch_info(f"{symbol}.NS"))
    exchange = "NSE"
    if not info or not info.get("regularMarketPrice"):
        logger.warning(f"[QuickDiscover] NSE miss for {symbol}, trying BSE...")
        info = await loop.run_in_executor(None, lambda: _fetch_info(f"{symbol}.BO"))
        exchange = "BSE"

    current_price = info.get("regularMarketPrice") if info else None
    if not current_price:
        logger.warning(f"[QuickDiscover] No price found for {symbol}")
        return {"status": "not_found", "symbol": symbol}

    company_name = info.get("longName") or info.get("shortName") or symbol
    raw_sector = info.get("sector") or "Unknown"
    sector = SECTOR_OVERRIDES.get(symbol, raw_sector) or "Unknown"
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
    debt_equity = round(de_raw / 100.0 if de_raw and de_raw > 3.0 else de_raw, 2) if de_raw is not None else None
    dy_raw = info.get("dividendYield")
    dividend_yield = round(float(dy_raw) * 100.0, 2) if dy_raw is not None else None

    check_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    existing = check_q.scalar_one_or_none()

    if existing:
        # Update existing record (covers both DISCOVERING skeletons and DISCOVERED records)
        existing.company_name = company_name
        existing.sector = sector
        existing.industry = industry
        existing.isin = isin
        existing.market_cap = market_cap
        existing.pe_ratio = pe_ratio
        existing.pb_ratio = pb_ratio
        existing.roe = roe
        existing.debt_equity = debt_equity
        existing.dividend_yield = dividend_yield
        existing.current_price = current_price
        existing.exchange = exchange
        existing.ingestion_status = "DISCOVERED"
        existing.ai_summary = "Analytics are being computed..."
        await db.commit()
        await db.refresh(existing)
    else:
        existing = StockMaster(
            symbol=symbol, company_name=company_name, sector=sector,
            industry=industry, isin=isin, market_cap=market_cap,
            pe_ratio=pe_ratio, pb_ratio=pb_ratio, roe=roe,
            debt_equity=debt_equity, dividend_yield=dividend_yield,
            current_price=current_price, exchange=exchange,
            ingestion_status="DISCOVERED",
            ai_summary="Analytics are being computed...",
        )
        db.add(existing)
        try:
            await db.commit()
            await db.refresh(existing)
        except Exception as e:
            await db.rollback()
            logger.error(f"[QuickDiscover] DB commit failed for {symbol}: {e}")
            return {"status": "error", "symbol": symbol, "reason": str(e)}

    # Sync to search index
    from app.core.database import is_sqlite
    from sqlalchemy import text
    try:
        await db.execute(text("DELETE FROM stock_search_index WHERE symbol = :symbol"), {"symbol": symbol})
        upsert_sql = (
            "INSERT INTO stock_search_index (symbol, company_name, exchange) VALUES (:s, :n, :e)"
            if is_sqlite else
            "INSERT INTO stock_search_index (symbol, company_name, exchange) VALUES (:s, :n, :e) ON CONFLICT (symbol) DO UPDATE SET company_name=:n, exchange=:e"
        )
        await db.execute(text(upsert_sql), {"s": symbol, "n": company_name, "e": exchange})
        await db.commit()
    except Exception as e:
        logger.warning(f"[QuickDiscover] search index sync failed: {e}")

    try:
        progress = json.dumps({
            "stage": "DISCOVERED", "progress": 10,
            "available_sections": ["meta"],
            "pending_sections": ["chart", "metrics", "briefing", "news"],
            "stage_message": "Downloading historical price data..."
        })
        await redis_client.setex(f"ingest_progress:{symbol}", 3600, progress)
    except Exception as e:
        logger.warning(f"[QuickDiscover] Redis progress write failed: {e}")

    logger.info(f"[QuickDiscover] {symbol} → {company_name} ({exchange}) @ ₹{current_price}")
    return {
        "status": "discovered", "symbol": symbol, "company_name": company_name,
        "sector": sector, "industry": industry, "current_price": current_price,
        "exchange": exchange, "market_cap": market_cap, "isin": isin,
    }


async def ingest_step1_history(symbol: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Step 1 — History Download (< 8s):
    Downloads 3Y price history (NSE → BSE fallback), writes StockPriceHistory rows.
    Transitions ingestion_status: DISCOVERED → INGESTING.
    """
    import asyncio
    import json
    import numpy as np
    import pandas as pd
    from app.core.redis import redis_client

    symbol = symbol.upper().strip()
    logger.info(f"[IngestStep1] Downloading history for {symbol}")

    check_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = check_q.scalar_one_or_none()
    if not stock:
        return {"status": "error", "reason": "not_found"}

    stock.ingestion_status = "INGESTING"
    await db.commit()

    loop = asyncio.get_event_loop()
    hist, info, news = await loop.run_in_executor(None, lambda: fetch_ticker_data_yfinance(symbol))

    if hist is None or hist.empty:
        logger.warning(f"[IngestStep1] NSE miss for {symbol}, trying BSE fallback...")
        def _bse():
            import yfinance as yf, requests, concurrent.futures
            s = requests.Session()
            s.headers.update({"User-Agent": "Mozilla/5.0"})
            class A(requests.adapters.HTTPAdapter):
                def send(self, r, **k): k["timeout"]=5.0; return super().send(r,**k)
            s.mount("https://",A()); s.mount("http://",A())
            t = yf.Ticker(f"{symbol}.BO", session=s)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                fh = ex.submit(lambda: next((t.history(period=p) for p in ("3y","2y","1y") if not t.history(period=p).empty), pd.DataFrame()))
                fi = ex.submit(lambda: t.info or {})
                return fh.result(), fi.result(), []
        hist, info, _ = await loop.run_in_executor(None, _bse)

    if hist is None or hist.empty:
        stock.ingestion_status = "FAILED"
        stock.sector = "Invalid"
        await db.commit()
        logger.error(f"[IngestStep1] All providers failed for {symbol}")
        return {"status": "failed", "symbol": symbol}

    end_date = date.today()
    start_date = end_date - timedelta(days=int(3.0 * 365.25))
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
        prices_to_insert.append(StockPriceHistory(symbol=symbol, date=p_date, close=round(close_val, 2)))

    if prices_to_insert:
        await db.execute(delete(StockPriceHistory).where(StockPriceHistory.symbol == symbol))
        db.add_all(prices_to_insert)

    if info and info.get("regularMarketPrice") and not stock.current_price:
        stock.current_price = info.get("regularMarketPrice")

    await db.commit()
    logger.info(f"[IngestStep1] {symbol}: wrote {len(prices_to_insert)} price rows")

    try:
        progress = json.dumps({
            "stage": "INGESTING", "progress": 40,
            "available_sections": ["meta", "chart"],
            "pending_sections": ["metrics", "briefing", "news"],
            "stage_message": "Computing Alpha Score and analytics..."
        })
        await redis_client.setex(f"ingest_progress:{symbol}", 3600, progress)
        await redis_client.delete(f"stock_history:{symbol}")
    except Exception as e:
        logger.warning(f"[IngestStep1] Redis update failed: {e}")

    return {"status": "ingesting", "symbol": symbol, "price_rows": len(prices_to_insert)}


async def ingest_step2_analytics(symbol: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Step 2 — Analytics (< 5s):
    Reads price rows from DB, computes CAGR 1/3/5Y, beta, and all
    alpha sub-scores. Transitions: INGESTING → ANALYTICS_RUNNING.
    """
    import json
    import pandas as pd
    from app.core.redis import redis_client

    symbol = symbol.upper().strip()
    logger.info(f"[IngestStep2] Computing analytics for {symbol}")

    check_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = check_q.scalar_one_or_none()
    if not stock:
        return {"status": "error", "reason": "not_found"}

    stock.ingestion_status = "ANALYTICS_RUNNING"
    await db.commit()

    hist_q = await db.execute(
        select(StockPriceHistory.date, StockPriceHistory.close)
        .where(StockPriceHistory.symbol == symbol)
        .order_by(StockPriceHistory.date.asc())
    )
    rows = hist_q.all()

    if len(rows) < 30:
        logger.warning(f"[IngestStep2] {symbol} has < 30 price rows — using defaults")
        prices_list = [100.0] * 50
        cagr_1y = cagr_3y = cagr_5y = 0.0
    else:
        prices_list = [float(r.close) for r in rows]
        prices_df = pd.DataFrame({"date": [r.date for r in rows], "close": prices_list})
        prices_df["date"] = pd.to_datetime(prices_df["date"])
        prices_df = prices_df.sort_values("date").reset_index(drop=True)

        def get_cagr(years: int) -> float:
            latest_row = prices_df.iloc[-1]
            target_d = latest_row["date"] - pd.DateOffset(years=years)
            diffs = (prices_df["date"] - target_d).abs()
            idx = diffs.idxmin()
            best_row = prices_df.loc[idx]
            if diffs.min().days > 30:
                return 0.0
            days = (latest_row["date"] - best_row["date"]).days
            years_act = days / 365.25
            if years_act < (years * 0.9):
                return 0.0
            return (latest_row["close"] / best_row["close"]) ** (1.0 / years_act) - 1.0

        cagr_1y = get_cagr(1)
        cagr_3y = get_cagr(3)
        cagr_5y = get_cagr(5)

    beta = stock.beta or 1.0
    sector_avgs = await get_sector_averages(stock.sector or "Unknown", db)
    stock_meta = {
        "roe": stock.roe or 15.0, "debt_equity": stock.debt_equity or 0.5,
        "pe_ratio": stock.pe_ratio or 20.0, "pb_ratio": stock.pb_ratio or 3.0,
        "target_beta": beta, "cagr_1y": cagr_1y, "cagr_3y": cagr_3y,
        "peg_ratio": None, "ev_ebitda": None, "operating_margin": None,
        "net_margin": None, "revenue_growth": None, "profit_growth": None,
        "free_cashflow": None, "held_promoters": None,
    }
    ratings = calculate_institutional_ratings(stock_meta, prices_list, sector_avgs, news_list=[])

    stock.cagr_1y = cagr_1y
    stock.cagr_3y = cagr_3y
    stock.cagr_5y = cagr_5y
    stock.beta = round(beta, 2)
    stock.alpha_score = ratings["final_score"]
    stock.fundamental_score = ratings["fundamental_score"]
    stock.valuation_score = ratings["valuation_score"]
    stock.technical_score = ratings["technical_score"]
    stock.risk_score = ratings["risk_score"]
    stock.sector_relative_score = ratings["sector_relative_score"]
    stock.confidence_score = ratings["confidence_score"]
    stock.quality_score = ratings["quality_score"]
    stock.event_score = ratings["event_score"]
    stock.investor_verdict = ratings["investor_verdict"]
    stock.trader_verdict = ratings["trader_verdict"]
    stock.trend_structure = ratings["trend_structure"]
    await db.commit()

    logger.info(f"[IngestStep2] {symbol}: alpha={ratings['final_score']}, cagr_3y={cagr_3y:.2%}")

    try:
        progress = json.dumps({
            "stage": "ANALYTICS_RUNNING", "progress": 70,
            "available_sections": ["meta", "chart", "metrics"],
            "pending_sections": ["briefing", "news"],
            "stage_message": "Generating AI Equity Intelligence Briefing..."
        })
        await redis_client.setex(f"ingest_progress:{symbol}", 3600, progress)
        await redis_client.delete(f"stock_detail:{symbol}", f"stock_master:{symbol}")
    except Exception as e:
        logger.warning(f"[IngestStep2] Redis update failed: {e}")

    return {
        "status": "analytics_running", "symbol": symbol,
        "alpha_score": ratings["final_score"], "cagr_3y": cagr_3y,
    }


async def ingest_step3_briefing(symbol: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Step 3 — AI Briefing (< 9s):
    Generates AI briefing via Groq/Llama. Writes ai_summary, bull/bear case.
    Transitions ingestion_status → READY. Busts all Redis caches.
    """
    import json
    from app.core.redis import redis_client

    symbol = symbol.upper().strip()
    logger.info(f"[IngestStep3] Generating briefing for {symbol}")

    check_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
    stock = check_q.scalar_one_or_none()
    if not stock:
        return {"status": "error", "reason": "not_found"}

    briefing_text = None
    try:
        from app.services.ai_agent import generate_stock_briefing
        # NOTE: this previously called generate_stock_briefing(symbol, db) — a
        # signature mismatch (the function expects a stock_data dict, not a
        # symbol string + session) that silently threw and was swallowed by
        # this except block, so the main QStash ingestion pipeline never
        # actually produced a briefing via this path. Fixed to build the
        # stock_data dict the function actually expects.
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
        briefing_result = await generate_stock_briefing(stock_dict)
        briefing_text = briefing_result.get("text") if isinstance(briefing_result, dict) else briefing_result
        logger.info(f"[IngestStep3] {symbol}: briefing ready ({len(briefing_text or '')} chars)")
    except Exception as e:
        logger.warning(f"[IngestStep3] briefing failed for {symbol}: {e}")
        briefing_result = None

    if briefing_text:
        bull, bear, rationale = parse_briefing_sections(briefing_text)
        stock.ai_summary = json.dumps(briefing_result) if isinstance(briefing_result, dict) else briefing_text
        stock.bull_case = bull
        stock.bear_case = bear
        stock.verdict_rationale = rationale

    stock.ingestion_status = "READY"
    await db.commit()
    logger.info(f"[IngestStep3] {symbol}: ingestion_status → READY")

    try:
        await redis_client.delete(
            f"stock_detail:{symbol}", f"stock_master:{symbol}",
            f"stock_history:{symbol}", f"stock_briefing:{symbol}",
            f"stock_meta_split:{symbol}", f"stock_search:{symbol.lower()}",
        )
        await redis_client.delete_pattern("stocks_list:*")
        progress = json.dumps({
            "stage": "READY", "progress": 100,
            "available_sections": ["meta", "chart", "metrics", "briefing", "news"],
            "pending_sections": [],
            "stage_message": "All analytics ready."
        })
        await redis_client.setex(f"ingest_progress:{symbol}", 86400, progress)
    except Exception as e:
        logger.warning(f"[IngestStep3] Redis bust failed: {e}")

    return {"status": "ready", "symbol": symbol}


async def seed_stocks_data(db: AsyncSession):
    """
    Main background process to seed stocks metadata and generate
    deterministic daily close price timeseries in the database.
    """
    import numpy as np
    import pandas as pd

    logger.info("Initializing stock table verification & seeding...")
    
    # 5.5 years historical price range
    end_date = date.today()
    start_date = end_date - timedelta(days=int(3.0 * 365.25))
    
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
        
        # Check if already seeded with real data
        check_q = await db.execute(select(StockMaster).where(StockMaster.symbol == symbol))
        existing_stock = check_q.scalar_one_or_none()
        
        if existing_stock and existing_stock.sector != "Unknown" and existing_stock.roe is not None:
            logger.info(f"Stock {symbol} already seeded with financial data. Skipping.")
            continue
        elif existing_stock:
            logger.info(f"Stock {symbol} exists as skeleton (sector={existing_stock.sector}). Overwriting with seed data...")
            await db.delete(existing_stock)
            await db.flush()
            
        logger.info(f"Seeding stock data for symbol: {symbol}...")
        
        # Try fetching real data from Yahoo Finance
        hist, info, news = fetch_ticker_data_yfinance(symbol)
        
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

        if symbol in SECTOR_OVERRIDES:
            real_info["sector"] = SECTOR_OVERRIDES[symbol]

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
                        
        # 3. Calculate Alpha Score and ratings
        sector_avgs = await get_sector_averages(real_info["sector"], db)
        ratings = calculate_institutional_ratings(
            {**real_info, "cagr_1y": cagr_1y, "cagr_3y": cagr_3y}, 
            [p.close for p in prices_to_insert] if prices_to_insert else [100.0] * 50, 
            sector_avgs,
            news_list=news
        )
        alpha_score = ratings["final_score"]
        
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
            
            # Populate ratings columns
            fundamental_score = ratings["fundamental_score"],
            valuation_score = ratings["valuation_score"],
            technical_score = ratings["technical_score"],
            risk_score = ratings["risk_score"],
            sector_relative_score = ratings["sector_relative_score"],
            confidence_score = ratings["confidence_score"],
            investor_verdict = ratings["investor_verdict"],
            trader_verdict = ratings["trader_verdict"],
            quality_score = ratings["quality_score"],
            event_score = ratings["event_score"],
            trend_structure = ratings["trend_structure"],
            
            ai_summary="Generating Equity Intelligence Briefing in the background..."
        )
        db.add(stock_master)
        await db.flush()

        # 5. Batch insert price histories
        await db.execute(delete(StockPriceHistory).where(StockPriceHistory.symbol == symbol))
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
        
        # Invalidate Redis cache for this stock after seeding
        try:
            from app.core.redis import redis_client
            await redis_client.delete(
                f"stock_detail:{symbol}",
                f"stock_master:{symbol}",
                f"stock_history:{symbol}",
                f"stock_briefing:{symbol}",
                f"stock_search:{symbol.lower()}",
            )
        except Exception as e:
            logger.warning(f"Failed to invalidate Redis cache for {symbol}: {e}")
        
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

