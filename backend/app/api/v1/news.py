import logging
import json
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import yfinance as yf

from app.core.security import check_rate_limit
from app.services.ai_agent import groq_client, groq_configured

router = APIRouter()
logger = logging.getLogger("app.api.v1.news")

class NewsArticleRequest(BaseModel):
    title: str
    publisher: str
    link: str

def get_impact_tag(title: str) -> str:
    """
    Classify market impact (HIGH, MEDIUM, LOW) based on keywords in title.
    """
    title_lower = title.lower()
    high_words = [
        "rbi", "fed", "interest rate", "budget", "gdp", "inflation", "slashed", 
        "surged", "plunged", "crash", "rates", "acquisition", "merger", "policy", 
        "sebi", "sec", "tariffs", "trade war", "monetary policy", "regulatory", "hike"
    ]
    med_words = [
        "earnings", "results", "quarterly", "stocks", "shares", "dividend", "deal", 
        "ipo", "revenue", "profit", "launch", "outperforms", "wins", "loses", "revenue cagr",
        "invest", "funding", "shares rise", "shares fall", "acquisitions", "nifty", "sensex"
    ]
    
    for w in high_words:
        if w in title_lower:
            return "HIGH"
    for w in med_words:
        if w in title_lower:
            return "MEDIUM"
    return "LOW"

def get_mock_analysis(title: str, publisher: str, link: str) -> dict:
    """
    Generates a realistic, context-aware analysis fallback when Groq is not configured.
    """
    title_lower = title.lower()
    
    # Default fallback contents
    summary = f"This report evaluates the market response to '{title}' as reported by {publisher}. Analysts are analyzing the headline to evaluate underlying earnings and systemic risk changes."
    direction = "Neutral"
    affected_sectors = [{"sector": "General Markets", "impact": "Neutral", "reason": "General macro adjustment."}]
    key_companies = []
    
    if "rbi" in title_lower or "interest rate" in title_lower or "fed" in title_lower or "inflation" in title_lower or "rate" in title_lower:
        summary = f"Monetary policy signals reported by {publisher} trigger adjustments in sovereign bond yields. Commercial banks and leveraged sectors are actively adjusting credit spreads to maintain margin profiles."
        direction = "Bullish" if ("cut" in title_lower or "pause" in title_lower or "slashed" in title_lower) else "Bearish"
        affected_sectors = [
            {"sector": "Banking & Financial Services", "impact": "Positive" if direction == "Bullish" else "Negative", "reason": "Sovereign bond portfolio yields and cost of funds re-pricing."},
            {"sector": "Real Estate & Infrastructure", "impact": "Positive" if direction == "Bullish" else "Negative", "reason": "Cost of debt direct impact on project IRR and buyer affordability."}
        ]
        key_companies = [
            {"company": "HDFC Bank", "ticker": "HDFCBANK.NS", "sentiment": "Bullish" if direction == "Bullish" else "Neutral", "reason": "Poised to optimize NIM spreads based on credit cycle updates."},
            {"company": "State Bank of India", "ticker": "SBIN.NS", "sentiment": "Neutral", "reason": "Substantial treasury book value exposed to systemic interest rate changes."}
        ]
    elif "tcs" in title_lower or "infy" in title_lower or "wipro" in title_lower or "tata consultancy" in title_lower or "tech" in title_lower or "infosys" in title_lower:
        summary = f"Enterprise demand cycles and deal contract updates reported by {publisher} influence digital services valuations. Shift towards hybrid cloud and generative AI pipelines continues to define long-term contract values."
        direction = "Bullish"
        affected_sectors = [
            {"sector": "Information Technology", "impact": "Positive", "reason": "Resilient enterprise technology spend and cloud transformation projects."}
        ]
        key_companies = [
            {"company": "TCS", "ticker": "TCS.NS", "sentiment": "Bullish", "reason": "Industry leader with strong cost control and robust pipeline of order execution."},
            {"company": "Infosys", "ticker": "INFY.NS", "sentiment": "Bullish", "reason": "Growth momentum supported by digital cloud deal wins."}
        ]
    elif "reliance" in title_lower or "jio" in title_lower or "oil" in title_lower or "refinery" in title_lower or "reliance industries" in title_lower:
        summary = f"Operations updates for Reliance Industries indicate stability across energy refining and retail networks. Ongoing capital expenditure on renewable solar energy and 5G services remain principal valuation catalysts."
        direction = "Bullish"
        affected_sectors = [
            {"sector": "Energy & Oil & Gas", "impact": "Positive", "reason": "Sustained gross refining margins and global export volumes."},
            {"sector": "Telecommunications", "impact": "Positive", "reason": "Jio subscriber additions and stable average revenue per user (ARPU)."}
        ]
        key_companies = [
            {"company": "Reliance Industries", "ticker": "RELIANCE.NS", "sentiment": "Bullish", "reason": "Multi-sector balance provides defense against commodity price swings."}
        ]
    elif "budget" in title_lower or "policy" in title_lower or "government" in title_lower or "sebi" in title_lower or "gst" in title_lower:
        summary = f"Fiscal budget measures or capital market guidelines reported by {publisher} introduce structural updates. Standardizing compliance protocols is viewed favorably by institutional investors."
        direction = "Neutral"
        affected_sectors = [
            {"sector": "Capital Markets", "impact": "Neutral", "reason": "Slightly higher cost of compliance offset by improved systemic market stability."}
        ]
        key_companies = [
            {"company": "BSE Limited", "ticker": "BSE.NS", "sentiment": "Bullish", "reason": "resilient transaction volumes driven by derivatives volume growth."}
        ]
    elif "earnings" in title_lower or "profit" in title_lower or "q1" in title_lower or "q2" in title_lower or "q3" in title_lower or "q4" in title_lower or "result" in title_lower:
        summary = f"Corporate quarterly disclosures reported by {publisher} signal operational trends. High earnings performance validates premium multiples, while margin compression remains a headwind."
        direction = "Bullish" if ("jump" in title_lower or "surge" in title_lower or "rise" in title_lower or "outperform" in title_lower) else "Bearish"
        affected_sectors = [
            {"sector": "General Equities", "impact": "Positive" if direction == "Bullish" else "Negative", "reason": "Corporate earnings trajectories anchoring forward PE benchmarks."}
        ]
        key_companies = [
            {"company": "TCS", "ticker": "TCS.NS", "sentiment": "Bullish" if direction == "Bullish" else "Neutral", "reason": "Earnings delivery aligning with margin guidelines."}
        ]
        
    return {
        "summary": summary,
        "affected_sectors": affected_sectors,
        "key_companies": key_companies,
        "direction": direction
    }

