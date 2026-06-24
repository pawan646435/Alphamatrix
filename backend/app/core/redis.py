import logging
import os
from typing import Optional
import httpx
import redis
from app.core.config import settings

logger = logging.getLogger("app.core.redis")

class RedisClient:
    def __init__(self):
        self.redis_client = None
        self.rest_url = settings.UPSTASH_REDIS_REST_URL
        self.rest_token = settings.UPSTASH_REDIS_REST_TOKEN
        self.redis_url = settings.REDIS_URL
        
        # Initialize TCP client if REDIS_URL is configured
        if self.redis_url:
            is_vercel = os.environ.get("VERCEL") is not None
            is_local_redis = "localhost" in self.redis_url or "127.0.0.1" in self.redis_url
            
            if is_vercel and is_local_redis:
                logger.info("Skipping local TCP Redis connection in Vercel serverless environment.")
                self.redis_client = None
            else:
                try:
                    self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
                    self.redis_client.ping()
                    logger.info("Connected to Redis successfully via TCP.")
                except Exception as e:
                    logger.error(f"Failed to connect to TCP Redis at {self.redis_url}: {e}")
                    self.redis_client = None

        # Check if Upstash REST is active
        if not self.redis_client and self.rest_url and self.rest_token:
            logger.info("Using Upstash Redis REST API client.")
            # Normalize REST URL to ensure no trailing slash
            if self.rest_url.endswith("/"):
                self.rest_url = self.rest_url[:-1]

    async def get(self, key: str) -> Optional[str]:
        if self.redis_client:
            try:
                return self.redis_client.get(key)
            except Exception as e:
                logger.error(f"TCP Redis GET failed: {e}")
                return None
                
        if self.rest_url and self.rest_token:
            try:
                async with httpx.AsyncClient() as client:
                    headers = {"Authorization": f"Bearer {self.rest_token}"}
                    response = await client.post(
                        self.rest_url,
                        json=["GET", key],
                        headers=headers,
                        timeout=5.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        # Upstash REST returns {"result": value}
                        return data.get("result")
            except Exception as e:
                logger.error(f"Upstash Redis REST GET failed: {e}")
                return None
        return None

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        if self.redis_client:
            try:
                self.redis_client.setex(key, seconds, value)
                return True
            except Exception as e:
                logger.error(f"TCP Redis SETEX failed: {e}")
                return False
                
        if self.rest_url and self.rest_token:
            try:
                async with httpx.AsyncClient() as client:
                    headers = {"Authorization": f"Bearer {self.rest_token}"}
                    response = await client.post(
                        self.rest_url,
                        json=["SET", key, value, "EX", str(seconds)],
                        headers=headers,
                        timeout=5.0
                    )
                    if response.status_code == 200:
                        return True
            except Exception as e:
                logger.error(f"Upstash Redis REST SETEX failed: {e}")
                return False
        return False

    async def delete(self, *keys: str) -> bool:
        if self.redis_client:
            try:
                self.redis_client.delete(*keys)
                return True
            except Exception as e:
                logger.error(f"TCP Redis DELETE failed: {e}")
                return False
                
        if self.rest_url and self.rest_token:
            try:
                async with httpx.AsyncClient() as client:
                    headers = {"Authorization": f"Bearer {self.rest_token}"}
                    for key in keys:
                        await client.post(
                            self.rest_url,
                            json=["DEL", key],
                            headers=headers,
                            timeout=5.0
                        )
                    return True
            except Exception as e:
                logger.error(f"Upstash Redis REST DELETE failed: {e}")
                return False
        return False

# Singleton instance
redis_client = RedisClient()
