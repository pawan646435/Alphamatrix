import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.security import check_rate_limit
from app.models.fund import FundMaster
from app.schemas.ai_schema import (
    AISemanticQueryRequest, AISemanticQueryResponse, ParsedFilters,
    AIChatRequest, AIChatResponse
)
from app.schemas.fund_schema import FundGridItem
from app.services.ai_agent import parse_semantic_query, run_ai_chat

router = APIRouter()
logger = logging.getLogger("app.api.v1.ai")

@router.post("/semantic-query", dependencies=[Depends(check_rate_limit)])
async def ai_semantic_query(payload: AISemanticQueryRequest, db: AsyncSession = Depends(get_db)):
    """
    Parse a natural language query into database filters,
    execute the query on the FundMaster table, and return results.
    """
    try:
        # 1. Parse using AI Service
        parsed_data = await parse_semantic_query(payload.query)
        
        # 2. Extract filter attributes
        category = parsed_data.get("category")
        min_cagr_1y = parsed_data.get("min_cagr_1y")
        max_cagr_1y = parsed_data.get("max_cagr_1y")
        min_cagr_3y = parsed_data.get("min_cagr_3y")
        max_cagr_3y = parsed_data.get("max_cagr_3y")
        min_cagr_5y = parsed_data.get("min_cagr_5y")
        max_cagr_5y = parsed_data.get("max_cagr_5y")
        min_expense = parsed_data.get("min_expense_ratio")
        max_expense = parsed_data.get("max_expense_ratio")
        min_sharpe = parsed_data.get("min_sharpe_ratio")
        max_sharpe = parsed_data.get("max_sharpe_ratio")
        min_pe = parsed_data.get("min_pe_ratio")
        max_pe = parsed_data.get("max_pe_ratio")
        sort_by = parsed_data.get("sort_by")
        sort_order = parsed_data.get("sort_order", "desc")
        explanation = parsed_data.get("sql_explanation", "")
        
        # 3. Query DB
        query = select(FundMaster)
        if category:
            query = query.where(FundMaster.category == category)
        if min_cagr_1y is not None:
            query = query.where(FundMaster.cagr_1y >= (min_cagr_1y / 100.0))
        if max_cagr_1y is not None:
            query = query.where(FundMaster.cagr_1y <= (max_cagr_1y / 100.0))
        if min_cagr_3y is not None:
            query = query.where(FundMaster.cagr_3y >= (min_cagr_3y / 100.0))
        if max_cagr_3y is not None:
            query = query.where(FundMaster.cagr_3y <= (max_cagr_3y / 100.0))
        if min_cagr_5y is not None:
            query = query.where(FundMaster.cagr_5y >= (min_cagr_5y / 100.0))
        if max_cagr_5y is not None:
            query = query.where(FundMaster.cagr_5y <= (max_cagr_5y / 100.0))
        if min_expense is not None:
            query = query.where(FundMaster.expense_ratio >= min_expense)
        if max_expense is not None:
            query = query.where(FundMaster.expense_ratio <= max_expense)
        if min_sharpe is not None:
            query = query.where(FundMaster.sharpe_ratio >= min_sharpe)
        if max_sharpe is not None:
            query = query.where(FundMaster.sharpe_ratio <= max_sharpe)
        if min_pe is not None:
            query = query.where(FundMaster.pe_ratio >= min_pe)
        if max_pe is not None:
            query = query.where(FundMaster.pe_ratio <= max_pe)
            
        # Apply sorting
        if sort_by and hasattr(FundMaster, sort_by):
            sort_attr = getattr(FundMaster, sort_by)
            if sort_order.lower() == "asc":
                query = query.order_by(sort_attr.asc())
            else:
                query = query.order_by(sort_attr.desc())
        else:
            query = query.order_by(FundMaster.cagr_3y.desc())
            
        # Execute Query
        result = await db.execute(query)
        funds = result.scalars().all()
        
        # Format matched funds
        matched_funds = []
        for f in funds:
            matched_funds.append({
                "scheme_code": f.scheme_code,
                "fund_name": f.fund_name,
                "category": f.category,
                "cagr_1y": f.cagr_1y,
                "cagr_3y": f.cagr_3y,
                "cagr_5y": f.cagr_5y,
                "sharpe_ratio": f.sharpe_ratio,
                "alpha": f.alpha,
                "pe_ratio": f.pe_ratio,
                "expense_ratio": f.expense_ratio
            })
            
        return {
            "query": payload.query,
            "parsed_filters": {
                "category": category,
                "min_cagr_1y": min_cagr_1y,
                "max_cagr_1y": max_cagr_1y,
                "min_cagr_3y": min_cagr_3y,
                "max_cagr_3y": max_cagr_3y,
                "min_cagr_5y": min_cagr_5y,
                "max_cagr_5y": max_cagr_5y,
                "min_expense_ratio": min_expense,
                "max_expense_ratio": max_expense,
                "min_sharpe_ratio": min_sharpe,
                "max_sharpe_ratio": max_sharpe,
                "min_pe_ratio": min_pe,
                "max_pe_ratio": max_pe,
                "sort_by": sort_by,
                "sort_order": sort_order
            },
            "sql_explanation": explanation,
            "matched_funds_count": len(matched_funds),
            "matched_funds": matched_funds
        }
        
    except Exception as e:
        logger.error(f"Semantic query execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse and execute semantic query: {str(e)}"
        )

@router.post("/chat", response_model=AIChatResponse, dependencies=[Depends(check_rate_limit)])
async def ai_chat_analyst(payload: AIChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Chat with the AI analyst, optionally injecting the context of a specific fund.
    """
    fund_dict = None
    sources = []
    
    # 1. Inject context if scheme_code is provided
    if payload.scheme_code:
        fund_check = await db.execute(select(FundMaster).where(FundMaster.scheme_code == payload.scheme_code))
        fund = fund_check.scalar_one_or_none()
        if fund:
            fund_dict = {
                "fund_name": fund.fund_name,
                "category": fund.category,
                "sub_category": fund.sub_category,
                "cagr_1y": round(fund.cagr_1y * 100, 2) if fund.cagr_1y else None,
                "cagr_3y": round(fund.cagr_3y * 100, 2) if fund.cagr_3y else None,
                "cagr_5y": round(fund.cagr_5y * 100, 2) if fund.cagr_5y else None,
                "sharpe_ratio": round(fund.sharpe_ratio, 2) if fund.sharpe_ratio else None,
                "sortino_ratio": round(fund.sortino_ratio, 2) if fund.sortino_ratio else None,
                "alpha": round(fund.alpha * 100, 2) if fund.alpha else None,
                "beta": round(fund.beta, 2) if fund.beta else None,
                "pe_ratio": fund.pe_ratio,
                "expense_ratio": fund.expense_ratio
            }
            sources.append(fund.fund_name)
            
    # 2. Run chat
    try:
        ai_response = await run_ai_chat(payload.message, payload.history, fund_dict)
        return {
            "response": ai_response,
            "scheme_code": payload.scheme_code,
            "sources": sources
        }
    except Exception as e:
        logger.error(f"AI chat execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run chat analyst: {str(e)}"
        )
