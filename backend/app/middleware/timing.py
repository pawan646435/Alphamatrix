"""
Request timing middleware for AlphaMatrix API.

Logs every request with structured fields:
  - method, path, status, duration_ms
  - cache_hit flag when X-Cache-Hit header is set

Example log output:
  GET /api/v1/search?query=tcs  42ms  status=200  cache=hit
  GET /api/v1/stocks/list        831ms status=200  cache=miss
  GET /api/v1/stocks/detail/TCS  23ms  status=200  cache=hit
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("app.timing")


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Measures wall-clock time for every HTTP request.
    Logs structured timing data at INFO level.
    """
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        # Read cache hint from response header (set by route handlers)
        cache_status = response.headers.get("X-Cache", "miss")

        # Only log API routes, skip health checks and static assets
        path = request.url.path
        if path.startswith("/api/"):
            logger.info(
                "%s %s  %dms  status=%d  cache=%s",
                request.method,
                path,
                duration_ms,
                response.status_code,
                cache_status,
            )

        # Expose timing to caller via response header
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        return response
