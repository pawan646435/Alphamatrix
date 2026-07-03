import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

db_url = settings.DATABASE_URL or ""
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
is_sqlite = db_url.startswith("sqlite")

# We will initialize the engine and session maker lazily on first access
engine = None
_real_async_session_maker = None

def get_engine():
    global engine
    if engine is None:
        _init_db_engine()
    return engine

def get_session_maker():
    global _real_async_session_maker
    if _real_async_session_maker is None:
        _init_db_engine()
    return _real_async_session_maker

def _init_db_engine():
    global engine, _real_async_session_maker
    import logging
    logger = logging.getLogger("app.core.database")
    try:
        if not db_url:
            logger.error("DATABASE_URL is not set or empty. Database operations will fail.")
            raise ValueError("DATABASE_URL is not set or empty.")
            
        connect_args = {}
        local_url = db_url
        if is_sqlite:
            connect_args["check_same_thread"] = False
        else:
            # Strip query parameters (like sslmode) to prevent asyncpg TypeError
            if "?" in local_url:
                local_url = local_url.split("?")[0]
            # Inject SSL parameter for secure PostgreSQL connections
            connect_args["ssl"] = True
            
        logger.info(f"Initializing database engine with URL schema: {db_url.split('://')[0]}://...")
        engine = create_async_engine(
            local_url if not is_sqlite else db_url,
            echo=False,
            connect_args=connect_args,
            # Connection pool settings for production (PostgreSQL only)
            # pool_size: number of persistent connections kept open
            # max_overflow: additional connections allowed above pool_size
            # pool_pre_ping: test connection liveness before use (prevents stale connection errors on Neon)
            # pool_recycle: recycle connections after 5 minutes to match Neon idle timeout
            **({
                "pool_size": 5,
                "max_overflow": 10,
                "pool_pre_ping": True,
                "pool_recycle": 300,
            } if not is_sqlite else {}),
        )

        _real_async_session_maker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        logger.info("Database engine and session maker initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database engine: {e}")
        raise e

class AsyncSessionMakerProxy:
    def __call__(self, *args, **kwargs):
        session_maker = get_session_maker()
        return session_maker(*args, **kwargs)

async_session_maker = AsyncSessionMakerProxy()

# Declarative Base for models
Base = declarative_base()

# Injected by main.py after app startup — avoids circular imports.
# Points to _ensure_db_ready() which calls init_db() once per cold start.
_ensure_db_ready_fn = None

# Dependency to get async DB session
async def get_db():
    # Run lazy init once on first DB access (Vercel cold-start safe)
    if _ensure_db_ready_fn is not None:
        await _ensure_db_ready_fn()
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Redis migration flag key — set after full migrations complete.
# This prevents re-running slow ALTER TABLE / CREATE INDEX on every cold start.
_MIGRATION_FLAG_KEY = "alphamatrix:schema_v3_done"

async def _check_migration_done() -> bool:
    """Returns True if the schema_v3 migration has already been applied."""
    try:
        from app.core.redis import redis_client
        val = await redis_client.get(_MIGRATION_FLAG_KEY)
        return val is not None
    except Exception:
        return False  # Redis unavailable — assume not done, run migrations

async def _set_migration_done():
    """Marks schema_v3 migration as complete in Redis (TTL: 30 days)."""
    try:
        from app.core.redis import redis_client
        await redis_client.setex(_MIGRATION_FLAG_KEY, 60 * 60 * 24 * 30, "1")
    except Exception:
        pass  # Non-critical — worst case is re-running migrations next cold start

