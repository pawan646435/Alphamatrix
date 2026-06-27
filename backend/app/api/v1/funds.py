import os
import json
import httpx
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, case

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
from app.core.cache_ttl import (
    FUND_DETAIL_TTL, 
    FUND_LIST_TTL,
    OPTIMIZED_METADATA_TTL,
    OPTIMIZED_CHART_TTL,
    OPTIMIZED_METRICS_TTL,
    OPTIMIZED_AI_TTL
)

router = APIRouter()
logger = logging.getLogger("app.api.v1.funds")
ingesting_funds = set()

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
async def search_funds_master(query: str = Query(..., min_length=1, max_length=100)):
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
    cache_key = f"funds_list:{category or ''}:{min_cagr_1y or ''}:{max_cagr_1y or ''}:{min_cagr_3y or ''}:{max_cagr_3y or ''}:{min_cagr_5y or ''}:{max_cagr_5y or ''}:{min_expense_ratio or ''}:{max_expense_ratio or ''}:{min_sharpe_ratio or ''}:{max_sharpe_ratio or ''}:{min_pe_ratio or ''}:{max_pe_ratio or ''}:{sort_by or ''}:{sort_order or ''}:{skip}:{limit}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis get funds list failed: {e}")

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
        
    # Apply sorting with NULLS LAST (non-null values first)
    if sort_by and hasattr(FundMaster, sort_by):
        sort_attr = getattr(FundMaster, sort_by)
        nulls_expr = case((sort_attr.is_(None), 1), else_=0)
        if sort_order.lower() == "asc":
            query = query.order_by(nulls_expr, sort_attr.asc())
        else:
            query = query.order_by(nulls_expr, sort_attr.desc())
            
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    funds = result.scalars().all()
    
    funds_data = [
        {
            "scheme_code": f.scheme_code,
            "fund_name": f.fund_name,
            "category": f.category,
            "cagr_1y": f.cagr_1y,
            "cagr_3y": f.cagr_3y,
            "cagr_5y": f.cagr_5y,
            "sharpe_ratio": f.sharpe_ratio,
            "alpha": f.alpha,
            "pe_ratio": f.pe_ratio,
            "expense_ratio": f.expense_ratio,
            "beta": f.beta
        }
        for f in funds
    ]

    try:
        await redis_client.setex(cache_key, FUND_LIST_TTL, json.dumps(funds_data))
    except Exception as e:
        logger.error(f"Redis set funds list failed: {e}")
    
    return funds_data

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
    cached_meta = None
    cached_chart = None
    cached_metrics = None
    cached_ai = None
    
    try:
        import asyncio
        cached_meta, cached_chart, cached_metrics, cached_ai = await asyncio.gather(
            redis_client.get(f"fund:{scheme_code}"),
            redis_client.get(f"fund_chart:{scheme_code}"),
            redis_client.get(f"fund_metrics:{scheme_code}"),
            redis_client.get(f"fund_ai:{scheme_code}")
        )
    except Exception as e:
        logger.error(f"Redis get split detail failed for fund {scheme_code}: {e}")
            
    # Reconstruct from cache if all exist and summary is not generating placeholder
    if cached_meta and cached_chart and cached_metrics and cached_ai:
        meta_dict = json.loads(cached_meta)
        metrics_dict = json.loads(cached_metrics)
        ai_val = cached_ai
        
        fund_dict = {**meta_dict, **metrics_dict}
        fund_dict["ai_summary"] = ai_val
        fund_dict["status"] = "discovering" if fund_dict.get("cagr_1y") is None else "ready"
        
        if ai_val != "Generating AI Analysis in the background...":
            logger.info(f"Returning fully split cached fund details for {scheme_code}")
            return {
                "fund": fund_dict,
                "nav_history": json.loads(cached_chart)
            }

    # Check if fund exists
    fund_check = await db.execute(select(FundMaster).where(FundMaster.scheme_code == scheme_code))
    fund = fund_check.scalar_one_or_none()
    
    if fund and fund.isin == "Invalid":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mutual Fund with code {scheme_code} not found on live exchanges."
        )
    
    is_new = False
    if not fund:
        logger.info(f"Fund {scheme_code} not found in DB. Creating skeleton and scheduling background sync...")
        try:
            fund = FundMaster(
                scheme_code=scheme_code,
                isin=None,
                fund_name=f"Discovering Mutual Fund {scheme_code}...",
                category="Equity",
                sub_category="Unknown",
                pe_ratio=None,
                expense_ratio=None,
                ai_summary="Generating AI Analysis in the background..."
            )
            db.add(fund)
            await db.commit()
            await db.refresh(fund)
            is_new = True
        except Exception as e:
            await db.rollback()
            fund_check = await db.execute(select(FundMaster).where(FundMaster.scheme_code == scheme_code))
            fund = fund_check.scalar_one_or_none()
            if not fund:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to initialize skeleton metadata for fund {scheme_code}: {e}"
                )
            
    # Trigger background ingestion if new skeleton or if metrics are missing
    if is_new or (fund.cagr_1y is None and fund.category == "Equity" and fund.sub_category == "Unknown"):
        if scheme_code not in ingesting_funds:
            ingesting_funds.add(scheme_code)
            logger.info(f"Fund {scheme_code} is in skeleton/discovering state — scheduling background ingestion")
            async def _ingest_and_brief(code: int):
                from app.core.database import async_session_maker
                from app.workers.ingestion import ingest_fund, generate_summary_background
                from app.models.fund import FundMaster
                try:
                    async with async_session_maker() as ingest_session:
                        await ingest_fund(ingest_session, code, force_recompute=True)
                        await generate_summary_background(code)
                except Exception as e:
                    logger.error(f"Background ingest failed for fund {code}: {e}")
                    # Mark fund as invalid in database to prevent infinite discovery loops
                    async with async_session_maker() as cleanup_session:
                        res = await cleanup_session.execute(
                            select(FundMaster).where(FundMaster.scheme_code == code)
                        )
                        f = res.scalar_one_or_none()
                        if f:
                            f.isin = "Invalid"
                            f.fund_name = f"Invalid Fund ({code})"
                            await cleanup_session.commit()
                finally:
                    ingesting_funds.discard(code)
            background_tasks.add_task(_ingest_and_brief, scheme_code)
        
    # Trigger background AI summary if missing (for already ingested funds)
    trigger_background = False
    if fund.cagr_1y is not None:
        if not fund.ai_summary or fund.ai_summary == "Generating AI Analysis in the background...":
            from app.workers.ingestion import generate_summary_background
            logger.info(f"Triggering background AI summary generation for existing fund: {scheme_code}")
            fund.ai_summary = "Generating AI Analysis in the background..."
            await db.commit()
            await db.refresh(fund)
            trigger_background = True
            
            try:
                await redis_client.delete(f"fund_ai:{scheme_code}")
            except Exception as e:
                logger.error(f"Failed to clear Redis cache on summary status change: {e}")
                    
            background_tasks.add_task(generate_summary_background, scheme_code)

    navs = []
    if cached_chart:
        navs = json.loads(cached_chart)
    else:
        # Get NAV history sorted descending (latest first)
        nav_check = await db.execute(
            select(NAVHistory.date, NAVHistory.nav)
            .where(NAVHistory.scheme_code == scheme_code)
            .order_by(NAVHistory.date.desc())
        )
        navs = [{"date": row.date.isoformat(), "nav": row.nav} for row in nav_check.all()]
        try:
            await redis_client.setex(f"fund_chart:{scheme_code}", OPTIMIZED_CHART_TTL, json.dumps(navs))
        except Exception as e:
            logger.error(f"Redis set fund history failed: {e}")
    
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
    
    if trigger_background or is_new:
        try:
            await redis_client.delete(
                f"fund:{scheme_code}",
                f"fund_metrics:{scheme_code}",
                f"fund_ai:{scheme_code}"
            )
        except Exception as e:
            logger.error(f"Failed to clear Redis keys for briefing status: {e}")
            
    # Cache in Redis split keys
    try:
        await redis_client.setex(f"fund:{scheme_code}", OPTIMIZED_METADATA_TTL, json.dumps(meta_dict))
        await redis_client.setex(f"fund_metrics:{scheme_code}", OPTIMIZED_METRICS_TTL, json.dumps(metrics_dict))
        
        ai_ttl = 5 if (trigger_background or is_new or fund.ai_summary == "Generating AI Analysis in the background...") else OPTIMIZED_AI_TTL
        await redis_client.setex(f"fund_ai:{scheme_code}", ai_ttl, fund.ai_summary or "Generating AI Analysis in the background...")
        logger.info(f"Cached fund split details for {scheme_code} in Redis")
    except Exception as e:
        logger.error(f"Redis set failed for key fund:{scheme_code}: {e}")
            
    fund_response = {**meta_dict, **metrics_dict}
    fund_response["ai_summary"] = fund.ai_summary
    fund_response["status"] = "discovering" if fund.cagr_1y is None else "ready"
    
    if (trigger_background or is_new or fund.ai_summary == "Generating AI Analysis in the background...") and response is not None:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return {
        "fund": fund_response,
        "nav_history": navs
    }

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
        await redis_client.delete_pattern("funds_list:*")
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
    try:
        await redis_client.delete_pattern("funds_list:*")
    except Exception as e:
        logger.error(f"Failed to delete Redis cache keys for sync-all: {e}")
    background_tasks.add_task(run_overnight_sync, db)
    return {"status": "accepted", "message": "Overnight batch update task launched in the background."}
