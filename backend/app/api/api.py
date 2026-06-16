from fastapi import APIRouter
from app.api.v1 import auth, funds, ai, stocks, search

api_router = APIRouter()

# Mount endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(funds.router, prefix="/funds", tags=["funds"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(search.router, prefix="/search", tags=["search"])

