import time
import logging
from typing import Dict, Tuple, Optional
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
# Sliding window rate limiter
# Key: IP Address, Value: List of request timestamps
rate_limit_store: Dict[str, list] = {}

async def check_rate_limit(request: Request):
    """
    Rate limiting dependency.
    Prevents abuse by tracking requests per IP.
    """
    client_ip = request.client.host if request.client else "unknown-ip"
    current_time = time.time()
    
    # Clean up older logs
    window_start = current_time - settings.RATE_LIMIT_PERIOD
    
    # Get request logs for client
    client_logs = rate_limit_store.get(client_ip, [])
    client_logs = [t for t in client_logs if t > window_start]
    
    if len(client_logs) >= settings.RATE_LIMIT_CALLS:
        logger.warning(f"Rate limit exceeded for client: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
        
    client_logs.append(current_time)
    rate_limit_store[client_ip] = client_logs
    
    # Header injections (standard rate limiting practice)
    # We can inject these into response headers if needed, but standard dependency check is sufficient
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

