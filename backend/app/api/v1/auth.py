from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Mock authentication validation
    if form_data.username == "admin@alphamatrix.com" and form_data.password == "admin123":
        return {"access_token": "mock-admin-token-alphamatrix", "token_type": "bearer"}
    
    # Allow any username/password combination for local trial
    if len(form_data.password) >= 6:
         return {"access_token": f"mock-user-token-{form_data.username.split('@')[0]}", "token_type": "bearer"}
         
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password (password must be at least 6 characters)",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.post("/signup", response_model=UserResponse)
async def signup(email: EmailStr, password: str):
    if len(password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters"
        )
    return {
        "id": 1,
        "email": email,
        "is_active": True
    }

@router.get("/me", response_model=UserResponse)
async def get_me(token: str = Depends(oauth2_scheme)):
    email = "user@alphamatrix.com"
    if "admin" in token:
        email = "admin@alphamatrix.com"
    elif "mock-user-token-" in token:
        email = f"{token.replace('mock-user-token-', '')}@alphamatrix.com"
        
    return {
        "id": 1,
        "email": email,
        "is_active": True
    }
