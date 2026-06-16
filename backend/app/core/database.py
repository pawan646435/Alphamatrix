from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Determine DB properties
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# Configure connection arguments
connect_args = {}
if is_sqlite:
    # Disable same-thread check for SQLite to allow multi-threaded access in development
    connect_args["check_same_thread"] = False

# Create Async Engine
engine = create_async_engine(
    settings.DATABASE_URL,
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
