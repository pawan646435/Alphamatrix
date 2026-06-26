import asyncio
import os

# Set DATABASE_URL to Neon for testing
os.environ["DATABASE_URL"] = "postgresql+asyncpg://neondb_owner:npg_3rPjc4TBlaoe@ep-twilight-base-atos9mpc-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

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
