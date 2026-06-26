import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    url = "postgresql+asyncpg://neondb_owner:npg_3rPjc4TBlaoe@ep-twilight-base-atos9mpc-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT 1"))
            print("SQLAlchemy Connected successfully:", res.scalar())
    except Exception as e:
        print(f"SQLAlchemy Connection failed: {e} ({type(e)})")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
