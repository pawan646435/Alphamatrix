import httpx
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.core.config import settings
from app.models.fund import FundMaster, NAVHistory
from app.services.analytics import calculate_risk_metrics
from app.services.ai_agent import generate_fund_summary

logger = logging.getLogger("app.workers.ingestion")

# Simple helper to map scheme_category to our core segments
def map_category(scheme_category: str, scheme_name: str) -> Tuple[str, str]:
    """
    Maps MFapi scheme_category text to: (Category, SubCategory)
    Category must be one of: Large Cap, Mid Cap, Small Cap, Sectoral, Index
    """
    sc_lower = scheme_category.lower()
    name_lower = scheme_name.lower()
    
    sub_cat = scheme_category
    
    if "index" in sc_lower or "index" in name_lower or "etf" in sc_lower or "etf" in name_lower:
        return "Index", sub_cat
    elif "small cap" in sc_lower:
        return "Small Cap", sub_cat
    elif "mid cap" in sc_lower:
        return "Mid Cap", sub_cat
    elif "large cap" in sc_lower or "bluechip" in sc_lower:
        return "Large Cap", sub_cat
    elif "sector" in sc_lower or "thematic" in sc_lower or "pharma" in sc_lower or "it" in sc_lower or "infra" in sc_lower or "banking" in sc_lower:
        return "Sectoral", sub_cat
    
    # Fallbacks based on name if category text is generic
    if "smallcap" in name_lower:
        return "Small Cap", sub_cat
    elif "midcap" in name_lower:
        return "Mid Cap", sub_cat
    elif "bluechip" in name_lower or "largecap" in name_lower:
        return "Large Cap", sub_cat
    
    # Default to Large Cap if nothing matches (safest default)
    return "Large Cap", sub_cat

def generate_mock_pe_expense(category: str) -> Tuple[float, float]:
    """Generates realistic PE and Expense ratio values based on fund category."""
    import random
    # Seed based on category string to keep it deterministic for the same fund category
    seed_val = sum(ord(c) for c in category)
    random.seed(seed_val)
    
    if category == "Large Cap":
        pe = round(random.uniform(18.0, 24.0), 2)
        expense = round(random.uniform(0.3, 0.8), 2)
    elif category == "Mid Cap":
        pe = round(random.uniform(22.0, 29.0), 2)
        expense = round(random.uniform(0.4, 1.1), 2)
    elif category == "Small Cap":
        pe = round(random.uniform(25.0, 36.0), 2)
        expense = round(random.uniform(0.5, 1.3), 2)
    elif category == "Index":
        pe = round(random.uniform(20.0, 23.0), 2)
        expense = round(random.uniform(0.1, 0.4), 2)
    else: # Sectoral / Default
        pe = round(random.uniform(24.0, 40.0), 2)
        expense = round(random.uniform(0.6, 1.5), 2)
        
    return pe, expense

async def generate_summary_background(scheme_code: int):
    """
    Background worker task to generate the AI summary for a fund.
    Spawns its own session to avoid sharing session across threads/tasks.
    """
    logger.info(f"Background AI summary task started for scheme_code {scheme_code}")
    from app.core.database import async_session_maker
    
    async with async_session_maker() as session:
        # Fetch fund from DB
        fund_check = await session.execute(
            select(FundMaster).where(FundMaster.scheme_code == scheme_code)
        )
        fund = fund_check.scalar_one_or_none()
        if not fund:
            logger.warning(f"Background summary worker could not find scheme_code {scheme_code} in DB")
            return
            
        fund_dict = {
            "fund_name": fund.fund_name,
            "category": fund.category,
            "sub_category": fund.sub_category,
            "cagr_1y": round(fund.cagr_1y * 100, 2) if fund.cagr_1y else None,
            "cagr_3y": round(fund.cagr_3y * 100, 2) if fund.cagr_3y else None,
            "cagr_5y": round(fund.cagr_5y * 100, 2) if fund.cagr_5y else None,
            "sharpe_ratio": round(fund.sharpe_ratio, 2) if fund.sharpe_ratio else None,
            "sortino_ratio": round(fund.sortino_ratio, 2) if fund.sortino_ratio else None,
            "alpha": round(fund.alpha * 100, 2) if fund.alpha else None,
            "beta": round(fund.beta, 2) if fund.beta else None,
            "pe_ratio": fund.pe_ratio,
            "expense_ratio": fund.expense_ratio
        }
        
        try:
            summary = await generate_fund_summary(fund_dict)
            fund.ai_summary = summary
            await session.commit()
            logger.info(f"Background AI summary generated successfully for scheme_code {scheme_code}")
        except Exception as e:
            logger.error(f"Error in background summary task for scheme_code {scheme_code}: {e}")

