import json
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from app.core.config import settings
from app.schemas.ai_schema import ParsedFilters, ChatMessage

logger = logging.getLogger("app.services.ai_agent")

# Configure Gemini if API Key is available
gemini_configured = False
if settings.GEMINI_API_KEY:
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        gemini_configured = True
        logger.info("Gemini API configured successfully.")
    except Exception as e:
        logger.error(f"Error configuring Gemini API: {e}")

async def parse_semantic_query(query: str) -> Dict[str, Any]:
    """
    Parses a natural language query like:
    "Show me high-yield mid-caps with low risk"
    and maps it to structured database filters.
    """
    if not gemini_configured:
        return _mock_parse_semantic_query(query)
        
    prompt = f"""
You are a Fintech AI database search assistant. Your job is to translate a user's natural language request for mutual funds into structured JSON search filters.

User Query: "{query}"

Translate this query into a JSON object matching this schema:
{{
  "category": "Large Cap" | "Mid Cap" | "Small Cap" | "Sectoral" | "Index" | null,
  "min_cagr_3y": float | null,
  "max_expense_ratio": float | null,
  "min_sharpe_ratio": float | null,
  "max_pe_ratio": float | null,
  "sort_by": "cagr_3y" | "cagr_5y" | "sharpe_ratio" | "sortino_ratio" | "alpha" | "beta" | "expense_ratio" | null,
  "sort_order": "asc" | "desc",
  "sql_explanation": "A short natural language explanation of how you mapped the user's terms (e.g. mapping 'high yield' to min_cagr_3y=18.0 and sorting by cagr_3y desc)"
}}

Rules:
1. Return ONLY the JSON object. Do not include any markdown backticks or extra text outside the JSON.
2. If "high yield" or "high return" is mentioned, set min_cagr_3y to 15.0 or 18.0, and set sort_by to "cagr_3y".
3. If "low risk" is mentioned, set min_sharpe_ratio to 1.2 or set sort_by to "sharpe_ratio".
4. If a specific category like "mid cap", "large cap", "small cap", "index", or "sectoral" is mentioned, map it exactly to category field.
5. If no sort order is implied, default to "desc" for performance metrics and "asc" for risk or expense ratio.
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        parsed_json = json.loads(response.text.strip())
        # Ensure default fields are present
        if "sort_order" not in parsed_json:
            parsed_json["sort_order"] = "desc"
        return parsed_json
    except Exception as e:
        logger.error(f"Gemini semantic parsing failed: {e}. Falling back to rule-based mock parser.")
        return _mock_parse_semantic_query(query)

async def generate_fund_summary(fund_data: Dict[str, Any]) -> str:
    """
    Generates a professional 3-bullet point investment analysis of a mutual fund
    based on its calculated database metrics, 1-year trend, and geopolitical overlay.
    """
    if not gemini_configured:
        return _generate_mock_fund_summary(fund_data)
        
    prompt = f"""
You are a Lead Portfolio Strategist and Chartered Financial Analyst (CFA) specializing in Indian Mutual Funds.
Analyze the following fund metrics and write a highly professional, 3-bullet-point synthesis of its risk-return profile.

Fund Details:
- Name: {fund_data.get('fund_name')}
- Category: {fund_data.get('category')}
- Sub-category: {fund_data.get('sub_category')}
- 1-Year Performance Trend: {fund_data.get('cagr_1y')}%
- 3-Year CAGR: {fund_data.get('cagr_3y')}%
- 5-Year CAGR: {fund_data.get('cagr_5y')}%
- Sharpe Ratio: {fund_data.get('sharpe_ratio')}
- Sortino Ratio: {fund_data.get('sortino_ratio')}
- Alpha (vs Nifty 50): {fund_data.get('alpha')}%
- Beta (vs Nifty 50): {fund_data.get('beta')}
- PE Ratio: {fund_data.get('pe_ratio')}
- Expense Ratio: {fund_data.get('expense_ratio')}%

