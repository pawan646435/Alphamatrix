import os
import json
import httpx
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import check_rate_limit
from app.models.fund import FundMaster, NAVHistory
from app.schemas.fund_schema import (
    FundGridItem, FundDetailResponse, FundMasterResponse, 
    NAVHistoryBase, SyncResponse
)
from app.workers.ingestion import ingest_fund
from app.workers.cron_jobs import run_overnight_sync

from app.core.config import settings
from app.core.redis import redis_client
from app.core.cache_ttl import FUND_DETAIL_TTL, FUND_LIST_TTL

router = APIRouter()
logger = logging.getLogger("app.api.v1.funds")

# In-memory cache for all Indian mutual funds search
MF_MASTER_LIST = []
CACHE_FILE = "mf_master_list.json"

async def load_master_list_if_empty():
    global MF_MASTER_LIST
    if not MF_MASTER_LIST:
        # Try loading from disk cache first
        if os.path.exists(CACHE_FILE):
            try:
                logger.info("Loading master mutual fund list from local disk cache...")
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    MF_MASTER_LIST = json.load(f)
                logger.info(f"Loaded {len(MF_MASTER_LIST)} schemes from disk cache.")
                return
            except Exception as e:
                logger.error(f"Failed to read local master list cache: {e}")

        # Fallback to network fetch
        try:
            logger.info("Fetching master mutual fund list from MFapi...")
            async with httpx.AsyncClient() as client:
                res = await client.get("https://api.mfapi.in/mf", timeout=15.0)
                if res.status_code == 200:
                    MF_MASTER_LIST = res.json()
                    logger.info(f"Loaded {len(MF_MASTER_LIST)} schemes into master cache.")
                    # Write to disk cache
                    try:
                        with open(CACHE_FILE, "w", encoding="utf-8") as f:
                            json.dump(MF_MASTER_LIST, f)
                        logger.info("Saved master mutual fund list to disk cache.")
                    except Exception as fs_err:
                        logger.error(f"Failed to save master list to disk: {fs_err}")
        except Exception as e:
            logger.error(f"Failed to load master fund list: {e}")

@router.get("/search", dependencies=[Depends(check_rate_limit)])
async def search_funds_master(query: str):
    """
    Search all Indian mutual funds in-memory using the MFapi list cache.
    Matches against schemeName and schemeCode, capped at 50 results.
    """
    await load_master_list_if_empty()
    if not MF_MASTER_LIST:
        return []
        
    query_lower = query.lower()
    results = []
    
    for item in MF_MASTER_LIST:
        name = item.get("schemeName", "")
        code = str(item.get("schemeCode", ""))
        
        if query_lower in name.lower() or query_lower in code:
            results.append({
                "scheme_code": item.get("schemeCode"),
                "fund_name": name
            })
            if len(results) >= 50:
                break
                
    return results

