import asyncio
import sys

sys.path.append('/Users/pawan/Projects/alphamatrix/backend')

from app.core.redis import redis_client

async def clear():
    print("Clearing Redis cache keys...")
    # Since we don't have KEYS in our REST interface easily, let's delete the specific test keys
    # or flush the local/remote redis if possible.
    # Our RedisClient has delete() which takes multiple keys.
    keys_to_delete = []
    
    # Stocks
    for q in ["tcs", "infy", "reliance", "hdfcbank", "sbin", "wipro", "bel", "hal", "irctc", "mahabank"]:
        keys_to_delete.append(f"global_search:stock:{q}")
        keys_to_delete.append(f"global_search:all:{q}")
        
    # Partials
    for q in ["tata", "info", "maha", "reli", "bank"]:
        keys_to_delete.append(f"global_search:stock:{q}")
        keys_to_delete.append(f"global_search:all:{q}")
        
    # Funds
    for q in ["parag parikh flexi cap", "sbi small cap", "nippon india small cap", "hdfc flexi cap"]:
        keys_to_delete.append(f"global_search:fund:{q}")
        keys_to_delete.append(f"global_search:all:{q}")
        
    if keys_to_delete:
        await redis_client.delete(*keys_to_delete)
        print(f"Deleted {len(keys_to_delete)} keys.")

if __name__ == "__main__":
    asyncio.run(clear())
