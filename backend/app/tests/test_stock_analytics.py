import pytest
from app.workers.stock_ingestion import calculate_alpha_score

def test_calculate_alpha_score_high_quality():
    # Test a high quality stock (e.g., TCS with high ROE, low Debt/Equity, and strong 1Y returns)
    stock = {
        "symbol": "TCS",
        "roe": 42.0,
        "debt_equity": 0.02,
        "pe_ratio": 28.0,
        "pb_ratio": 12.0,
        "target_beta": 0.75
    }
    # 25% 1Y CAGR, 15% 3Y CAGR (momentum acceleration)
    score = calculate_alpha_score(stock, cagr_1y=0.25, cagr_3y=0.15)
    
    # High quality should yield a very strong score
    assert 0.0 <= score <= 100.0
    assert score > 70.0

def test_calculate_alpha_score_high_risk_leverage():
    # Test a high-leverage, underperforming stock
    stock = {
        "symbol": "HIGH_RISK",
        "roe": 5.0,
        "debt_equity": 2.5,
        "pe_ratio": 45.0,
        "pb_ratio": 8.0,
        "target_beta": 1.6
    }
    # Poor performance
    score = calculate_alpha_score(stock, cagr_1y=-0.10, cagr_3y=0.02)
    
    # Should yield a low score due to leverage, valuation and poor returns
    assert 0.0 <= score <= 100.0
    assert score < 40.0

@pytest.mark.anyio
async def test_market_regime_diagnostics():
    from app.services.ai_agent import get_market_regime_diagnostics
    res = await get_market_regime_diagnostics()
    assert "regime" in res
    assert "confidence" in res
    assert "explanation" in res
    assert res["regime"] in ["RISK ON", "RISK OFF", "NEUTRAL"]