@router.get("/", response_model=List[FundGridItem], dependencies=[Depends(check_rate_limit)])
async def get_funds(
    category: Optional[str] = None,
    min_cagr_1y: Optional[float] = None,
    max_cagr_1y: Optional[float] = None,
    min_cagr_3y: Optional[float] = None,
    max_cagr_3y: Optional[float] = None,
    min_cagr_5y: Optional[float] = None,
    max_cagr_5y: Optional[float] = None,
    min_expense_ratio: Optional[float] = None,
    max_expense_ratio: Optional[float] = None,
    min_sharpe_ratio: Optional[float] = None,
    max_sharpe_ratio: Optional[float] = None,
    min_pe_ratio: Optional[float] = None,
    max_pe_ratio: Optional[float] = None,
    sort_by: Optional[str] = "cagr_3y",
    sort_order: str = "desc",
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Get lists of ingested mutual funds applying filters.
    Includes pagination and dynamic sorting.
    """
    query = select(FundMaster)
    
    # Apply filters
    if category:
        query = query.where(FundMaster.category == category)
    if min_cagr_1y is not None:
        query = query.where(FundMaster.cagr_1y >= (min_cagr_1y / 100.0))
    if max_cagr_1y is not None:
        query = query.where(FundMaster.cagr_1y <= (max_cagr_1y / 100.0))
    if min_cagr_3y is not None:
        query = query.where(FundMaster.cagr_3y >= (min_cagr_3y / 100.0))
    if max_cagr_3y is not None:
        query = query.where(FundMaster.cagr_3y <= (max_cagr_3y / 100.0))
    if min_cagr_5y is not None:
        query = query.where(FundMaster.cagr_5y >= (min_cagr_5y / 100.0))
    if max_cagr_5y is not None:
        query = query.where(FundMaster.cagr_5y <= (max_cagr_5y / 100.0))
    if min_expense_ratio is not None:
        query = query.where(FundMaster.expense_ratio >= min_expense_ratio)
    if max_expense_ratio is not None:
        query = query.where(FundMaster.expense_ratio <= max_expense_ratio)
    if min_sharpe_ratio is not None:
        query = query.where(FundMaster.sharpe_ratio >= min_sharpe_ratio)
    if max_sharpe_ratio is not None:
        query = query.where(FundMaster.sharpe_ratio <= max_sharpe_ratio)
    if min_pe_ratio is not None:
        query = query.where(FundMaster.pe_ratio >= min_pe_ratio)
    if max_pe_ratio is not None:
        query = query.where(FundMaster.pe_ratio <= max_pe_ratio)
        
    # Apply sorting
    if sort_by and hasattr(FundMaster, sort_by):
        sort_attr = getattr(FundMaster, sort_by)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_attr.asc())
        else:
            query = query.order_by(sort_attr.desc())
            
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    funds = result.scalars().all()
    
    return funds

@router.get("/{scheme_code}", response_model=FundDetailResponse, dependencies=[Depends(check_rate_limit)])
async def get_fund_detail(
    scheme_code: int, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db),
    response: Response = None
):
    """
    Retrieve full details of a mutual fund and its NAV history.
    Self-healing: If the fund doesn't exist in DB, triggers on-demand ingestion.
    """
    cache_key = f"fund_detail:{scheme_code}"
    try:
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached fund details for {scheme_code}")
            return json.loads(cached_data)
    except Exception as e:
        logger.error(f"Redis get failed for key {cache_key}: {e}")

    # Check if fund exists
    fund_check = await db.execute(select(FundMaster).where(FundMaster.scheme_code == scheme_code))
    fund = fund_check.scalar_one_or_none()
    
    if not fund:
        logger.info(f"Fund {scheme_code} not found in DB. Ingesting on-demand...")
        try:
            await ingest_fund(db, scheme_code, force_recompute=True, background_tasks=background_tasks)
            # Fetch again after ingestion
            fund_check = await db.execute(select(FundMaster).where(FundMaster.scheme_code == scheme_code))
            fund = fund_check.scalar_one_or_none()
        except Exception as e:
            logger.error(f"On-demand ingestion failed for {scheme_code}: {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mutual Fund with code {scheme_code} not found, and on-demand ingestion failed: {str(e)}"
            )
            
    if not fund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mutual Fund with code {scheme_code} not found."
        )
        
    # If the fund exists but doesn't have a summary, trigger background summary generation
    if not fund.ai_summary or fund.ai_summary == "Generating AI Analysis in the background...":
        from app.workers.ingestion import generate_summary_background
        logger.info(f"Triggering background AI summary generation for existing fund: {scheme_code}")
        fund.ai_summary = "Generating AI Analysis in the background..."
        await db.commit()
        await db.refresh(fund)
        
        # Invalidate cache so that cached response reflects the loading status
        try:
            await redis_client.delete(cache_key)
        except Exception as e:
            logger.error(f"Failed to clear Redis cache on summary status change: {e}")
                
        background_tasks.add_task(generate_summary_background, scheme_code)

    # Get NAV history sorted descending (latest first)
    nav_check = await db.execute(
        select(NAVHistory.date, NAVHistory.nav)
        .where(NAVHistory.scheme_code == scheme_code)
        .order_by(NAVHistory.date.desc())
    )
    navs = [{"date": row.date.isoformat(), "nav": row.nav} for row in nav_check.all()]
    
    response_data = {
        "fund": {
            "scheme_code": fund.scheme_code,
            "isin": fund.isin,
            "fund_name": fund.fund_name,
            "category": fund.category,
            "sub_category": fund.sub_category,
            "pe_ratio": fund.pe_ratio,
            "expense_ratio": fund.expense_ratio,
            "cagr_1y": fund.cagr_1y,
            "cagr_3y": fund.cagr_3y,
            "cagr_5y": fund.cagr_5y,
            "sharpe_ratio": fund.sharpe_ratio,
            "sortino_ratio": fund.sortino_ratio,
            "alpha": fund.alpha,
            "beta": fund.beta,
            "ai_summary": fund.ai_summary,
            "last_updated": fund.last_updated.isoformat() if fund.last_updated else None
        },
        "nav_history": navs
    }
    
    # Store response in Redis cache (1 hour expiry, or 5 seconds if loading)
    try:
        ttl = 5 if fund.ai_summary == "Generating AI Analysis in the background..." else FUND_DETAIL_TTL
        await redis_client.setex(cache_key, ttl, json.dumps(response_data))
        logger.info(f"Cached fund details for {scheme_code} in Redis with TTL={ttl}s")
    except Exception as e:
        logger.error(f"Redis set failed for key {cache_key}: {e}")
            
    if fund.ai_summary == "Generating AI Analysis in the background..." and response is not None:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return response_data

@router.post("/sync/{scheme_code}", response_model=SyncResponse)
async def sync_fund_manual(
    scheme_code: int, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger sync and metrics computation for a specific fund.
    """
    # Invalidate cache
    try:
        await redis_client.delete(f"fund_detail:{scheme_code}")
        logger.info(f"Invalidated Redis cache for manual sync of {scheme_code}")
    except Exception as e:
        logger.error(f"Failed to delete Redis cache key for {scheme_code}: {e}")
            
    try:
        res = await ingest_fund(db, scheme_code, force_recompute=True, background_tasks=background_tasks)
        return {
            "status": "success",
            "message": f"Successfully synced fund: {res['fund_name']}",
            "scheme_code": scheme_code,
            "records_synced": res["new_records"]
        }
    except Exception as e:
        logger.error(f"Manual sync failed for {scheme_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )

@router.post("/sync-all")
async def trigger_all_funds_sync(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Trigger overnight sync for all loaded funds in the background.
    """
    background_tasks.add_task(run_overnight_sync, db)
    return {"status": "accepted", "message": "Overnight batch update task launched in the background."}
