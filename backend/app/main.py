import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
import asyncio
import logging
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, async_session_maker
from app.api.api import api_router
from app.workers.ingestion import ingest_fund

from app.workers.stock_ingestion import seed_stocks_data

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
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "ok"}

async def seed_data_background():
    """
    Background worker task to seed database with popular Indian mutual funds
    and stock market equities on initial startup.
    """
    logger.info("Starting background database seeding...")
    
    # 1. Ensure tables are created
    try:
        await init_db()
        logger.info("Database tables initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
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
    # Run seeding in background after server start
    asyncio.create_task(seed_data_background())
