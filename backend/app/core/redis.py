import logging
import os
from typing import Optional
import httpx
import redis
from app.core.config import settings

logger = logging.getLogger("app.core.redis")

# ---------------------------------------------------------------------------
# Shared persistent httpx client for Upstash REST API calls.
# Creating a new AsyncClient per request wastes connection setup time.
# A module-level client is reused across all coroutines within the same worker.
# ---------------------------------------------------------------------------
_upstash_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    """Return (or lazily create) the shared Upstash HTTP client."""
    global _upstash_http_client
    if _upstash_http_client is None or _upstash_http_client.is_closed:
        # connection limits: max 20 concurrent connections to Upstash REST
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
        _upstash_http_client = httpx.AsyncClient(
            timeout=5.0,
            limits=limits,
        )
    return _upstash_http_client


class RedisClient:
    def __init__(self):
        self.redis_client = None
        self.rest_url = settings.UPSTASH_REDIS_REST_URL
        self.rest_token = settings.UPSTASH_REDIS_REST_TOKEN
        self.redis_url = settings.REDIS_URL
        self._initialized = False

    def _ensure_client(self):
        if self._initialized:
            return

        self._initialized = True

        # Normalize Upstash REST URL
        if self.rest_url and self.rest_url.endswith("/"):
            self.rest_url = self.rest_url[:-1]

        # Initialize TCP client only when REDIS_URL is configured
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

        if not self.redis_client and self.rest_url and self.rest_token:
            logger.info("Using Upstash Redis REST API (persistent connection pool).")

    async def get(self, key: str) -> Optional[str]:
        self._ensure_client()
        if self.redis_client:
            try:
                return self.redis_client.get(key)
            except Exception as e:
                logger.error(f"TCP Redis GET failed: {e}")
                return None

        if self.rest_url and self.rest_token:
            try:
                client = _get_http_client()
                response = await client.post(
                    self.rest_url,
                    json=["GET", key],
                    headers={"Authorization": f"Bearer {self.rest_token}"},
                )
                if response.status_code == 200:
                    return response.json().get("result")
            except Exception as e:
                logger.error(f"Upstash Redis REST GET failed: {e}")
                return None
        return None

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        self._ensure_client()
        if self.redis_client:
            try:
                self.redis_client.setex(key, seconds, value)
                return True
            except Exception as e:
                logger.error(f"TCP Redis SETEX failed: {e}")
                return False

        if self.rest_url and self.rest_token:
            try:
                client = _get_http_client()
                response = await client.post(
                    self.rest_url,
                    json=["SET", key, value, "EX", str(seconds)],
                    headers={"Authorization": f"Bearer {self.rest_token}"},
                )
                return response.status_code == 200
            except Exception as e:
                logger.error(f"Upstash Redis REST SETEX failed: {e}")
                return False
        return False

    async def set_nx(self, key: str, value: str, ex: int) -> bool:
        """SET key value EX seconds NX — atomic lock acquisition.
        Returns True if the key was set (lock acquired), False if already exists.
        """
        self._ensure_client()
        if self.redis_client:
            try:
                result = self.redis_client.set(key, value, ex=ex, nx=True)
                return result is not None  # None means key already existed
            except Exception as e:
                logger.error(f"TCP Redis SET NX failed: {e}")
                return True  # Fail open: if Redis is broken, allow ingestion

        if self.rest_url and self.rest_token:
            try:
                client = _get_http_client()
                response = await client.post(
                    self.rest_url,
                    json=["SET", key, value, "EX", str(ex), "NX"],
                    headers={"Authorization": f"Bearer {self.rest_token}"},
                )
                if response.status_code == 200:
                    result = response.json().get("result")
                    return result == "OK"   # "OK" = set, null = already existed
                return True  # Fail open on HTTP errors
            except Exception as e:
                logger.error(f"Upstash Redis REST SET NX failed: {e}")
                return True  # Fail open
        return True  # No Redis configured — allow ingestion

    async def delete(self, *keys: str) -> bool:
        self._ensure_client()
        if self.redis_client:
            try:
                self.redis_client.delete(*keys)
                return True
            except Exception as e:
                logger.error(f"TCP Redis DELETE failed: {e}")
                return False

        if self.rest_url and self.rest_token:
            try:
                client = _get_http_client()
                for key in keys:
                    await client.post(
                        self.rest_url,
                        json=["DEL", key],
                        headers={"Authorization": f"Bearer {self.rest_token}"},
                    )
                return True
            except Exception as e:
                logger.error(f"Upstash Redis REST DELETE failed: {e}")
                return False
        return False

    async def keys(self, pattern: str) -> list:
        self._ensure_client()
        if self.redis_client:
            try:
                return self.redis_client.keys(pattern)
            except Exception as e:
                logger.error(f"TCP Redis KEYS failed: {e}")
                return []

        if self.rest_url and self.rest_token:
            try:
                client = _get_http_client()
                response = await client.post(
                    self.rest_url,
                    json=["KEYS", pattern],
                    headers={"Authorization": f"Bearer {self.rest_token}"},
                )
                if response.status_code == 200:
                    return response.json().get("result") or []
            except Exception as e:
                logger.error(f"Upstash Redis REST KEYS failed: {e}")
                return []
        return []

    async def delete_pattern(self, pattern: str) -> bool:
        matching_keys = await self.keys(pattern)
        if matching_keys:
            # Handle list conversion / slicing if matching_keys is large, but for lists it is tiny
            await self.delete(*[str(k) for k in matching_keys])
            return True
        return False

    async def expire(self, key: str, seconds: int) -> bool:
        """Set TTL on an existing key."""
        self._ensure_client()
        if self.redis_client:
            try:
                self.redis_client.expire(key, seconds)
                return True
            except Exception as e:
                logger.error(f"TCP Redis EXPIRE failed: {e}")
                return False

        if self.rest_url and self.rest_token:
            try:
                client = _get_http_client()
                response = await client.post(
                    self.rest_url,
                    json=["EXPIRE", key, str(seconds)],
                    headers={"Authorization": f"Bearer {self.rest_token}"},
                )
                return response.status_code == 200
            except Exception as e:
                logger.error(f"Upstash Redis REST EXPIRE failed: {e}")
                return False
        return False

    async def incr(self, key: str) -> int:
        """INCR key — atomic increment, creates key at 1 if missing.
        Returns 0 on any Redis error (fail open — same convention as
        zincrby/zrevrange below), so callers that compare the result against
        a threshold (e.g. rate limiting) treat a Redis outage as "not over
        the limit yet" rather than raising or blocking.
        """
        self._ensure_client()
        if self.redis_client:
            try:
                return int(self.redis_client.incr(key))
            except Exception as e:
                logger.error(f"TCP Redis INCR failed: {e}")
                return 0

        if self.rest_url and self.rest_token:
            try:
                client = _get_http_client()
                response = await client.post(
                    self.rest_url,
                    json=["INCR", key],
                    headers={"Authorization": f"Bearer {self.rest_token}"},
                )
                if response.status_code == 200:
                    result = response.json().get("result")
                    return int(result) if result is not None else 0
            except Exception as e:
                logger.error(f"Upstash Redis REST INCR failed: {e}")
                return 0
        return 0

    async def zincrby(self, key: str, increment: float, member: str) -> float:
        """Increment the score of a member in a sorted set. Creates if not exists."""
        self._ensure_client()
        if self.redis_client:
            try:
                return float(self.redis_client.zincrby(key, increment, member))
            except Exception as e:
                logger.error(f"TCP Redis ZINCRBY failed: {e}")
                return 0.0

        if self.rest_url and self.rest_token:
            try:
                client = _get_http_client()
                response = await client.post(
                    self.rest_url,
                    json=["ZINCRBY", key, str(increment), member],
                    headers={"Authorization": f"Bearer {self.rest_token}"},
                )
                if response.status_code == 200:
                    result = response.json().get("result")
                    return float(result) if result is not None else 0.0
            except Exception as e:
                logger.error(f"Upstash Redis REST ZINCRBY failed: {e}")
                return 0.0
        return 0.0

    async def zrevrange(self, key: str, start: int, stop: int, withscores: bool = False):
        """Return members of sorted set in descending score order."""
        self._ensure_client()
        cmd = ["ZREVRANGE", key, str(start), str(stop)]
        if withscores:
            cmd.append("WITHSCORES")

        if self.redis_client:
            try:
                if withscores:
                    return self.redis_client.zrevrange(key, start, stop, withscores=True)
                return self.redis_client.zrevrange(key, start, stop)
            except Exception as e:
                logger.error(f"TCP Redis ZREVRANGE failed: {e}")
                return []

        if self.rest_url and self.rest_token:
            try:
                client = _get_http_client()
                response = await client.post(
                    self.rest_url,
                    json=cmd,
                    headers={"Authorization": f"Bearer {self.rest_token}"},
                )
                if response.status_code == 200:
                    result = response.json().get("result") or []
                    if withscores and result:
                        # Upstash returns flat [member, score, member, score, ...]
                        pairs = []
                        for i in range(0, len(result), 2):
                            if i + 1 < len(result):
                                pairs.append((result[i], float(result[i + 1])))
                        return pairs
                    return result
            except Exception as e:
                logger.error(f"Upstash Redis REST ZREVRANGE failed: {e}")
                return []
        return []

    async def set(self, key: str, value: str, ex: int = None, nx: bool = False) -> bool:
        """General SET with optional EX and NX flags (delegates to set_nx if nx=True)."""
        if nx and ex:
            return await self.set_nx(key, value, ex=ex)
        return await self.setex(key, ex or 3600, value)


# Singleton instance
redis_client = RedisClient()
