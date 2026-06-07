from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import List, Optional

# NAV History schemas
class NAVHistoryBase(BaseModel):
    date: date
    nav: float

class NAVHistoryCreate(NAVHistoryBase):
    scheme_code: int

class NAVHistoryResponse(NAVHistoryBase):
    id: int
    scheme_code: int
    model_config = ConfigDict(from_attributes=True)

# Fund Master schemas
class FundMasterBase(BaseModel):
    scheme_code: int
    isin: Optional[str] = None
    fund_name: str
    category: str
    sub_category: Optional[str] = None
    pe_ratio: Optional[float] = None
    expense_ratio: Optional[float] = None

class FundMasterCreate(FundMasterBase):
    pass

class FundMasterUpdateMetrics(BaseModel):
    cagr_1y: Optional[float] = None
    cagr_3y: Optional[float] = None
    cagr_5y: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    ai_summary: Optional[str] = None

class FundMasterResponse(FundMasterBase):
    cagr_1y: Optional[float] = None
    cagr_3y: Optional[float] = None
    cagr_5y: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    ai_summary: Optional[str] = None
    last_updated: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Detailed Response including NAV history (for charting)
class FundDetailResponse(BaseModel):
    fund: FundMasterResponse
    nav_history: List[NAVHistoryBase]
    
    model_config = ConfigDict(from_attributes=True)

# Short version for list grids
class FundGridItem(BaseModel):
    scheme_code: int
    fund_name: str
    category: str
    cagr_1y: Optional[float] = None
    cagr_3y: Optional[float] = None
    cagr_5y: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    alpha: Optional[float] = None
    pe_ratio: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)

# Schema for manual sync operations
class SyncResponse(BaseModel):
    status: str
    message: str
    scheme_code: int
    records_synced: int
