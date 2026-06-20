import os
import pytest
import asyncio
from sqlalchemy import text

# Force test database URL before any application code imports settings
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_alphamatrix.db"

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Make sure we clean up the test database file after the session
    yield
    test_db_path = "./test_alphamatrix.db"
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass
