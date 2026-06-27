import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Add parent path to allow imports from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

async def main():
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        print("DATABASE_URL is SQLite. test_sqlalchemy_ssl requires a PostgreSQL URL.")
        return

    # Remove query parameters from URL
    if "?" in url:
        url = url.split("?")[0]

    # Pass ssl=True via connect_args
    engine = create_async_engine(
        url,
        connect_args={"ssl": True}
    )
    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT 1"))
            print("SQLAlchemy SSL Connected successfully:", res.scalar())
    except Exception as e:
        print(f"SQLAlchemy SSL Connection failed: {e} ({type(e)})")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
