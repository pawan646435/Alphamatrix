from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

db_url = settings.DATABASE_URL
is_sqlite = db_url.startswith("sqlite")

# Configure connection arguments
connect_args = {}
if is_sqlite:
    # Disable same-thread check for SQLite to allow multi-threaded access in development
    connect_args["check_same_thread"] = False
else:
    # It's PostgreSQL or other SQL. Strip query parameters (like sslmode) to prevent asyncpg TypeError
    if "?" in db_url:
        db_url = db_url.split("?")[0]
    # Inject SSL parameter for secure PostgreSQL connections
    connect_args["ssl"] = True

# Create Async Engine
engine = create_async_engine(
    db_url,
    echo=False,
    connect_args=connect_args,
)

# Async Session Factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Declarative Base for models
Base = declarative_base()

# Dependency to get async DB session
async def get_db():
    async with async_session_maker() as session:
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
    async with engine.begin() as conn:
        # Import models inside function to prevent circular imports
        from app.models.fund import FundMaster, NAVHistory
        from app.models.user import User
        from app.models.stock import StockMaster, StockPriceHistory, WatchlistItem
        await conn.run_sync(Base.metadata.create_all)
        
    # Initialize SQLite FTS5 search index virtual tables
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

