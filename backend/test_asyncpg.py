import asyncio
import asyncpg
import sys
import os

# Add parent path to allow imports from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

async def main():
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif db_url.startswith("sqlite"):
        print("DATABASE_URL is SQLite. asyncpg test requires a PostgreSQL URL.")
        return
        
    try:
        conn = await asyncpg.connect(db_url)
        print("Connected successfully!")
        await conn.close()
    except Exception as e:
        print(f"Connection failed: {e} ({type(e)})")

if __name__ == "__main__":
    asyncio.run(main())