async def ingest_fund(
    db: AsyncSession, 
    scheme_code: int, 
    force_recompute: bool = False,
    background_tasks: Optional[BackgroundTasks] = None
) -> Dict[str, Any]:
    """
    Ingests or updates a mutual fund's metadata and historical NAV.
    Returns sync statistics.
    """
    logger.info(f"Starting ingestion for scheme_code: {scheme_code}")
    
    # 5.5 years historical NAV cutoff date
    cutoff_date = date.today() - timedelta(days=int(5.5 * 365.25))
    
    # 1. Self-healing check: Ensure the benchmark fund is present
    if scheme_code != settings.BENCHMARK_SCHEME_CODE:
        bench_check = await db.execute(select(FundMaster).where(FundMaster.scheme_code == settings.BENCHMARK_SCHEME_CODE))
        benchmark = bench_check.scalar_one_or_none()
        if not benchmark:
            logger.info(f"Benchmark fund {settings.BENCHMARK_SCHEME_CODE} not found. Ingesting benchmark first.")
            await ingest_fund(db, settings.BENCHMARK_SCHEME_CODE, force_recompute=True, background_tasks=background_tasks)
            
    # 2. Fetch from MFapi.in
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch data from MFapi.in. Status code: {response.status_code}")
            
        json_data = response.json()
        
    meta = json_data.get("meta", {})
    nav_data = json_data.get("data", [])
    
    if not meta or not nav_data:
        raise Exception(f"Incomplete data returned for scheme_code: {scheme_code}")
        
    scheme_name = meta.get("scheme_name")
    scheme_category = meta.get("scheme_category", "Equity")
    isin = meta.get("isin_gp") or meta.get("isin_div_payer") or None
    
    # Map to our segments
    category, sub_category = map_category(scheme_category, scheme_name)
    pe_ratio, expense_ratio = generate_mock_pe_expense(category)
    
    # 3. Check if FundMaster exists
    fund_check = await db.execute(select(FundMaster).where(FundMaster.scheme_code == scheme_code))
    fund = fund_check.scalar_one_or_none()
    
    if not fund:
        fund = FundMaster(
            scheme_code=scheme_code,
            isin=isin,
            fund_name=scheme_name,
            category=category,
            sub_category=sub_category,
            pe_ratio=pe_ratio,
            expense_ratio=expense_ratio
        )
        db.add(fund)
        await db.flush()
    else:
        # Update details
        fund.isin = isin or fund.isin
        fund.fund_name = scheme_name
        fund.category = category
        fund.sub_category = sub_category
        
    # 4. Ingest NAV records
    # Get existing dates in DB to avoid duplicates
    existing_dates_query = await db.execute(
        select(NAVHistory.date).where(NAVHistory.scheme_code == scheme_code)
    )
    existing_dates = set(existing_dates_query.scalars().all())
    
    new_nav_records = []
    for nav_item in nav_data:
        date_str = nav_item.get("date")
        nav_val_str = nav_item.get("nav")
        if not date_str or not nav_val_str:
            continue
            
        try:
            # MFapi.in returns dates in DD-MM-YYYY format
            nav_date = datetime.strptime(date_str, "%d-%m-%Y").date()
            nav_val = float(nav_val_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing date/nav '{date_str}'/'{nav_val_str}': {e}")
            continue
            
        # Skip daily NAVs older than 5.5 years limit to optimize DB size and ingestion speed
        if nav_date < cutoff_date:
            continue
            
        if nav_date not in existing_dates:
            new_nav_records.append(
                NAVHistory(
                    scheme_code=scheme_code,
                    date=nav_date,
                    nav=nav_val
                )
            )
            
    if new_nav_records:
        db.add_all(new_nav_records)
        await db.flush()
        logger.info(f"Inserted {len(new_nav_records)} new NAV records for scheme {scheme_code}")
        
    # 5. Compute performance and risk metrics
    # Fetch all sorted NAV histories for the fund within last 5.5 years
    fund_nav_q = await db.execute(
        select(NAVHistory.date, NAVHistory.nav)
        .where(NAVHistory.scheme_code == scheme_code)
        .where(NAVHistory.date >= cutoff_date)
        .order_by(NAVHistory.date.asc())
    )
    fund_navs = [(row.date, row.nav) for row in fund_nav_q.all()]
    
    # Fetch benchmark NAVs within last 5.5 years
    bench_navs = []
    if scheme_code != settings.BENCHMARK_SCHEME_CODE:
        bench_nav_q = await db.execute(
            select(NAVHistory.date, NAVHistory.nav)
            .where(NAVHistory.scheme_code == settings.BENCHMARK_SCHEME_CODE)
            .where(NAVHistory.date >= cutoff_date)
            .order_by(NAVHistory.date.asc())
        )
        bench_navs = [(row.date, row.nav) for row in bench_nav_q.all()]
        
    # Run the analytics math
    metrics = calculate_risk_metrics(fund_navs, bench_navs)
    
    # Save computed metrics back to FundMaster
    fund.cagr_1y = metrics.get("cagr_1y")
    fund.cagr_3y = metrics.get("cagr_3y")
    fund.cagr_5y = metrics.get("cagr_5y")
    fund.sharpe_ratio = metrics.get("sharpe_ratio")
    fund.sortino_ratio = metrics.get("sortino_ratio")
    fund.alpha = metrics.get("alpha")
    fund.beta = metrics.get("beta")
    
    # Trigger AI synthesis on initial load or if explicitly forced
    if not fund.ai_summary or force_recompute or fund.ai_summary == "Generating AI Analysis in the background...":
        if background_tasks:
            logger.info(f"Offloading AI summary generation to background task for scheme_code: {scheme_code}")
            fund.ai_summary = "Generating AI Analysis in the background..."
            background_tasks.add_task(generate_summary_background, scheme_code)
        else:
            logger.info(f"Generating AI Summary synchronously for fund {scheme_code}...")
            fund_dict = {
                "fund_name": fund.fund_name,
                "category": fund.category,
                "sub_category": fund.sub_category,
                "cagr_1y": round(fund.cagr_1y * 100, 2) if fund.cagr_1y else None,
                "cagr_3y": round(fund.cagr_3y * 100, 2) if fund.cagr_3y else None,
                "cagr_5y": round(fund.cagr_5y * 100, 2) if fund.cagr_5y else None,
                "sharpe_ratio": round(fund.sharpe_ratio, 2) if fund.sharpe_ratio else None,
                "sortino_ratio": round(fund.sortino_ratio, 2) if fund.sortino_ratio else None,
                "alpha": round(fund.alpha * 100, 2) if fund.alpha else None,
                "beta": round(fund.beta, 2) if fund.beta else None,
                "pe_ratio": fund.pe_ratio,
                "expense_ratio": fund.expense_ratio
            }
            fund.ai_summary = await generate_fund_summary(fund_dict)
        
    await db.commit()
    logger.info(f"Ingestion and metrics calculation complete for scheme_code: {scheme_code}")
    
    return {
        "status": "success",
        "scheme_code": scheme_code,
        "fund_name": fund.fund_name,
        "new_records": len(new_nav_records),
        "total_records": len(fund_navs) + len(new_nav_records)
    }
