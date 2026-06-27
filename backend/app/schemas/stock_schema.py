from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import List, Optional

# Stock Price History schemas
class StockPriceHistoryBase(BaseModel):
    date: date
    close: float

class StockPriceHistoryCreate(StockPriceHistoryBase):
    symbol: str

class StockPriceHistoryResponse(StockPriceHistoryBase):
    id: int
    symbol: str
    model_config = ConfigDict(from_attributes=True)

# Stock Master schemas
class StockMasterBase(BaseModel):
    symbol: str
    company_name: str
    isin: Optional[str] = None
    sector: str
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    debt_equity: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None

class StockMasterCreate(StockMasterBase):
    pass

class StockMasterResponse(StockMasterBase):
    cagr_1y: Optional[float] = None
    cagr_3y: Optional[float] = None
    cagr_5y: Optional[float] = None
    alpha_score: Optional[float] = None
    ai_summary: Optional[str] = None
    last_updated: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

from typing import List, Optional, Dict

# Detailed Response including history (for charting)
class StockDetailResponse(BaseModel):
    stock: StockMasterResponse
    price_history: List[StockPriceHistoryBase]
    alpha_score_breakdown: Optional[Dict[str, float]] = None
    
    model_config = ConfigDict(from_attributes=True)

# Comparison Response schema
class StockComparisonResponse(BaseModel):
    stock1: StockMasterResponse
    stock2: StockMasterResponse
    comparison_verdict: str
    price_history1: List[StockPriceHistoryBase]
    price_history2: List[StockPriceHistoryBase]
    alpha_score_breakdown1: Optional[Dict[str, float]] = None
    alpha_score_breakdown2: Optional[Dict[str, float]] = None
    
    model_config = ConfigDict(from_attributes=True)


# Short version for list grids
class StockGridItem(BaseModel):
    symbol: str
    company_name: str
    sector: str
    cagr_1y: Optional[float] = None
    cagr_3y: Optional[float] = None
    cagr_5y: Optional[float] = None
    pe_ratio: Optional[float] = None
    roe: Optional[float] = None
    alpha_score: Optional[float] = None
    beta: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)

# Watchlist schemas
class WatchlistItemBase(BaseModel):
    symbol: str

class WatchlistItemResponse(WatchlistItemBase):
    id: int
    email: str
    added_at: datetime
    stock: Optional[StockGridItem] = None
    
    model_config = ConfigDict(from_attributes=True)

class WatchlistAddRequest(BaseModel):
    symbol: str

class WatchlistRemoveRequest(BaseModel):
    symbol: str

class WatchlistAnalyticsResponse(BaseModel):
    health_score: float
    ai_summary: str
    strongest_position: str
    weakest_position: str
    risk_concentration: str
    sector_exposure: str
    
    model_config = ConfigDict(from_attributes=True)

# Sector Lab schemas
class SectorDetailsResponse(BaseModel):
    sector: str
    sector_score: float
    growth_drivers: List[str]
    major_risks: List[str]
    top_stocks: List[StockGridItem]
    ai_outlook: str
    
    model_config = ConfigDict(from_attributes=True)
