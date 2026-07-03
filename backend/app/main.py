import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.timing import TimingMiddleware

from app.core.config import settings
from app.core.database import init_db, async_session_maker
from app.api.api import api_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AlphaMatrix High-Performance Mutual Fund Analytics & AI Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression for all JSON responses > 1KB
# Reduces payload size ~60-70% on typical fund/stock JSON responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Cache-Control headers for static-ish read endpoints
# Instructs Vercel edge cache and browser to cache read API responses
CACHEABLE_PREFIXES = (
    "/api/v1/stocks/list",
    "/api/v1/stocks/detail/",
    "/api/v1/stocks/sector/",
    "/api/v1/stocks/market-regime",
    "/api/v1/funds/",
    "/api/v1/news/",
    "/api/v1/search",
)

class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if (
            request.method == "GET"
            and response.status_code == 200
            and "Cache-Control" not in response.headers
            and any(path.startswith(p) for p in CACHEABLE_PREFIXES)
        ):
            # stale-while-revalidate: serve stale for 60s while refetching in background
            response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=30"
        return response

app.add_middleware(CacheControlMiddleware)

# TimingMiddleware added last so it runs outermost (first in, last out)
# It therefore captures total wall-clock time including all other middleware
app.add_middleware(TimingMiddleware)

# ── Lazy DB initialization for Vercel ────────────────────────────────────────
# On Vercel, @app.on_event("startup") is bypassed because the function is
# invoked cold per-request. We call init_db() on the FIRST /api/v1 request
# to ensure tables + column migrations are applied before any DB query runs.
_db_initialized = False
_db_init_lock = asyncio.Lock()

async def _ensure_db_ready():
    global _db_initialized
    if _db_initialized:
        return
    async with _db_init_lock:
        if _db_initialized:  # double-check inside lock
            return
        try:
            await init_db()
            logger.info("[LazyInit] init_db() completed successfully on first request.")
        except Exception as e:
            logger.error(f"[LazyInit] init_db() failed: {e}")
            # Don't set _db_initialized so next request retries — but cap to
            # avoid hammering DB on every cold start failure
        finally:
            _db_initialized = True  # Set True regardless to avoid retry storm

class LazyDbInitMiddleware(BaseHTTPMiddleware):
    """Runs init_db once on the first /api/v1 request (Vercel cold-start safe)."""
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/v1"):
            await _ensure_db_ready()
        return await call_next(request)

app.add_middleware(LazyDbInitMiddleware)


# Include v1 routes
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs": "/docs",
        "status": "healthy"
    }

@app.get("/health")
async def health():
    """Bulletproof health check — never crashes, always returns 200."""
    status_payload = {
        "status": "ok",
        "database": "unknown",
        "redis": "unknown",
        "ai": "not_configured",
    }

    # Database check
    try:
        from sqlalchemy import text
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        status_payload["database"] = "connected"
    except Exception as e:
        status_payload["database"] = f"disconnected ({type(e).__name__})"

    # Redis check
    try:
        from app.core.redis import redis_client
        result = await redis_client.get("health_probe")
        status_payload["redis"] = "connected"
    except Exception as e:
        status_payload["redis"] = f"disconnected ({type(e).__name__})"

    # AI check (Groq)
    try:
        import app.services.ai_agent as ai_agent_module
        ai_agent_module._init_groq()
        status_payload["ai"] = "configured" if ai_agent_module.groq_configured else "not_configured"
    except Exception:
        status_payload["ai"] = "error"

    return status_payload


@app.get("/api/v1/db-health")
async def db_health():
    from sqlalchemy import text, func
    from sqlalchemy.future import select
    from app.models.user import User
    from app.models.fund import FundMaster
    from app.models.stock import StockMaster

    try:
        async with async_session_maker() as session:
            # 1. Verify active connection
            await session.execute(text("SELECT 1"))
            
            # 2. Check table existence / count rows using count query
            user_count = 0
            fund_count = 0
            stock_count = 0
            
            try:
                user_res = await session.execute(select(func.count()).select_from(User))
                user_count = user_res.scalar() or 0
            except Exception as e:
                logger.warning(f"Could not count users table: {e}")
                user_count = -1
                
            try:
                fund_res = await session.execute(select(func.count()).select_from(FundMaster))
                fund_count = fund_res.scalar() or 0
            except Exception as e:
                logger.warning(f"Could not count fund_masters table: {e}")
                fund_count = -1

            try:
                stock_res = await session.execute(select(func.count()).select_from(StockMaster))
                stock_count = stock_res.scalar() or 0
            except Exception as e:
                logger.warning(f"Could not count stock_masters table: {e}")
                stock_count = -1
                
            return {
                "status": "healthy",
                "database": "connected",
                "counts": {
                    "users": user_count,
                    "funds": fund_count,
                    "stocks": stock_count
                }
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

async def seed_data_background():
    """
    Background worker task to seed database with popular Indian mutual funds
    and stock market equities on initial startup.
    """
    logger.info("Starting background database seeding...")
    from app.workers.ingestion import ingest_fund
    from app.workers.stock_ingestion import seed_stocks_data, populate_search_indices
    
    # 1. Ensure tables are created and search indices populated
    try:
        await init_db()
        logger.info("Database tables initialized.")
        async with async_session_maker() as session:
            await populate_search_indices(session)
    except Exception as e:
        logger.error(f"Failed to initialize database and populate search indices: {e}")
        return
        
    # 2. Seed popular funds (including Benchmark fund 120687)
    seed_schemes = [
        settings.BENCHMARK_SCHEME_CODE,
        119063,
        120586,
        120716,
        120828
    ]
    
    # Run ingestion sequentially for safety
    async with async_session_maker() as session:
        for scheme_code in seed_schemes:
            try:
                # Check if fund is already ingested
                from sqlalchemy.future import select
                from app.models.fund import FundMaster
                
                check = await session.execute(
                    select(FundMaster).where(FundMaster.scheme_code == scheme_code)
                )
                if check.scalar_one_or_none():
                    logger.info(f"Scheme {scheme_code} already seeded. Skipping.")
                    continue
                    
                logger.info(f"Seeding scheme {scheme_code}...")
                await ingest_fund(session, scheme_code, force_recompute=False)
                logger.info(f"Seeding completed for scheme {scheme_code}")
                # Wait 1 sec to be nice to the open API feed
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(f"Error seeding scheme {scheme_code}: {e}")
                
    # 3. Seed Stocks
    try:
        async with async_session_maker() as session:
            await seed_stocks_data(session)
    except Exception as e:
        logger.error(f"Error seeding stocks data: {e}")
                
    logger.info("Seeding background task finished.")

@app.on_event("startup")
async def startup_event():
    # Do not execute background seeding inside Vercel serverless environments
    if "VERCEL" in os.environ:
        logger.info("Server running inside Vercel Serverless. Bypassing background seed queue.")
        return

    # Run seeding in background after server start locally
    asyncio.create_task(seed_data_background())
