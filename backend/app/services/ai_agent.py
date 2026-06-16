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
  "min_cagr_1y": float | null,
  "max_cagr_1y": float | null,
  "min_cagr_3y": float | null,
  "max_cagr_3y": float | null,
  "min_cagr_5y": float | null,
  "max_cagr_5y": float | null,
  "min_expense_ratio": float | null,
  "max_expense_ratio": float | null,
  "min_sharpe_ratio": float | null,
  "max_sharpe_ratio": float | null,
  "min_pe_ratio": float | null,
  "max_pe_ratio": float | null,
  "sort_by": "cagr_1y" | "cagr_3y" | "cagr_5y" | "sharpe_ratio" | "sortino_ratio" | "alpha" | "beta" | "expense_ratio" | "pe_ratio" | null,
  "sort_order": "asc" | "desc",
  "sql_explanation": "A short natural language explanation of how you mapped the user's terms"
}}

Rules:
1. Return ONLY the JSON object. Do not include any markdown backticks or extra text outside the JSON.
2. If "lost money", "negative return" or "negative performance" over the last year is mentioned, set max_cagr_1y to 0.0.
3. If "high yield" or "high return" is mentioned, set min_cagr_3y to 15.0 or 18.0, and set sort_by to "cagr_3y".
4. If "low risk" is mentioned, set min_sharpe_ratio to 1.2 or set sort_by to "sharpe_ratio".
5. If a specific category like "mid cap", "large cap", "small cap", "index", or "sectoral" is mentioned, map it exactly to category field.
6. If no sort order is implied, default to "desc" for performance metrics and "asc" for risk or expense ratio.
"""
    try:
        model = genai.GenerativeModel("gemini-3.1-flash-lite")
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
        model = genai.GenerativeModel("gemini-3.1-flash-lite")
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
        model = genai.GenerativeModel("gemini-3.1-flash-lite", system_instruction=system_instruction)
        response = model.generate_content(contents)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini chat failed: {e}")
        return f"I apologize, I encountered an issue interacting with the AI endpoint. Here is a baseline response based on fund context:\n{_mock_chat_response(message, fund_data)}"

# --- MOCK FALLBACKS ---

def _mock_parse_semantic_query(query: str) -> Dict[str, Any]:
    import re
    q = query.lower()
    
    # Initialize completely fresh and blank on every single function call
    filters = {
        "category": None,
        "min_cagr_1y": None,
        "max_cagr_1y": None,
        "min_cagr_3y": None,
        "max_cagr_3y": None,
        "min_cagr_5y": None,
        "max_cagr_5y": None,
        "min_expense_ratio": None,
        "max_expense_ratio": None,
        "min_sharpe_ratio": None,
        "max_sharpe_ratio": None,
        "min_pe_ratio": None,
        "max_pe_ratio": None,
        "sort_by": None,
        "sort_order": "desc",
        "sql_explanation": "Parsed query locally using keyword & regex filters: "
    }
    
    # 1. Global context extraction (e.g. category and duration detection from entire query)
    global_category = None
    if re.search(r'\b(?:large\s*cap|bluechip)\b', q):
        global_category = "LARGE_CAP"
    elif re.search(r'\b(?:mid\s*cap)\b', q):
        global_category = "MID_CAP"
    elif re.search(r'\b(?:small\s*cap)\b', q):
        global_category = "SMALL_CAP"
    elif re.search(r'\b(?:index|nifty)\b', q):
        global_category = "INDEX"
    elif re.search(r'\b(?:sectoral|sector|it|pharma|banking)\b', q):
        global_category = "SECTORAL"

    global_duration = None
    if any(x in q for x in ["1 year", "1y", "1-year", "last year", "one year", "past year"]):
        global_duration = 1
    elif any(x in q for x in ["3 year", "3y", "3-year", "three year"]):
        global_duration = 3
    elif any(x in q for x in ["5 year", "5y", "5-year", "five year"]):
        global_duration = 5

    filters["category"] = global_category

    # 2. Split query by conjunctions chunk-by-chunk to avoid dropping constraints
    chunks = re.split(r'\b(?:and|but|with|still|yet|for|so|although|though|whereas|while|which|that|who|whose)\b|,', q)
    
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
            
        # Detect local duration if any, fallback to global
        chunk_duration = global_duration
        if any(x in chunk for x in ["1 year", "1y", "1-year", "last year", "one year", "past year"]):
            chunk_duration = 1
        elif any(x in chunk for x in ["3 year", "3y", "3-year", "three year"]):
            chunk_duration = 3
        elif any(x in chunk for x in ["5 year", "5y", "5-year", "five year"]):
            chunk_duration = 5
            
        # Match positive / gains / made money
        if any(x in chunk for x in ["positive", "gains", "made money", "gain"]):
            dur = chunk_duration if chunk_duration is not None else 3
            if dur == 1:
                filters["min_cagr_1y"] = 0.0
            elif dur == 3:
                filters["min_cagr_3y"] = 0.0
            elif dur == 5:
                filters["min_cagr_5y"] = 0.0

        # Match lost money / negative / in the red
        if any(x in chunk for x in ["lost money", "negative", "in the red", "lose money", "lost value"]):
            dur = chunk_duration if chunk_duration is not None else 1
            if dur == 1:
                filters["max_cagr_1y"] = 0.0
            elif dur == 3:
                filters["max_cagr_3y"] = 0.0
            elif dur == 5:
                filters["max_cagr_5y"] = 0.0

        # Match numeric inequalities
        # --- Sharpe ratio ---
        sharpe_above = re.search(r'\b(?:sharpe|sharpe\s*ratio)\b\s*(?:above|greater than|more than|over|>|>=|of at least|at least)\s*([0-9]+(?:\.[0-9]+)?)', chunk)
        if sharpe_above:
            filters["min_sharpe_ratio"] = float(sharpe_above.group(1))
            
        sharpe_below = re.search(r'\b(?:sharpe|sharpe\s*ratio)\b\s*(?:below|less than|under|<|<=|of at most|at most)\s*([0-9]+(?:\.[0-9]+)?)', chunk)
        if sharpe_below:
            filters["max_sharpe_ratio"] = float(sharpe_below.group(1))

        if "high sharpe" in chunk or "good sharpe" in chunk:
            if filters["min_sharpe_ratio"] is None:
                filters["min_sharpe_ratio"] = 1.2
                filters["sort_by"] = "sharpe_ratio"
        elif "low sharpe" in chunk:
            if filters["max_sharpe_ratio"] is None:
                filters["max_sharpe_ratio"] = 0.8
                filters["sort_by"] = "sharpe_ratio"
                filters["sort_order"] = "asc"

        # --- PE Ratio (Strict word boundary prevents leakage matching "sharpe ratio") ---
        pe_above = re.search(r'\b(?:pe|pe\s*ratio|p/e|p/e\s*ratio|valuation)\b\s*(?:above|greater than|more than|over|>|>=|of at least|at least)\s*([0-9]+(?:\.[0-9]+)?)', chunk)
        if pe_above:
            filters["min_pe_ratio"] = float(pe_above.group(1))
            
        pe_below = re.search(r'\b(?:pe|pe\s*ratio|p/e|p/e\s*ratio|valuation)\b\s*(?:below|less than|under|<|<=|of at most|at most)\s*([0-9]+(?:\.[0-9]+)?)', chunk)
        if pe_below:
            filters["max_pe_ratio"] = float(pe_below.group(1))

        if "cheap" in chunk or "low pe" in chunk or "undervalued" in chunk:
            if filters["max_pe_ratio"] is None:
                filters["max_pe_ratio"] = 22.0
                filters["sort_by"] = "pe_ratio"
                filters["sort_order"] = "asc"
        elif "expensive" in chunk or "high pe" in chunk or "overvalued" in chunk:
            if filters["min_pe_ratio"] is None:
                filters["min_pe_ratio"] = 35.0
                filters["sort_by"] = "pe_ratio"
                filters["sort_order"] = "desc"

        # --- Expense Ratio ---
        expense_above = re.search(r'\b(?:expense|expense\s*ratio|cost|fee)\b\s*(?:above|greater than|more than|over|>|>=|of at least|at least)\s*([0-9]+(?:\.[0-9]+)?)', chunk)
        if expense_above:
            filters["min_expense_ratio"] = float(expense_above.group(1))
            
        expense_below = re.search(r'\b(?:expense|expense\s*ratio|cost|fee)\b\s*(?:below|less than|under|<|<=|of at most|at most)\s*([0-9]+(?:\.[0-9]+)?)', chunk)
        if expense_below:
            filters["max_expense_ratio"] = float(expense_below.group(1))

        if "low cost" in chunk or "low expense" in chunk or "cheap expense" in chunk:
            if filters["max_expense_ratio"] is None:
                filters["max_expense_ratio"] = 1.0
                filters["sort_by"] = "expense_ratio"
                filters["sort_order"] = "asc"
        elif "high cost" in chunk or "high expense" in chunk:
            if filters["min_expense_ratio"] is None:
                filters["min_expense_ratio"] = 1.5
                filters["sort_by"] = "expense_ratio"
                filters["sort_order"] = "desc"

        # --- CAGR / Returns ---
        cagr_above = re.search(r'\b(?:cagr|return|returns|yield|performance)\b\s*(?:above|greater than|more than|over|>|>=|of at least|at least)\s*([0-9]+(?:\.[0-9]+)?)\s*%?', chunk)
        cagr_below = re.search(r'\b(?:cagr|return|returns|yield|performance)\b\s*(?:below|less than|under|<|<=|of at most|at most)\s*([0-9]+(?:\.[0-9]+)?)\s*%?', chunk)
        
        cagr_1y_above = re.search(r'\b(?:1\s*y(?:ear)?|last\s*year)\b\s*(?:cagr|return|returns|yield|performance)?\s*(?:above|greater than|more than|over|>|>=|of at least|at least)\s*([0-9]+(?:\.[0-9]+)?)\s*%?', chunk)
        cagr_3y_above = re.search(r'\b(?:3\s*y(?:ear)?)\b\s*(?:cagr|return|returns|yield|performance)?\s*(?:above|greater than|more than|over|>|>=|of at least|at least)\s*([0-9]+(?:\.[0-9]+)?)\s*%?', chunk)
        cagr_5y_above = re.search(r'\b(?:5\s*y(?:ear)?)\b\s*(?:cagr|return|returns|yield|performance)?\s*(?:above|greater than|more than|over|>|>=|of at least|at least)\s*([0-9]+(?:\.[0-9]+)?)\s*%?', chunk)

        cagr_1y_below = re.search(r'\b(?:1\s*y(?:ear)?|last\s*year)\b\s*(?:cagr|return|returns|yield|performance)?\s*(?:below|less than|under|<|<=|of at most|at most)\s*([0-9]+(?:\.[0-9]+)?)\s*%?', chunk)
        cagr_3y_below = re.search(r'\b(?:3\s*y(?:ear)?)\b\s*(?:cagr|return|returns|yield|performance)?\s*(?:below|less than|under|<|<=|of at most|at most)\s*([0-9]+(?:\.[0-9]+)?)\s*%?', chunk)
        cagr_5y_below = re.search(r'\b(?:5\s*y(?:ear)?)\b\s*(?:cagr|return|returns|yield|performance)?\s*(?:below|less than|under|<|<=|of at most|at most)\s*([0-9]+(?:\.[0-9]+)?)\s*%?', chunk)

        if cagr_1y_above:
            filters["min_cagr_1y"] = float(cagr_1y_above.group(1))
        elif cagr_1y_below:
            filters["max_cagr_1y"] = float(cagr_1y_below.group(1))
            
        if cagr_3y_above:
            filters["min_cagr_3y"] = float(cagr_3y_above.group(1))
        elif cagr_3y_below:
            filters["max_cagr_3y"] = float(cagr_3y_below.group(1))

        if cagr_5y_above:
            filters["min_cagr_5y"] = float(cagr_5y_above.group(1))
        elif cagr_5y_below:
            filters["max_cagr_5y"] = float(cagr_5y_below.group(1))

        if cagr_above and not (cagr_1y_above or cagr_3y_above or cagr_5y_above):
            val = float(cagr_above.group(1))
            dur = chunk_duration if chunk_duration is not None else 3
            if dur == 1:
                filters["min_cagr_1y"] = val
            elif dur == 5:
                filters["min_cagr_5y"] = val
            else:
                filters["min_cagr_3y"] = val

        if cagr_below and not (cagr_1y_below or cagr_3y_below or cagr_5y_below):
            val = float(cagr_below.group(1))
            dur = chunk_duration if chunk_duration is not None else 3
            if dur == 1:
                filters["max_cagr_1y"] = val
            elif dur == 5:
                filters["max_cagr_5y"] = val
            else:
                filters["max_cagr_3y"] = val

        if "high yield" in chunk or "high cagr" in chunk or "high return" in chunk:
            dur = chunk_duration if chunk_duration is not None else 3
            if dur == 1 and filters["min_cagr_1y"] is None:
                filters["min_cagr_1y"] = 15.0
                filters["sort_by"] = "cagr_1y"
            elif dur == 5 and filters["min_cagr_5y"] is None:
                filters["min_cagr_5y"] = 15.0
                filters["sort_by"] = "cagr_5y"
            elif dur == 3 and filters["min_cagr_3y"] is None:
                filters["min_cagr_3y"] = 18.0
                filters["sort_by"] = "cagr_3y"

    # 3. Sorting overrides parsed globally
    sort_match = re.search(r'\b(?:sort|sorted|order|ordered)\b\s*by\s*([a-z0-9\s\-]+)', q)
    if sort_match:
        sort_field_text = sort_match.group(1).strip()
        sort_mapping = {
            "cagr 1y": "cagr_1y", "cagr 1 year": "cagr_1y", "1y cagr": "cagr_1y", "1 year cagr": "cagr_1y", "1y return": "cagr_1y",
            "cagr 5y": "cagr_5y", "cagr 5 year": "cagr_5y", "5y cagr": "cagr_5y", "5 year cagr": "cagr_5y", "5y return": "cagr_5y",
            "cagr 3y": "cagr_3y", "cagr 3 year": "cagr_3y", "3y cagr": "cagr_3y", "3 year cagr": "cagr_3y", "3y return": "cagr_3y",
            "sharpe": "sharpe_ratio", "sortino": "sortino_ratio", "alpha": "alpha", "beta": "beta",
            "expense": "expense_ratio", "fee": "expense_ratio", "cost": "expense_ratio",
            "pe": "pe_ratio", "valuation": "pe_ratio"
        }
        for keyword, field in sort_mapping.items():
            if keyword in sort_field_text:
                filters["sort_by"] = field
                break

    if "ascending" in q or "asc" in q or "lowest" in q or "least" in q:
        filters["sort_order"] = "asc"
    elif "descending" in q or "desc" in q or "highest" in q or "most" in q:
        filters["sort_order"] = "desc"

    # 4. Build explanation text
    explanation_parts = []
    if filters["category"]:
        explanation_parts.append(f"category = '{filters['category']}'")
    for key, val in filters.items():
        if key not in ["category", "sort_by", "sort_order", "sql_explanation"] and val is not None:
            if "min_" in key:
                op = ">="
            else:
                op = "<="
            field_name = key.replace("min_", "").replace("max_", "")
            explanation_parts.append(f"{field_name} {op} {val}")
    
    if filters["sort_by"]:
        explanation_parts.append(f"sort by {filters['sort_by']} {filters['sort_order']}")
        
    if explanation_parts:
        filters["sql_explanation"] += ", ".join(explanation_parts) + "."
    else:
        filters["sql_explanation"] += "No specific filters matched, returning defaults sorted by CAGR 3Y."

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

