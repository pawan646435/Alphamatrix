import time
import logging
from typing import Dict, Tuple, Optional
from fastapi import Request, HTTPException, status
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
