import os
import sys
import asyncio
import tempfile
import pytest
from typing import Generator

# Use a temp file for test DB so FTS5 works
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".test.db")

# Override settings BEFORE any app module imports
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db_path}"
os.environ["REDIS_URL"] = ""
os.environ["UPSTASH_REDIS_REST_URL"] = ""
os.environ["UPSTASH_REDIS_REST_TOKEN"] = ""
os.environ["GROQ_API_KEY"] = ""
os.environ["SECRET_KEY"] = "TEST_SECRET_KEY_DONT_USE_IN_PROD"
os.environ["RATE_LIMIT_CALLS"] = "10000"
os.environ["RATE_LIMIT_PERIOD"] = "3600"
os.environ["VERCEL"] = "1"  # Prevents startup event from running async seeding

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.database import get_db, init_db, async_session_maker
from app.core.security import get_password_hash


async def override_get_db():
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _init_db():
    """Initialize the test database and seed data."""
    from app.models.fund import FundMaster
    from app.models.user import User
    from app.models.stock import StockMaster, StockPriceHistory, WatchlistItem

    async def init():
        await init_db()

        async with async_session_maker() as session:
            stocks = [
                StockMaster(symbol="RELIANCE", company_name="Reliance Industries Ltd", sector="Energy", industry="Oil & Gas", market_cap=1700000.0, pe_ratio=28.5, pb_ratio=9.2, roe=12.4, debt_equity=0.45, dividend_yield=0.35, beta=1.2, cagr_1y=8.5, cagr_3y=22.1, cagr_5y=18.3, alpha_score=72.5),
                StockMaster(symbol="TCS", company_name="Tata Consultancy Services Ltd", sector="IT", industry="Software", market_cap=1400000.0, pe_ratio=32.1, pb_ratio=15.8, roe=48.2, debt_equity=0.08, dividend_yield=1.1, beta=0.85, cagr_1y=12.3, cagr_3y=18.7, cagr_5y=16.2, alpha_score=68.0),
                StockMaster(symbol="HDFCBANK", company_name="HDFC Bank Ltd", sector="Banking", industry="Private Bank", market_cap=1200000.0, pe_ratio=20.4, pb_ratio=3.1, roe=15.6, debt_equity=0.0, dividend_yield=0.8, beta=1.05, cagr_1y=5.2, cagr_3y=14.9, cagr_5y=12.1, alpha_score=65.3),
                StockMaster(symbol="INFY", company_name="Infosys Ltd", sector="IT", industry="Software", market_cap=700000.0, pe_ratio=28.9, pb_ratio=12.4, roe=38.7, debt_equity=0.12, dividend_yield=1.5, beta=0.9, cagr_1y=15.1, cagr_3y=16.3, cagr_5y=14.8, alpha_score=70.1),
                StockMaster(symbol="SBIN", company_name="State Bank of India", sector="Banking", industry="PSU Bank", market_cap=600000.0, pe_ratio=10.2, pb_ratio=1.5, roe=14.8, debt_equity=0.0, dividend_yield=1.8, beta=1.3, cagr_1y=25.4, cagr_3y=20.6, cagr_5y=10.5, alpha_score=74.2),
            ]
            session.add_all(stocks)
            await session.commit()

        async with async_session_maker() as session:
            funds = [
                FundMaster(scheme_code=120687, fund_name="HDFC Nifty 50 Index Fund Direct Growth", isin="INF179K01XD3", category="Large Cap", sub_category="Index Fund", expense_ratio=0.35, alpha=0.12, beta=1.0, sharpe_ratio=0.85, cagr_1y=14.5, cagr_3y=16.2, cagr_5y=13.8),
                FundMaster(scheme_code=118550, fund_name="SBI Bluechip Fund Direct Growth", isin="INF200K01QX5", category="Large Cap", sub_category="Value Fund", expense_ratio=1.05, alpha=1.45, beta=0.92, sharpe_ratio=0.91, cagr_1y=18.2, cagr_3y=19.5, cagr_5y=15.1),
                FundMaster(scheme_code=122639, fund_name="ICICI Prudential Technology Direct Growth", isin="INF109K018P7", category="Sectoral", sub_category="Technology", expense_ratio=0.98, alpha=3.21, beta=1.15, sharpe_ratio=0.78, cagr_1y=28.3, cagr_3y=22.7, cagr_5y=19.4),
            ]
            session.add_all(funds)
            await session.commit()

        async with async_session_maker() as session:
            users = [
                User(email="test@example.com", hashed_password=get_password_hash("testpass123"), is_active=True, is_superuser=False),
                User(email="admin@example.com", hashed_password=get_password_hash("adminpass123"), is_active=True, is_superuser=True),
            ]
            session.add_all(users)
            await session.commit()

    asyncio.run(init())


# Initialize once at module import time
_init_db()

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield
    os.close(_test_db_fd)
    os.unlink(_test_db_path)


@pytest.fixture
def client() -> Generator:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/v1/auth/login", data={"username": "test@example.com", "password": "testpass123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client):
    resp = client.post("/api/v1/auth/login", data={"username": "admin@example.com", "password": "adminpass123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
