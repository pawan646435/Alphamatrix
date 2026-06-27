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
        print("DATABASE_URL is SQLite. test_check_tables requires a PostgreSQL URL.")
        return

    connect_args = {}
    if "postgresql" in url:
        if "?" in url:
            url = url.split("?")[0]
        connect_args["ssl"] = True

    engine = create_async_engine(url, connect_args=connect_args)
    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [r[0] for r in res.all()]
            print("Tables in Neon database:", tables)
    except Exception as e:
        print(f"Failed to fetch tables: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
