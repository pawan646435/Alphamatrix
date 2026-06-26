import asyncio
import asyncpg

async def main():
    dsn = "postgresql://neondb_owner:npg_3rPjc4TBlaoe@ep-twilight-base-atos9mpc-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    try:
        conn = await asyncpg.connect(dsn)
        print("Connected successfully!")
        await conn.close()
    except Exception as e:
        print(f"Connection failed: {e} ({type(e)})")

if __name__ == "__main__":
    asyncio.run(main())
