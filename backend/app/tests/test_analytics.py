import pytest
import pandas as pd
from datetime import date, timedelta
from app.services.analytics import calculate_cagr, calculate_risk_metrics

def test_calculate_cagr():
    # Create 3 years of daily NAVs with a steady 10% CAGR
    # 3 years * 365 = 1095 days
    start_date = date(2023, 1, 1)
    nav_list = []
    
    # 10% annual return -> daily return factor
    cagr_target = 0.10
    days = 3 * 365
    
    for i in range(days + 1):
        d = start_date + timedelta(days=i)
        # NAV starts at 10.0 and grows exponentially
        nav = 10.0 * ((1 + cagr_target) ** (i / 365.25))
        nav_list.append((d, nav))
        
    df = pd.DataFrame(nav_list, columns=['date', 'nav'])
    df['date'] = pd.to_datetime(df['date'])
    
    cagr_3y = calculate_cagr(df, 3)
    assert cagr_3y is not None
    assert abs(cagr_3y - cagr_target) < 0.005  # Within 0.5% tolerance due to day offsets

def test_calculate_risk_metrics():
    import numpy as np
    # Generate mock NAV lists
    start_date = date(2023, 1, 1)
    fund_navs = []
    bench_navs = []
    
    fund_nav = 100.0
    bench_nav = 100.0
    
    fund_navs.append((start_date, fund_nav))
    bench_navs.append((start_date, bench_nav))
    
    # Generate 120 days of data with simulated volatility
    for i in range(1, 120):
        d = start_date + timedelta(days=i)
        
        # Base returns + sine wave oscillation to create standard deviation > 0
        fund_ret = 0.00047 + 0.005 * np.sin(i)
        bench_ret = 0.00039 + 0.004 * np.cos(i)
        
        fund_nav = fund_nav * (1 + fund_ret)
        bench_nav = bench_nav * (1 + bench_ret)
        
        fund_navs.append((d, fund_nav))
        bench_navs.append((d, bench_nav))
        
    metrics = calculate_risk_metrics(fund_navs, bench_navs, rf_annual=0.06)
    
    assert metrics["sharpe_ratio"] is not None
    assert metrics["sortino_ratio"] is not None
    assert metrics["beta"] is not None
    assert metrics["alpha"] is not None
    
    # Check that we computed reasonable numbers
    assert isinstance(metrics["sharpe_ratio"], float)
    assert isinstance(metrics["beta"], float)
