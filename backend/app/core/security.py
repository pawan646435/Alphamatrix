import time
import logging
from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger("app.core.security")

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# JWT Creation
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# --- Rate Limiter ---
# Redis-backed fixed-window rate limiter (key: ratelimit:{ip}:{window_bucket}).
#
# Replaces the previous in-process `rate_limit_store` dict, which lived in a
# single Python process's memory — on Vercel, each serverless invocation can
# land on a different (or freshly cold-started) instance, so that dict never
# actually accumulated a global per-IP count in production; it only limited
# requests that happened to hit the same warm instance. Same class of bug as
# the stock pipeline's old in-memory ingestion lock, fixed the same way here:
# move the counter into Redis so it's shared across all instances.
#
# This is a fixed window (bucketed by RATE_LIMIT_PERIOD-second intervals),
# not the previous sliding log — simpler to implement atomically with a
# single INCR, at the cost of allowing up to ~2x the configured rate right
# at a window boundary (a well-known, generally-accepted fixed-window
# tradeoff). If stricter enforcement at the boundary is needed later, this
# would need to move to a Redis sorted-set sliding-log or a Lua script.
#
# Fail-open on Redis errors: reuses the same convention as
# RedisClient.set_nx/zincrby elsewhere in this codebase (e.g. the QStash
# pipeline locks) — if Redis is down, requests are allowed through rather
# than blocked or the endpoint erroring. This was a deliberate choice to
# stay consistent with the rest of the codebase rather than invent a new
# policy just for rate limiting; the tradeoff is that abuse/DoS traffic
# would go unthrottled for the duration of a Redis outage.
async def check_rate_limit(request: Request):
    """
    Rate limiting dependency.
    Prevents abuse by tracking requests per IP, shared across all instances via Redis.
    """
    from app.core.redis import redis_client

    client_ip = request.client.host if request.client else "unknown-ip"
    window_bucket = int(time.time() // settings.RATE_LIMIT_PERIOD)
    key = f"ratelimit:{client_ip}:{window_bucket}"

    count = await redis_client.incr(key)
    if count == 1:
        # First request in this window — set the bucket to expire so it's
        # self-cleaning (a couple of seconds of slack beyond the window
        # itself is harmless and avoids a race with the INCR above).
        try:
            await redis_client.expire(key, settings.RATE_LIMIT_PERIOD + 5)
        except Exception as e:
            logger.error(f"Failed to set TTL on rate limit key {key}: {e}")

    if count > settings.RATE_LIMIT_CALLS:
        logger.warning(f"Rate limit exceeded for client: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )

    return True

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx

security_scheme = HTTPBearer(auto_error=False)

# Fetch Google public keys to verify Firebase ID tokens signature
firebase_keys = {}
last_fetched_keys = 0

async def fetch_firebase_keys():
    global firebase_keys, last_fetched_keys
    now = time.time()
    if not firebase_keys or now - last_fetched_keys > 3600:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get("https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com")
                if res.status_code == 200:
                    firebase_keys = res.json()
                    last_fetched_keys = now
        except Exception as e:
            logger.error(f"Failed to fetch Firebase public keys: {e}")

async def get_current_user_email(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)) -> str:
    """
    Decodes the Firebase JWT from Authorization Header.
    Falls back gracefully to a mock email if mock tokens are used or if Firebase credentials are mock.
    """
    default_email = "user@alphamatrix.io"
    if not credentials:
        return default_email

    token = credentials.credentials
    if not token or token.strip() == "" or token.lower() in ("null", "undefined"):
        return default_email

    # Handle developer fallback mock tokens
    if token.startswith("mock-user-token-"):
        username = token.replace("mock-user-token-", "")
        return f"{username}@alphamatrix.io"
    if token == "mock-google-id-token-payload-alphamatrix":
        return "trial-google@alphamatrix.io"
    if token == "mock-admin-token-alphamatrix":
        return "admin@alphamatrix.com"

    # Real Firebase verification
    try:
        # If the token is not mock and doesn't look like a JWT, treat it as guest fallback
        if len(token.split(".")) != 3:
            return default_email

        await fetch_firebase_keys()
        # Decode without verification first to get kid from header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid or kid not in firebase_keys:
            # Firebase keys are not available — reject non-mock token
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Firebase authentication is not configured. Use mock tokens for development."
            )
            
        # Verify signature using correct certificate key
        certificate = firebase_keys[kid]
        payload = jwt.decode(token, certificate, algorithms=["RS256"], options={"verify_aud": False})
        email = payload.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token: missing email")
        return email
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Firebase JWT decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access credentials."
        )

