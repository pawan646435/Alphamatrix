from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# Structured filters parsed from natural language query
class ParsedFilters(BaseModel):
    category: Optional[str] = Field(
        default=None, 
        description="Fund category: 'Large Cap', 'Mid Cap', 'Small Cap', 'Sectoral', 'Index' or None if not specified"
    )
    min_cagr_1y: Optional[float] = Field(
        default=None,
        description="Minimum 1-year CAGR expected as float (e.g. 15.0 for 15%)"
    )
    min_cagr_3y: Optional[float] = Field(
        default=None, 
        description="Minimum 3-year CAGR expected as float (e.g. 15.0 for 15%)"
    )
    max_expense_ratio: Optional[float] = Field(
        default=None, 
        description="Maximum expense ratio allowed as float (e.g. 1.5 for 1.5%)"
    )
    min_sharpe_ratio: Optional[float] = Field(
        default=None, 
        description="Minimum Sharpe ratio allowed"
    )
    max_pe_ratio: Optional[float] = Field(
        default=None, 
        description="Maximum PE ratio allowed"
    )
    sort_by: Optional[str] = Field(
        default=None, 
        description="Field to sort by: 'cagr_3y', 'cagr_5y', 'sharpe_ratio', 'sortino_ratio', 'alpha', 'beta', 'expense_ratio'"
    )
    sort_order: str = Field(
        default="desc", 
        description="'asc' or 'desc'"
    )

# Semantic Query API contract
class AISemanticQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language search term e.g. 'Show me high sharpe mid cap funds'")

class AISemanticQueryResponse(BaseModel):
    query: str
    parsed_filters: ParsedFilters
    sql_explanation: str = Field(..., description="Explanation of what was parsed and how it translates to database filtering")
    matched_funds_count: int

# Chat messages schema
class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text content")

# AI Chat API contract
class AIChatRequest(BaseModel):
    message: str
    scheme_code: Optional[int] = None  # If chatting within a specific fund detail context
    history: List[ChatMessage] = []

class AIChatResponse(BaseModel):
    response: str
    scheme_code: Optional[int] = None
    sources: List[str] = Field(default=[], description="List of funds or variables injected into LLM context")
