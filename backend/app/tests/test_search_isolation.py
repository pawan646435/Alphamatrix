import pytest
from sqlalchemy import text
from app.api.v1.search import global_search
from app.core.database import async_session_maker, init_db

@pytest.mark.asyncio
async def test_search_isolation_stocks():
    # Initialize DB schema and virtual tables if not already present
    await init_db()
    
    async with async_session_maker() as session:
        # Seed test data into database and FTS5 tables
        # Clear existing test data in indices first
        await session.execute(text("DELETE FROM stock_search_index"))
        await session.execute(text("DELETE FROM fund_search_index"))
        await session.execute(text("DELETE FROM stock_masters"))
        
        # Insert a mock stock
        await session.execute(text("""
            INSERT INTO stock_masters (symbol, company_name, sector, industry, cagr_3y, alpha_score)
            VALUES ('TCS', 'Tata Consultancy Services Limited', 'IT', 'Software', 15.0, 85.0)
        """))
        await session.execute(text("""
            INSERT INTO stock_search_index (symbol, company_name, exchange)
            VALUES ('TCS', 'Tata Consultancy Services Limited', 'NSE')
        """))
        
        # Insert a mock mutual fund
        await session.execute(text("""
            INSERT INTO fund_search_index (scheme_code, scheme_name)
            VALUES ('120687', 'Parag Parikh Flexi Cap Fund - Direct Plan')
        """))
        await session.commit()
        
        # 1. Search for 'TCS' in 'stock' context
        res_stock = await global_search(query="TCS", type="stock", db=session)
        assert len(res_stock) > 0
        assert all(r["type"] == "stock" for r in res_stock)
        assert any(r["symbol"] == "TCS" for r in res_stock)
        
        # 2. Search for 'TCS' in 'fund' context
        res_fund_tcs = await global_search(query="TCS", type="fund", db=session)
        # Should return no results because TCS is a stock and we are searching funds
        assert len(res_fund_tcs) == 0 or all(r["type"] == "fund" for r in res_fund_tcs)
        assert not any(r["type"] == "stock" for r in res_fund_tcs)

        # 3. Search for 'Parag' in 'fund' context
        res_fund = await global_search(query="Parag", type="fund", db=session)
        assert len(res_fund) > 0
        assert all(r["type"] == "fund" for r in res_fund)
        assert any("Parag" in r["name"] for r in res_fund)

        # 4. Search for 'Parag' in 'stock' context
        res_stock_parag = await global_search(query="Parag", type="stock", db=session)
        # Should return no results or only stock results
        assert len(res_stock_parag) == 0 or all(r["type"] == "stock" for r in res_stock_parag)
        assert not any(r["type"] == "fund" for r in res_stock_parag)