@router.get("/list", dependencies=[Depends(check_rate_limit)])
async def list_news(stream: str = "india", category: str = "all"):
    """
    Retrieve live financial news headlines from Yahoo Finance based on stream and category filters.
    """
    # 1. Map stream and category to Yahoo Finance Search query strings
    queries_map = {
        "india": {
            "all": "Nifty",
            "stocks": "Indian Stocks",
            "mutual_funds": "SEBI",
            "economy": "India Economy",
            "policy": "RBI",
            "earnings": "Sensex"
        },
        "global": {
            "all": "Nasdaq",
            "stocks": "S&P 500",
            "mutual_funds": "ETFs",
            "economy": "Inflation",
            "policy": "Federal Reserve",
            "earnings": "Mutual Funds"
        }
    }
    
    stream_val = stream.lower() if stream.lower() in ["india", "global"] else "india"
    category_val = category.lower() if category.lower() in queries_map[stream_val] else "all"
    
    query = queries_map[stream_val][category_val]
    logger.info(f"Fetching news for query: {query}")
    
    try:
        # Fetch news in a non-blocking threadpool
        search = await asyncio.to_thread(yf.Search, query)
        raw_news = search.news
        
        formatted_news = []
        if raw_news:
            for item in raw_news:
                title = item.get("title", "")
                if not title:
                    continue
                
                formatted_news.append({
                    "uuid": item.get("uuid", ""),
                    "title": title,
                    "publisher": item.get("publisher", "Yahoo Finance"),
                    "link": item.get("link", ""),
                    "timestamp": item.get("providerPublishTime", 0),
                    "type": item.get("type", "STORY"),
                    "category": category_val,
                    "stream": stream_val,
                    "impact": get_impact_tag(title)
                })
        
        # Sort news by newest timestamp first
        formatted_news.sort(key=lambda x: x["timestamp"], reverse=True)
        return formatted_news
        
    except Exception as e:
        logger.error(f"Error fetching news from yfinance: {e}")
        # Return fallback mock list if yfinance fails
        return []

@router.post("/analyze", dependencies=[Depends(check_rate_limit)])
async def analyze_news_article(payload: NewsArticleRequest):
    """
    Generate professional, structured market impact analysis using Groq Llama 3.3.
    Falls back to intelligent local keyword mapping if Groq is not configured or fails.
    """
    if not groq_configured:
        logger.info("Groq is not configured. Returning rich mock news intelligence analysis.")
        return get_mock_analysis(payload.title, payload.publisher, payload.link)
        
    prompt = f"""
    You are an elite institutional financial research analyst at AlphaMatrix.
    Analyze this recent financial news story headline:
    Headline: "{payload.title}"
    Publisher: "{payload.publisher}"
    URL: "{payload.link}"
    
    Provide a professional investment impact analysis structured exactly as a JSON object with these keys:
    - "summary": A concise 2-3 sentence explanation of the news and its immediate market relevance.
    - "affected_sectors": A list of dicts with keys "sector", "impact" ("Positive", "Negative", or "Neutral"), and "reason" (short explanation). Limit to 2 sectors maximum.
    - "key_companies": A list of dicts with keys "company", "ticker" (valid exchange ticker, e.g. TCS.NS, RELIANCE.NS, TSLA, AAPL), "sentiment" ("Bullish", "Bearish", or "Neutral"), and "reason". Limit to 2 companies maximum.
    - "direction": "Bullish" | "Bearish" | "Neutral"
    
    Return ONLY the raw JSON object. Do not include any markdown fences or other texts.
    """
    
    try:
        response = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        res_text = response.choices[0].message.content
        analysis = json.loads(res_text.strip())
        return analysis
        
    except Exception as e:
        logger.error(f"Groq news analysis failed: {e}. Falling back to mock generator.")
        return get_mock_analysis(payload.title, payload.publisher, payload.link)
