import json
import logging
from typing import Optional, Any
from app.core.redis import redis_client

logger = logging.getLogger("app.services.cache_service")

# TTL definitions (in seconds)
TTL_SEARCH = 3600      # 1 hour
TTL_NEWS = 900         # 15 minutes
TTL_DASHBOARD = 300    # 5 minutes
TTL_AI_ANALYSIS = 86400 # 24 hours

class CacheService:
    @staticmethod
    async def get_search(query: str, type_str: Optional[str]) -> Optional[list]:
        key = f"global_search:{type_str or 'all'}:{query.strip().lower()}"
        data = await redis_client.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception as e:
                logger.error(f"Failed to parse cached search data for {key}: {e}")
        return None

    @staticmethod
    async def set_search(query: str, type_str: Optional[str], results: list) -> bool:
        key = f"global_search:{type_str or 'all'}:{query.strip().lower()}"
        try:
            return await redis_client.setex(key, TTL_SEARCH, json.dumps(results))
        except Exception as e:
            logger.error(f"Failed to cache search results for {key}: {e}")
            return False

    @staticmethod
    async def get_dashboard_stats() -> Optional[dict]:
        key = "dashboard:stats"
        data = await redis_client.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception as e:
                logger.error(f"Failed to parse cached dashboard stats: {e}")
        return None

    @staticmethod
    async def set_dashboard_stats(stats: dict) -> bool:
        key = "dashboard:stats"
        try:
            return await redis_client.setex(key, TTL_DASHBOARD, json.dumps(stats))
        except Exception as e:
            logger.error(f"Failed to cache dashboard stats: {e}")
            return False

    @staticmethod
    async def get_news_feed(stream: str, category: str) -> Optional[list]:
        key = f"news_feed:{stream}:{category}"
        data = await redis_client.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception as e:
                logger.error(f"Failed to parse cached news feed for {stream}:{category}: {e}")
        return None

    @staticmethod
    async def set_news_feed(stream: str, category: str, news: list) -> bool:
        key = f"news_feed:{stream}:{category}"
        try:
            return await redis_client.setex(key, TTL_NEWS, json.dumps(news))
        except Exception as e:
            logger.error(f"Failed to cache news feed for {stream}:{category}: {e}")
            return False

    @staticmethod
    async def get_ai_briefing(identifier: str) -> Optional[str]:
        # identifier can be symbol (stock) or scheme_code (fund)
        key = f"ai_briefing:{identifier.strip().upper()}"
        return await redis_client.get(key)

    @staticmethod
    async def set_ai_briefing(identifier: str, briefing: str) -> bool:
        key = f"ai_briefing:{identifier.strip().upper()}"
        try:
            return await redis_client.setex(key, TTL_AI_ANALYSIS, briefing)
        except Exception as e:
            logger.error(f"Failed to cache AI briefing for {identifier}: {e}")
            return False

    @staticmethod
    async def invalidate_fund(scheme_code: Any) -> bool:
        key = f"fund_detail:{scheme_code}"
        try:
            await redis_client.delete(key)
            # Also invalidate dashboard stats since they depend on fund data
            await redis_client.delete("dashboard:stats")
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate fund cache for {scheme_code}: {e}")
            return False

    @staticmethod
    async def invalidate_stock(symbol: str) -> bool:
        key = f"stock_detail:{symbol.strip().upper()}"
        try:
            await redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate stock cache for {symbol}: {e}")
            return False