async def init_db():
    """
    Initializes tables and runs column migrations.

    Fast path (< 300ms): If Redis flag 'schema_v3_done' is set, only runs
    create_all (idempotent table creation) and skips slow ALTER TABLE / index ops.

    Slow path (first ever run, ~3-5s): Runs full schema migrations, then sets
    the Redis flag so all future cold starts take the fast path.
    """
    import logging
    logger = logging.getLogger("app.core.database")

    db_engine = get_engine()

    # Always run create_all — fast, idempotent, creates tables if missing
    async with db_engine.begin() as conn:
        from app.models.fund import FundMaster, NAVHistory
        from app.models.user import User
        from app.models.stock import StockMaster, StockPriceHistory, WatchlistItem
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[DB] create_all completed.")

    # Check Redis flag — skip heavy migrations if already applied
    already_migrated = await _check_migration_done()
    if already_migrated:
        logger.info("[DB] schema_v3 migration flag found in Redis — skipping ALTER TABLE/index ops.")
        return

    logger.info("[DB] schema_v3 migration flag NOT found — running full migrations...")

    # Initialize SQLite FTS5 search index virtual tables or PostgreSQL trigram search tables/indexes
    if is_sqlite:
        from sqlalchemy import text
        async with async_session_maker() as session:
            try:
                await session.execute(text("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS stock_search_index USING fts5(
                        symbol,
                        company_name,
                        exchange UNINDEXED
                    );
                """))
                await session.execute(text("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS fund_search_index USING fts5(
                        scheme_code,
                        scheme_name
                    );
                """))
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
    else:
        from sqlalchemy import text
        async with async_session_maker() as session:
            try:
                # 1. Create pg_trgm extension
                await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                
                # 2. Create search index tables
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS stock_search_index (
                        symbol VARCHAR(50) PRIMARY KEY,
                        company_name VARCHAR(255) NOT NULL,
                        exchange VARCHAR(50) NOT NULL
                    );
                """))
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS fund_search_index (
                        scheme_code VARCHAR(50) PRIMARY KEY,
                        scheme_name VARCHAR(255) NOT NULL
                    );
                """))
                
                # 3. Create trigram indexes on stock_search_index
                await session.execute(text("CREATE INDEX IF NOT EXISTS idx_stock_search_symbol_trgm ON stock_search_index USING gin (symbol gin_trgm_ops)"))
                await session.execute(text("CREATE INDEX IF NOT EXISTS idx_stock_search_name_trgm ON stock_search_index USING gin (company_name gin_trgm_ops)"))
                
                # 4. Create trigram index on fund_search_index
                await session.execute(text("CREATE INDEX IF NOT EXISTS idx_fund_search_name_trgm ON fund_search_index USING gin (scheme_name gin_trgm_ops)"))
                
                # 5. Create trigram indexes on primary master tables
                await session.execute(text("CREATE INDEX IF NOT EXISTS idx_stock_master_name_trgm ON stock_masters USING gin (company_name gin_trgm_ops)"))
                await session.execute(text("CREATE INDEX IF NOT EXISTS idx_fund_master_name_trgm ON fund_masters USING gin (fund_name gin_trgm_ops)"))
                
                await session.commit()
                logger.info("[DB] PostgreSQL search tables and trigram indexes initialized.")
            except Exception as e:
                await session.rollback()
                logger.error(f"[DB] Failed to initialize PostgreSQL search tables/indexes: {e}")
                # Don't fail the startup if index creation fails
                pass

    # Run column migrations for ratings engine v2 + progressive discovery pipeline v3
    mig_logger = logging.getLogger("app.core.database.migration")
    async with async_session_maker() as session:
        try:
            from sqlalchemy import text
            if is_sqlite:
                res = await session.execute(text("PRAGMA table_info(stock_masters)"))
                columns = [row[1] for row in res.fetchall()]
                columns_to_add = {
                    "fundamental_score": "FLOAT",
                    "valuation_score": "FLOAT",
                    "technical_score": "FLOAT",
                    "risk_score": "FLOAT",
                    "sector_relative_score": "FLOAT",
                    "confidence_score": "FLOAT",
                    "investor_verdict": "VARCHAR(50)",
                    "trader_verdict": "VARCHAR(50)",
                    "quality_score": "FLOAT",
                    "event_score": "FLOAT",
                    "trend_structure": "VARCHAR(50)",
                    "bull_case": "TEXT",
                    "bear_case": "TEXT",
                    "verdict_rationale": "TEXT",
                    "ingestion_status": "VARCHAR(20)",
                    "current_price": "FLOAT",
                    "exchange": "VARCHAR(10)",
                }
                for col_name, col_type in columns_to_add.items():
                    if col_name not in columns:
                        await session.execute(text(f"ALTER TABLE stock_masters ADD COLUMN {col_name} {col_type}"))
                        mig_logger.info(f"SQLite migration: Added column {col_name}")
                await session.execute(text("UPDATE stock_masters SET ingestion_status='READY' WHERE ingestion_status IS NULL"))
                await session.commit()
            else:
                columns_to_add = {
                    "fundamental_score": "DOUBLE PRECISION",
                    "valuation_score": "DOUBLE PRECISION",
                    "technical_score": "DOUBLE PRECISION",
                    "risk_score": "DOUBLE PRECISION",
                    "sector_relative_score": "DOUBLE PRECISION",
                    "confidence_score": "DOUBLE PRECISION",
                    "investor_verdict": "VARCHAR(50)",
                    "trader_verdict": "VARCHAR(50)",
                    "quality_score": "DOUBLE PRECISION",
                    "event_score": "DOUBLE PRECISION",
                    "trend_structure": "VARCHAR(50)",
                    "bull_case": "TEXT",
                    "bear_case": "TEXT",
                    "verdict_rationale": "TEXT",
                    "ingestion_status": "VARCHAR(20)",
                    "current_price": "DOUBLE PRECISION",
                    "exchange": "VARCHAR(10)",
                }
                for col_name, col_type in columns_to_add.items():
                    await session.execute(text(f"ALTER TABLE stock_masters ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                # Set READY for existing stocks that have no ingestion_status
                await session.execute(text(
                    "UPDATE stock_masters SET ingestion_status='READY' WHERE ingestion_status IS NULL AND alpha_score IS NOT NULL"
                ))
                await session.commit()
                mig_logger.info("[DB] PostgreSQL stock_masters column migrations applied.")
        except Exception as e:
            await session.rollback()
            mig_logger.error(f"[DB] stock_masters column migration failed: {e}")
            raise e

    # Run column migrations for fund_masters
    async with async_session_maker() as session:
        try:
            from sqlalchemy import text
            fund_columns_to_add = {
                "fund_score": "DOUBLE PRECISION",
                "fund_verdict": "VARCHAR(20)",
                "std_deviation": "DOUBLE PRECISION",
                "max_drawdown": "DOUBLE PRECISION",
                "aum": "DOUBLE PRECISION",
                "consistency_score": "DOUBLE PRECISION",
                "category_rank": "INTEGER",
                "category_count": "INTEGER",
                "category_avg_cagr_3y": "DOUBLE PRECISION",
                "category_avg_sharpe": "DOUBLE PRECISION",
                "category_avg_alpha": "DOUBLE PRECISION",
                "bull_case": "TEXT",
                "bear_case": "TEXT",
                "fund_rationale": "TEXT",
            }
            if is_sqlite:
                res = await session.execute(text("PRAGMA table_info(fund_masters)"))
                existing = [row[1] for row in res.fetchall()]
                for col_name, col_type in fund_columns_to_add.items():
                    if col_name not in existing:
                        await session.execute(text(f"ALTER TABLE fund_masters ADD COLUMN {col_name} {col_type}"))
            else:
                for col_name, col_type in fund_columns_to_add.items():
                    await session.execute(text(f"ALTER TABLE fund_masters ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
            await session.commit()
        except Exception as e:
            await session.rollback()
            mig_logger.error(f"[DB] fund_masters column migration failed: {e}")
            # Don't raise — fund migrations shouldn't block startup

    # Mark migrations as done in Redis so future cold starts skip this block
    await _set_migration_done()
    logger.info("[DB] schema_v3 migration flag written to Redis. Future cold starts will be fast.")