Instruction:
Generate EXACTLY 3 bullet points starting with a hyphen (-). No introductory text, no conclusion.
You MUST write about these specific domains:
1. **1-Year Trend & Trajectory**: Detail how the 1-Year performance ({fund_data.get('cagr_1y')}%) relates to the 3Y and 5Y CAGR, explaining the growth path.
2. **Geopolitical & Macro Overlay**: Evaluate how current geopolitical situations (e.g. global trade friction, interest rate cycles, inflation, supply chains) affect the specific holdings of this category ({fund_data.get('category')} / {fund_data.get('sub_category')}).
3. **Investment Stance & Future Forecast**: Give a clear, definitive recommendation (either **BUY**, **HOLD**, or **AVOID**) with a forecast of its future trend and a risk-adjusted justification.

Return ONLY the 3 bullet points starting with a hyphen (-). Mention the numerical metrics in your points.
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        summary = response.text.strip()
        if not summary:
            return _generate_mock_fund_summary(fund_data)
        return summary
    except Exception as e:
        logger.error(f"Gemini summary generation failed: {e}. Falling back to mock generator.")
        return _generate_mock_fund_summary(fund_data)

async def run_ai_chat(message: str, history: List[ChatMessage], fund_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Conversational chatbot for mutual funds with optional context injection.
    """
    if not gemini_configured:
        return _mock_chat_response(message, fund_data)
        
    system_instruction = (
        "You are AlphaMatrix AI Analyst. You help users analyze mutual funds, explain risk ratios, and compare portfolios. "
        "When the user asks about investing in a company or mutual fund, you MUST check the fund's full past 1-year performance trend, "
        "consider the geopolitical and macroeconomic situations (global trade friction, interest rate cycles, inflation, supply chains) "
        "affecting its category, predict future trends, and give a clear recommendation of whether the user should invest (BUY, HOLD, or AVOID) in bold."
    )
    
    context = ""
    if fund_data:
        context = f"""
Currently the user is viewing details for the fund: {fund_data.get('fund_name')}.
Metrics:
- CAGR 1Y: {fund_data.get('cagr_1y')}%
- CAGR 3Y: {fund_data.get('cagr_3y')}%
- CAGR 5Y: {fund_data.get('cagr_5y')}%
- Sharpe Ratio: {fund_data.get('sharpe_ratio')}
- Sortino Ratio: {fund_data.get('sortino_ratio')}
- Alpha: {fund_data.get('alpha')}
- Beta: {fund_data.get('beta')}
- PE: {fund_data.get('pe_ratio')}
- Expense Ratio: {fund_data.get('expense_ratio')}%
Use these details to answer user queries about this fund.
"""
    
    # Format chat history
    contents = []
    for msg in history:
        contents.append({"role": "user" if msg.role == "user" else "model", "parts": [msg.content]})
        
    # Append latest message with context
    latest_parts = [f"{context}\nUser Question: {message}"]
    contents.append({"role": "user", "parts": latest_parts})
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
        response = model.generate_content(contents)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini chat failed: {e}")
        return f"I apologize, I encountered an issue interacting with the AI endpoint. Here is a baseline response based on fund context:\n{_mock_chat_response(message, fund_data)}"

# --- MOCK FALLBACKS ---

def _mock_parse_semantic_query(query: str) -> Dict[str, Any]:
    q = query.lower()
    filters = {
        "category": None,
        "min_cagr_1y": None,
        "min_cagr_3y": None,
        "max_expense_ratio": None,
        "min_sharpe_ratio": None,
        "max_pe_ratio": None,
        "sort_by": "cagr_3y",
        "sort_order": "desc",
        "sql_explanation": "Parsed query locally using keyword filters: "
    }
    
    # Category matches
    if "large cap" in q or "bluechip" in q:
        filters["category"] = "Large Cap"
        filters["sql_explanation"] += "category = 'Large Cap'; "
    elif "mid cap" in q:
        filters["category"] = "Mid Cap"
        filters["sql_explanation"] += "category = 'Mid Cap'; "
    elif "small cap" in q:
        filters["category"] = "Small Cap"
        filters["sql_explanation"] += "category = 'Small Cap'; "
    elif "sector" in q or "it" in q or "pharma" in q or "banking" in q:
        filters["category"] = "Sectoral"
        filters["sql_explanation"] += "category = 'Sectoral'; "
    elif "index" in q or "nifty" in q:
        filters["category"] = "Index"
        filters["sql_explanation"] += "category = 'Index'; "
        
    # Parameter matches
    if "high yield" in q or "high cagr" in q or "high return" in q:
        filters["min_cagr_3y"] = 18.0
        filters["sort_by"] = "cagr_3y"
        filters["sql_explanation"] += "min_cagr_3y >= 18.0, sorting by CAGR 3Y desc; "
    elif "low risk" in q or "stable" in q:
        filters["min_sharpe_ratio"] = 1.1
        filters["sort_by"] = "sharpe_ratio"
        filters["sql_explanation"] += "min_sharpe_ratio >= 1.1, sorting by Sharpe desc; "
    elif "cheap" in q or "low pe" in q:
        filters["max_pe_ratio"] = 25.0
        filters["sort_by"] = "pe_ratio"
        filters["sort_order"] = "asc"
        filters["sql_explanation"] += "max_pe_ratio <= 25.0, sorting by PE ratio asc; "
    elif "low cost" in q or "low expense" in q:
        filters["max_expense_ratio"] = 1.0
        filters["sort_by"] = "expense_ratio"
        filters["sort_order"] = "asc"
        filters["sql_explanation"] += "max_expense_ratio <= 1.0, sorting by Expense Ratio asc; "
        
    if filters["sql_explanation"] == "Parsed query locally using keyword filters: ":
        filters["sql_explanation"] += "No filters matched, returning defaults sorted by CAGR 3Y."
        
    return filters

def _generate_mock_fund_summary(fund_data: Dict[str, Any]) -> str:
    name = fund_data.get('fund_name', 'This Fund')
    cagr_1y = fund_data.get('cagr_1y') or "N/A"
    cagr_3y = fund_data.get('cagr_3y') or "N/A"
    cagr_5y = fund_data.get('cagr_5y') or "N/A"
    sharpe = fund_data.get('sharpe_ratio') or "N/A"
    alpha = fund_data.get('alpha') or "N/A"
    beta = fund_data.get('beta') or "N/A"
    pe = fund_data.get('pe_ratio') or "N/A"
    cat = fund_data.get('category') or "Large Cap"
    sub_cat = fund_data.get('sub_category') or "Equity - Growth"
    
    # Stance logic based on Sharpe Ratio
    rec = "HOLD"
    reason = "moderate risk-adjusted performance with stable cash flows."
    try:
        if sharpe != "N/A" and float(sharpe) >= 1.2:
            rec = "BUY"
            reason = "superior risk-adjusted performance and positive alpha creation."
        elif sharpe != "N/A" and float(sharpe) < 0.6:
            rec = "AVOID"
            reason = "underperforming benchmark returns on a risk-adjusted basis."
    except ValueError:
        pass
        
    return f"""- **1-Year Trend & Trajectory**: {name} shows a 1-Year performance of {cagr_1y}%, comparing to its 3-Year CAGR of {cagr_3y}% and 5-Year CAGR of {cagr_5y}%. This outlines a compounding trajectory with stable momentum in recent quarters.
- **Geopolitical & Macro Overlay**: For the {cat} ({sub_cat}) category, holdings are sensitive to global macroeconomic variables. Ongoing global trade frictions, interest rate cycle shifts, and supply chain updates present moderate volatility, but active sector rotations are cushioning systemic exposure.
- **Investment Stance & Future Forecast**: We assign a definitive **{rec}** recommendation. The future trend is projected to remain stable, with a Sharpe ratio of {sharpe} and a Beta of {beta} justifying this stance based on {reason}"""

def _mock_chat_response(message: str, fund_data: Optional[Dict[str, Any]] = None) -> str:
    q = message.lower()
    if fund_data:
        name = fund_data.get('fund_name')
        cagr_1y = fund_data.get('cagr_1y', 'N/A')
        cagr_3y = fund_data.get('cagr_3y', 'N/A')
        cagr_5y = fund_data.get('cagr_5y', 'N/A')
        sharpe = fund_data.get('sharpe_ratio', 'N/A')
        sortino = fund_data.get('sortino_ratio', 'N/A')
        alpha = fund_data.get('alpha', 'N/A')
        beta = fund_data.get('beta', 'N/A')
        pe = fund_data.get('pe_ratio', 'N/A')
        expense = fund_data.get('expense_ratio', 'N/A')
        cat = fund_data.get('category', 'Large Cap')
        
        rec = "HOLD"
        try:
            if sharpe != "N/A" and float(sharpe) >= 1.2:
                rec = "BUY"
            elif sharpe != "N/A" and float(sharpe) < 0.6:
                rec = "AVOID"
        except ValueError:
            pass
            
        if any(term in q for term in ["invest", "recommend", "buy", "should i", "avoid", "hold"]):
            return (
                f"Regarding your query about investing in {name}, here is my analysis:\n\n"
                f"1. **1-Year Trend**: The fund's 1-year performance is {cagr_1y}%, demonstrating a solid growth trajectory compared to its 3-year CAGR of {cagr_3y}%.\n"
                f"2. **Geopolitical & Macro Overlay**: The {cat} space is currently adapting to global interest rate cycles and supply chain friction. Larger capitalized holdings remain relatively insulated from global trade frictions.\n"
                f"3. **Investment Recommendation**: We recommend a **{rec}** stance. The future trend is forecasted to remain stable based on a Sharpe ratio of {sharpe} and a Beta of {beta}."
            )
            
        if any(term in q for term in ["cagr", "return", "performance", "trend", "growth", "1 year", "past year", "1-year"]):
            return f"The performance trajectory of {name} is as follows:\n- 1-Year CAGR/Trend: {cagr_1y}%\n- 3-Year CAGR: {cagr_3y}%\n- 5-Year CAGR: {cagr_5y}%."
            
        if any(term in q for term in ["sharpe", "sortino", "risk-adjusted"]):
            return f"For {name}, the risk-adjusted efficiency metrics are:\n- Sharpe Ratio: {sharpe}\n- Sortino Ratio: {sortino}\nThese metrics evaluate the excess return generated per unit of risk/downside risk."
            
        if any(term in q for term in ["beta", "volatility", "volatile"]):
            return f"The volatility profile of {name} is defined by a Beta of {beta} (relative to the Nifty 50 benchmark). A Beta of {beta} indicates that the fund is {'more' if (beta != 'N/A' and float(beta) > 1.0) else 'less'} volatile than the broader market."
            
        if "alpha" in q:
            return f"The fund {name} has generated an Alpha of {alpha}% relative to the Nifty 50 benchmark, representing the active excess return generated by the fund manager."
            
        if any(term in q for term in ["pe", "valuation", "ratio"]):
            return f"The portfolio valuation of {name} exhibits a P/E Ratio of {pe}. This represents the weighted average price-to-earnings multiple of its underlying stock holdings."
            
        if any(term in q for term in ["expense", "cost", "fee", "charge"]):
            return f"The Expense Ratio of {name} is {expense}%. This annual operating fee covers the fund's management fees and administrative costs."
            
        return f"Regarding {name}, it is a {cat} fund with a P/E of {pe} and expense ratio of {expense}%. How can I help you analyze its risk metrics further?"
        
    if "sharpe" in q:
        return "The Sharpe ratio measures the performance of an investment compared to a risk-free asset, after adjusting for its risk. It is defined as the difference between the returns of the investment and the risk-free rate, divided by the standard deviation of investment returns. Higher is better."
    if "sortino" in q:
        return "The Sortino ratio is a variation of the Sharpe ratio that only differentiates downside volatility from total volatility. It divides the excess return by the downside standard deviation, penalizing only negative returns."
    if "alpha" in q:
        return "Alpha measures the active return on an investment compared to a benchmark index. An alpha of 1.0 means the fund outperformed its benchmark index by 1%."
    
    return "Hello! I am your AlphaMatrix AI Analyst. You can ask me to explain risk ratios like Sharpe or Sortino, query specific funds, or ask for comparisons."

