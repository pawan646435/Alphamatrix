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

# Dependency to get async DB session
async def get_db():
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
            
async def init_db():
    """Initializes tables in database if they do not exist."""
    db_engine = get_engine()
    async with db_engine.begin() as conn:
        # Import models inside function to prevent circular imports
        from app.models.fund import FundMaster, NAVHistory
        from app.models.user import User
        from app.models.stock import StockMaster, StockPriceHistory, WatchlistItem
        await conn.run_sync(Base.metadata.create_all)
        
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
        import logging
        logger = logging.getLogger("app.core.database")
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
                logger.info("Successfully initialized PostgreSQL search tables and trigram indexes.")
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to initialize PostgreSQL search tables/indexes: {e}")
                # Don't fail the startup if index creation fails, but log it
                pass

