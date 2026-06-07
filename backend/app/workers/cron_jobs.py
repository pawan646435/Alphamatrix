import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.fund import FundMaster
from app.workers.ingestion import ingest_fund

logger = logging.getLogger("app.workers.cron_jobs")

async def run_overnight_sync(db: AsyncSession) -> dict:
    """
    Simulated nightly cron job.
    Fetches all funds in the DB, pulls latest NAV data,
    re-computes CAGR, Sharpe, Sortino, Alpha, Beta,
    and regenerates AI summaries if outdated.
    """
    logger.info("Initializing overnight batch sync process...")
    
    # Fetch all registered funds
    result = await db.execute(select(FundMaster.scheme_code))
    scheme_codes = result.scalars().all()
    
    success_count = 0
    failed_count = 0
    details = []
    
    # Process each fund
    for scheme_code in scheme_codes:
        try:
            logger.info(f"Syncing fund {scheme_code} in background...")
            sync_res = await ingest_fund(db, scheme_code, force_recompute=True)
            details.append(sync_res)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to sync fund {scheme_code} in background: {e}")
            failed_count += 1
            details.append({
                "status": "failed",
                "scheme_code": scheme_code,
                "error": str(e)
            })
            
    logger.info(f"Overnight batch sync complete. Success: {success_count}, Failed: {failed_count}")
    
    return {
        "status": "completed",
        "processed": len(scheme_codes),
        "success": success_count,
        "failed": failed_count,
        "details": details
    }
