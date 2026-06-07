from datetime import date, timedelta
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
import numpy as np
from app.core.config import settings

def calculate_cagr(nav_df: pd.DataFrame, years: int) -> Optional[float]:
    """
    Calculate CAGR for a given number of years.
    Expects nav_df to have columns: 'date' (datetime) and 'nav' (float), sorted by date ascending.
    """
    if len(nav_df) < 2:
        return None
        
    latest_row = nav_df.iloc[-1]
    latest_date = latest_row['date']
    latest_nav = latest_row['nav']
    
    target_date = latest_date - pd.DateOffset(years=years)
    
    # Calculate absolute difference in days to target_date
    temp_df = nav_df.copy()
    temp_df['date_diff'] = (temp_df['date'] - target_date).abs()
    
    # Find the row with the minimum date difference
    best_idx = temp_df['date_diff'].idxmin()
    best_row = temp_df.loc[best_idx]
    
    # If the closest matching date is more than 30 days away, we don't have enough history
    if best_row['date_diff'].days > 30:
        return None
        
    start_nav = best_row['nav']
    start_date = best_row['date']
    
    # Calculate exact duration in years
    actual_days = (latest_date - start_date).days
    time_years = actual_days / 365.25
    
    # Ensure minimum duration threshold (e.g. at least 95% of target time)
    if time_years < (years * 0.95):
        return None
        
    if start_nav <= 0 or latest_nav <= 0:
        return None
        
    cagr = (latest_nav / start_nav) ** (1.0 / time_years) - 1.0
    return float(cagr)

def calculate_risk_metrics(
    fund_nav_list: List[Tuple[date, float]], 
    bench_nav_list: List[Tuple[date, float]], 
    rf_annual: float = None
) -> Dict[str, Any]:
    """
    Calculate Sharpe, Sortino, Alpha, and Beta.
    fund_nav_list: list of (date, nav) sorted by date ascending.
    bench_nav_list: list of (date, nav) sorted by date ascending.
    """
    if rf_annual is None:
        rf_annual = settings.RISK_FREE_RATE
        
    # Default outputs
    results = {
        "sharpe_ratio": None,
        "sortino_ratio": None,
        "alpha": None,
        "beta": None,
        "cagr_1y": None,
        "cagr_3y": None,
        "cagr_5y": None
    }
    
    if len(fund_nav_list) < 30:
        # Not enough data points to compute risk metrics
        return results

    # Convert to DataFrames
    fund_df = pd.DataFrame(fund_nav_list, columns=['date', 'nav'])
    fund_df['date'] = pd.to_datetime(fund_df['date'])
    fund_df = fund_df.sort_values('date').reset_index(drop=True)
    
    # Compute CAGR 1Y, 3Y and 5Y
    results["cagr_1y"] = calculate_cagr(fund_df, 1)
    results["cagr_3y"] = calculate_cagr(fund_df, 3)
    results["cagr_5y"] = calculate_cagr(fund_df, 5)
    
    # Compute daily returns
    fund_df['returns'] = fund_df['nav'].pct_change()
    
    # Need returns to compute volatility metrics
    clean_fund = fund_df.dropna(subset=['returns'])
    if len(clean_fund) < 20:
        return results
        
    # Annualize factor (approx trading days in a year)
    trading_days = 252
    
    # Mean and volatility of daily returns
    mean_daily_return = clean_fund['returns'].mean()
    std_daily_return = clean_fund['returns'].std(ddof=1)
    
    # Annualized parameters
    annualized_return = mean_daily_return * trading_days
    annualized_vol = std_daily_return * np.sqrt(trading_days)
    
    # Daily risk free rate
    rf_daily = rf_annual / trading_days
    
    # 1. Sharpe Ratio
    if std_daily_return > 0:
        sharpe = (annualized_return - rf_annual) / annualized_vol
        results["sharpe_ratio"] = float(sharpe)
        
    # 2. Sortino Ratio
    # Downside deviation uses standard deviation of negative returns relative to 0
    downside_returns = clean_fund['returns'].copy()
    downside_returns[downside_returns > 0] = 0
    
    # Math: Downside Std = sqrt(mean(squared_negative_returns))
    downside_var = np.mean(np.square(downside_returns))
    downside_std = np.sqrt(downside_var)
    
    # Annualized Downside Volatility
    annualized_downside_vol = downside_std * np.sqrt(trading_days)
    
    if annualized_downside_vol > 0:
        sortino = (annualized_return - rf_annual) / annualized_downside_vol
        results["sortino_ratio"] = float(sortino)
        
    # 3. Alpha & Beta calculations (relative to benchmark)
    if bench_nav_list and len(bench_nav_list) >= 30:
        bench_df = pd.DataFrame(bench_nav_list, columns=['date', 'nav'])
        bench_df['date'] = pd.to_datetime(bench_df['date'])
        bench_df = bench_df.sort_values('date').reset_index(drop=True)
        bench_df['returns'] = bench_df['nav'].pct_change()
        
        # Merge on date to align returns
        merged = pd.merge(
            clean_fund[['date', 'returns']], 
            bench_df[['date', 'returns']], 
            on='date', 
            suffixes=('_fund', '_bench')
        ).dropna()
        
        if len(merged) >= 20:
            cov = merged['returns_fund'].cov(merged['returns_bench'])
            bench_var = merged['returns_bench'].var()
            
            if bench_var > 0:
                beta = cov / bench_var
                results["beta"] = float(beta)
                
                # Annualized benchmark return
                mean_bench_return = merged['returns_bench'].mean()
                annualized_bench_return = mean_bench_return * trading_days
                
                # CAPM Alpha = Fund_Return - [Rf + Beta * (Bench_Return - Rf)]
                alpha = annualized_return - (rf_annual + beta * (annualized_bench_return - rf_annual))
                results["alpha"] = float(alpha)
                
    return results
