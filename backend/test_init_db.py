import asyncio
import sys
import os

# Add parent path to allow imports from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

from app.core.database import init_db, get_engine

async def main():
    try:
        print("Initializing database...")
        await init_db()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database initialization failed: {e}")
    finally:
        engine = get_engine()
        if engine:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
