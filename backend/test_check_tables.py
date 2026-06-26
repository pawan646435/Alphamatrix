import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    url = "postgresql+asyncpg://neondb_owner:npg_3rPjc4TBlaoe@ep-twilight-base-atos9mpc-pooler.c-9.us-east-1.aws.neon.tech/neondb"
    engine = create_async_engine(url, connect_args={"ssl": True})
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
