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
        model = genai.GenerativeModel("gemini-2.5-flash")
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
        model = genai.GenerativeModel("gemini-2.5-flash")
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
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_instruction)
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


# --- NEW STOCKS AI METHODS ---

async def generate_stock_briefing(stock_data: Dict[str, Any], historical_prices: List[Dict[str, Any]] = None) -> str:
    """
    Generates a comprehensive Markdown equity research report briefing
    using Gemini-3.1-flash-lite.
    """
    if not gemini_configured:
        return _generate_mock_stock_briefing(stock_data)
        
    symbol = stock_data.get("symbol", "")
    company_name = stock_data.get("company_name", "")
    sector = stock_data.get("sector", "")
    industry = stock_data.get("industry", "")
    
    prompt = f"""
You are a Lead Portfolio Manager and CFA specializing in Indian Equities.
Analyze the following stock details and write a highly professional, comprehensive equity research report briefing.

Stock Details:
- Symbol: {symbol}
- Name: {company_name}
- Sector: {sector}
- Industry: {industry}
- Market Cap: ₹{stock_data.get('market_cap')} Cr
- PE Ratio: {stock_data.get('pe_ratio')}
- PB Ratio: {stock_data.get('pb_ratio')}
- ROE: {stock_data.get('roe')}%
- Debt/Equity: {stock_data.get('debt_equity')}
- Dividend Yield: {stock_data.get('dividend_yield')}%
- Beta: {stock_data.get('beta')}
- Alpha Score: {stock_data.get('alpha_score')}
- 1-Year Price Trend: {round((stock_data.get('cagr_1y') or 0)*100, 2)}%
- 3-Year CAGR: {round((stock_data.get('cagr_3y') or 0)*100, 2)}%
- 5-Year CAGR: {round((stock_data.get('cagr_5y') or 0)*100, 2)}%

Format:
Return the output in clean Markdown. You MUST include these headers exactly:
### Executive Summary
(summary content)

### Performance Analysis
(analysis of trend, cagr, volatility)

### Fundamental Analysis
(analysis of profitability, leverage, valuation vs industry peers)

### Sector Analysis
(industry drivers, tailwinds/headwinds)

### Macro Analysis
(interest rates, inflation impact)

### Geopolitical Analysis
(trade policy, global supply chain implications)

### Investment Thesis
(detailed bullet points of the positive drivers and reasons to invest)

### Risk Factors
(detailed bullet points of risks, concerns, or reasons NOT to invest)

### Research Timeline
(significant historical events and near-future projections in chronological order. Each timeline entry MUST be on a new line and use EXACTLY the format: - **Month Year**: Description)

### Bull Case
(upside scenarios)

### Base Case
(expected performance)

### Bear Case
(downside risks)

### Final Verdict
(Choose either **Strong Buy**, **Buy**, **Accumulate**, **Hold**, or **Avoid**)

### Confidence Score & Risk Rating
Confidence Score: [0-100]
Risk Rating: [Low | Medium | High]

Safety Constraint: Do NOT state anything with absolute certainty. Always write using probability-based language (e.g., 'represents a likely possibility', 'potential risk factor under interest rate pressure', 'probable trend').
"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        briefing = response.text.strip()
        if not briefing:
            return _generate_mock_stock_briefing(stock_data)
        return briefing
    except Exception as e:
        logger.error(f"Gemini stock briefing generation failed: {e}. Falling back to mock.")
        return _generate_mock_stock_briefing(stock_data)

async def run_stock_chat(message: str, history: List[ChatMessage], stock_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Conversational chatbot for stocks with context injection.
    """
    if not gemini_configured:
        return _mock_stock_chat_response(message, stock_data)
        
    system_instruction = (
        "You are AlphaMatrix AI Equity Analyst. You help users analyze Indian stocks, explain fundamental ratios, and compare companies. "
        "When the user asks about investing in a stock, you must check its returns, sector metrics, valuation parameters, and give a clear recommendation of "
        "either BUY, HOLD, or AVOID in bold, considering macroeconomic risks. Never claim certainty."
    )
    
    context = ""
    if stock_data:
        context = f"""
Currently the user is viewing details for the stock: {stock_data.get('company_name')} ({stock_data.get('symbol')}).
Metrics:
- Sector: {stock_data.get('sector')}
- Market Cap: ₹{stock_data.get('market_cap')} Cr
- P/E Ratio: {stock_data.get('pe_ratio')}
- P/B Ratio: {stock_data.get('pb_ratio')}
- ROE: {stock_data.get('roe')}%
- Debt/Equity: {stock_data.get('debt_equity')}
- Dividend Yield: {stock_data.get('dividend_yield')}%
- Beta: {stock_data.get('beta')}
- Alpha Score: {stock_data.get('alpha_score')}
- CAGR 1Y: {round((stock_data.get('cagr_1y') or 0)*100, 2)}%
- CAGR 3Y: {round((stock_data.get('cagr_3y') or 0)*100, 2)}%
- CAGR 5Y: {round((stock_data.get('cagr_5y') or 0)*100, 2)}%
Use these details to answer user queries about this stock.
"""
    
    contents = []
    for msg in history:
        contents.append({"role": "user" if msg.role == "user" else "model", "parts": [msg.content]})
        
    latest_parts = [f"{context}\nUser Question: {message}"]
    contents.append({"role": "user", "parts": latest_parts})
    
    try:
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_instruction)
        response = model.generate_content(contents)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini stock chat failed: {e}")
        return f"I apologize, I encountered an issue interacting with the AI endpoint. Here is a baseline response based on stock context:\n{_mock_stock_chat_response(message, stock_data)}"

async def generate_watchlist_analytics(stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a complete portfolio diagnostics analysis for saved watchlist stocks.
    """
    if not stocks:
        return {
            "health_score": 0.0,
            "ai_summary": "No stocks in watchlist.",
            "biggest_opportunity": "N/A",
            "biggest_risk": "N/A",
            "most_volatile_position": "N/A",
            "best_performing_position": "N/A"
        }
        
    if not gemini_configured:
        return _generate_mock_watchlist_analytics(stocks)
        
    stocks_summary = []
    for s in stocks:
        stocks_summary.append(
            f"Symbol: {s.get('symbol')}, Name: {s.get('company_name')}, Sector: {s.get('sector')}, PE: {s.get('pe_ratio')}, ROE: {s.get('roe')}%, "
            f"Debt/Equity: {s.get('debt_equity')}, Beta: {s.get('beta')}, Alpha Score: {s.get('alpha_score')}, "
            f"1Y Return: {round((s.get('cagr_1y') or 0)*100, 2)}%"
        )
        
    prompt = f"""
You are a Lead Portfolio Risk Analyst and CFA. Analyze the following user stock watchlist and output a structured portfolio diagnostics JSON report.

Watchlisted Stocks:
{chr(10).join(stocks_summary)}

Output format:
Return ONLY a JSON object with this exact schema:
{{
  "health_score": float,  // A score from 0 to 100 indicating the overall fundamental strength & safety of the portfolio
  "ai_summary": "A 2-sentence summary of the portfolio diversification, quality, and overall health.",
  "strongest_position": "Stock Symbol: Short explanation of why this position is fundamentals-wise the strongest in the watchlist.",
  "weakest_position": "Stock Symbol: Short explanation of why this position represents the weakest link (due to high leverage, poor margins, or valuation).",
  "risk_concentration": "Assessment of concentration risks (e.g. over-exposure to certain sectors, high beta profiles, or debt levels).",
  "sector_exposure": "Brief breakdown of the sector weights and exposure balance in the watchlist."
}}
"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text.strip())
    except Exception as e:
        logger.error(f"Gemini watchlist diagnostics failed: {e}")
        return _generate_mock_watchlist_analytics(stocks)

async def generate_sector_outlook(sector: str, stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a sectoral health score, growth drivers, risks, and AI outlook using Gemini.
    """
    if not gemini_configured:
        return _generate_mock_sector_outlook(sector, stocks)
        
    stocks_summary = []
    for s in stocks:
        stocks_summary.append(
            f"Symbol: {s.get('symbol')}, Name: {s.get('company_name')}, PE: {s.get('pe_ratio')}, ROE: {s.get('roe')}%, Debt/Equity: {s.get('debt_equity')}, 1Y Return: {round((s.get('cagr_1y') or 0)*100, 2)}%"
        )
        
    prompt = f"""
You are a Lead Industry Researcher. Analyze the following sector and its seeded companies to output a structured sector diagnostics report.

Sector: {sector}
Seeded Companies:
{chr(10).join(stocks_summary)}

Output format:
Return ONLY a JSON object with this exact schema:
{{
  "sector": "{sector}",
  "sector_score": float,  // Sector score from 0 to 100 based on current growth momentum, tailwinds, and risks
  "growth_drivers": [
    "Driver 1: explanation",
    "Driver 2: explanation"
  ],  // List of exactly 2 key growth drivers
  "major_risks": [
    "Risk 1: explanation",
    "Risk 2: explanation"
  ],  // List of exactly 2 major risks
  "ai_outlook": "A professional paragraph detailing the 1-2 year outlook of the {sector} sector, considering macro headwinds, government policy, and digital transformations."
}}
"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text.strip())
    except Exception as e:
        logger.error(f"Gemini sector outlook generation failed: {e}")
        return _generate_mock_sector_outlook(sector, stocks)


# --- MOCK FALLBACKS FOR STOCKS ---

def _generate_mock_stock_briefing(stock_data: Dict[str, Any]) -> str:
    sym = stock_data.get("symbol", "")
    name = stock_data.get("company_name", "")
    sector = stock_data.get("sector", "")
    industry = stock_data.get("industry", "")
    pe = stock_data.get("pe_ratio", "N/A")
    roe = stock_data.get("roe", "N/A")
    beta = stock_data.get("beta", "N/A")
    alpha_score = stock_data.get("alpha_score", "N/A")
    ret_1y = round((stock_data.get('cagr_1y') or 0)*100, 2)
    ret_3y = round((stock_data.get('cagr_3y') or 0)*100, 2)
    
    verdict = "BUY"
    if float(alpha_score) >= 80:
        verdict = "Strong Buy"
    elif float(alpha_score) < 45:
        verdict = "Avoid"
    elif float(alpha_score) < 60:
        verdict = "Hold"
        
    return f"""### Executive Summary
{name} ({sym}) represents a leading enterprise in the {sector} sector ({industry}). With an Alpha Score of {alpha_score}/100, it demonstrates a robust quantitative and qualitative investment setup. The company appears positioned to capture long-term structural tailwinds despite temporary market fluctuations.

### Performance Analysis
Over the past year, the stock has delivered a trend return of {ret_1y}%, which stands in comparison to its 3-Year CAGR of {ret_3y}%. With a Beta of {beta}, the stock exhibits {'above' if beta > 1.0 else 'below'} average systemic volatility relative to the benchmark Nifty 50 index.

### Fundamental Analysis
From a fundamental stance, the business reports an ROE of {roe}% and a P/E Ratio of {pe}. Profitability metrics show strong efficiency, while leverage levels (Debt/Equity: {stock_data.get('debt_equity')}) remain within manageable bounds for the industry.

### Sector Analysis
The {sector} sector is seeing significant technological integration and consolidation. Market leaders are likely to experience pricing power and market share gains, although wage inflation or regulatory updates could pose margin pressures.

### Macro Analysis
Monetary policy, interest rate shifts, and consumer inflation cycles present systematic risks. A higher interest rate regime could raise capital costs, though the company's strong balance sheet likely mitigates severe liquidity friction.

### Geopolitical Analysis
Trade frictions and shifting geopolitical alliances impact global supply chains. As an Indian enterprise, domestic policy push and export diversification efforts represent probable buffers against global macro friction.

### Investment Thesis
- Strong market leadership under the {name} brand with high operational barriers to entry.
- Favorable balance sheet with robust cash-flow conversion and high Return on Equity ({roe}%).
- Strong tailwinds in the {sector} space supporting long-term structural compounding.

### Risk Factors
- Potential wage inflation and rising talent retention costs within the {industry} industry.
- Macroeconomic interest rate cycles increasing funding costs for capital expenditure.
- Potential competitive pressure from regional/international entrants leading to margin dilution.

### Research Timeline
- **June 2023**: Completed major infrastructure scaling to support high-throughput clients.
- **December 2023**: Secured a major multi-year domestic contract enhancing order book visibility.
- **July 2024**: Launched AI-assisted workflow modules, driving early margin expansion.
- **March 2025**: Projected expansion into regional international markets to diversify revenue base.

### Bull Case
Under favorable economic growth, the stock has potential to experience valuation expansion, driven by robust order books, margin recovery, and accelerating compound yields.

### Base Case
Our base expectation assumes steady margin maintenance and volume growth, yielding returns in line with its historical 3-Year CAGR performance bounds.

### Bear Case
Downside risks involve localized demand deceleration, supply disruptions, or high competitive intensity, which could depress margins and trigger valuation contraction.

### Final Verdict
We assign a definitive **{verdict}** recommendation for this counter.

### Confidence Score & Risk Rating
Confidence Score: 85
Risk Rating: {'High' if beta > 1.2 else 'Medium' if beta > 0.8 else 'Low'}
"""

def _mock_stock_chat_response(message: str, stock_data: Optional[Dict[str, Any]] = None) -> str:
    q = message.lower()
    if stock_data:
        sym = stock_data.get("symbol")
        name = stock_data.get("company_name")
        sector = stock_data.get("sector")
        pe = stock_data.get("pe_ratio")
        roe = stock_data.get("roe")
        beta = stock_data.get("beta")
        alpha_score = stock_data.get("alpha_score")
        ret_1y = round((stock_data.get('cagr_1y') or 0)*100, 2)
        
        verdict = "HOLD"
        if float(alpha_score) >= 75:
            verdict = "BUY"
        elif float(alpha_score) < 50:
            verdict = "AVOID"
            
        if any(term in q for term in ["invest", "recommend", "buy", "should i", "avoid", "hold"]):
            return (
                f"Regarding your query about investing in {name} ({sym}), here is my equity analysis:\n\n"
                f"1. **Alpha Score**: The stock boasts a proprietary Alpha Score of **{alpha_score}/100**, indicating a strong combination of fundamental quality and valuation safety.\n"
                f"2. **Returns**: Its 1-year yield is {ret_1y}%, exhibiting solid short-term momentum.\n"
                f"3. **Beta Profile**: With a Beta of {beta}, the stock possesses a {'higher' if beta > 1.0 else 'lower'} volatility index than the market index.\n"
                f"4. **Verdict**: We recommend a **{verdict}** stance for this counter under current macroeconomic conditions."
            )
            
        if any(term in q for term in ["pe", "roe", "fundamental", "ratio", "valuation"]):
            return f"The fundamental ratios for {sym} are:\n- P/E Ratio: {pe}\n- Return on Equity (ROE): {roe}%\n- Debt/Equity: {stock_data.get('debt_equity')}\nThese reflect the firm's operational leverage and multiple valuation."
            
    return "I am your AlphaMatrix AI Equity Analyst. Ask me about stock valuations, compare sectors, check watchlist metrics, or analyze individual corporate details."

def _generate_mock_watchlist_analytics(stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    scores = [s.get("alpha_score", 50) for s in stocks]
    avg_score = sum(scores) / len(scores) if scores else 0
    symbols = [s.get("symbol") for s in stocks]
    
    strongest = symbols[0] if symbols else "N/A"
    weakest = symbols[-1] if len(symbols) > 1 else "N/A"
    sectors = list(set([s.get("sector") for s in stocks]))
    sector_str = ", ".join(sectors) if sectors else "None"
    
    return {
        "health_score": round(avg_score, 1),
        "ai_summary": f"Your watchlist containing {len(stocks)} stocks shows healthy sector diversification across {sector_str}. The aggregate score is supported by quality names, though attention should be paid to high valuation multiples.",
        "strongest_position": f"{strongest}: Demonstrates excellent capital efficiency with high ROE and strong market momentum.",
        "weakest_position": f"{weakest}: Exhibits higher relative valuation multiples or balance sheet leverage.",
        "risk_concentration": "Systemic risk is moderate. Beta metrics are centered around historical benchmark levels.",
        "sector_exposure": f"Watchlist spans key sectors: {sector_str} with balanced allocations."
    }

def _generate_mock_sector_outlook(sector: str, stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    scores = [s.get("alpha_score", 50) for s in stocks]
    avg_score = sum(scores) / len(scores) if scores else 65.0
    
    drivers = {
        "IT": ["Digital Transformation: enterprise spending on cloud and AI migration.", "Global In-Sourcing: increase in long-term offshoring contracts."],
        "Banking": ["Credit Growth: expansion in retail and corporate loan portfolios.", "Margin Strength: favorable net interest margins in a stable rate cycle."],
        "Auto": ["EV Transition: rising consumer adoption of electric and hybrid drivetrains.", "Premiumization: higher average selling prices in SUVs and premium sedans."],
        "Defence": ["Indigenization: domestic production mandates from the Ministry of Defence.", "Export Expansion: rising exports of aerospace and defense electronics."],
        "Energy": ["Green Energy CapEx: investments in solar, hydrogen, and clean infrastructure.", "Refining Margins: robust regional refining margins supporting fossil cash flows."],
        "FMCG": ["Rural Demand Recovery: stabilization of rural disposable income.", "Premium Portfolio Expansion: higher gross margins on premium consumer goods."]
    }
    
    risks = {
        "IT": ["Talent Costs: high wage inflation and subcontractor costs.", "Macro Slowdown: reduced capital budgets in US/EU banking clients."],
        "Banking": ["Asset Quality: potential rise in retail unsecured loan delinquencies.", "Deposit Costs: tight liquidity forcing banks to offer higher deposit rates."],
        "Auto": ["Commodity Inflation: price volatility in steel, copper, and battery inputs.", "Interest Rates: higher financing costs tempering entry-level vehicle demand."],
        "Defence": ["Execution Delay: long gestation and delivery schedules on capital projects.", "Budget Constraints: dependence on government defense capital allocations."],
        "Energy": ["Windfall Taxes: government regulatory price caps on crude extraction.", "Transition Cost: massive cash requirements for transition to net-zero assets."],
        "FMCG": ["Input Inflation: raw material cost increases in palm oil and packaging.", "Local Competition: rise of regional direct-to-consumer brands."]
    }
    
    default_drivers = ["Capital Expenditure: expansion of domestic manufacturing capacity.", "Policy Support: government incentives for production and localization."]
    default_risks = ["Inflation: rising raw material and wage expenses.", "Global Headwinds: export slowdown due to international economic deceleration."]
    
    return {
        "sector": sector,
        "sector_score": round(avg_score, 1),
        "growth_drivers": drivers.get(sector, default_drivers),
        "major_risks": risks.get(sector, default_risks),
        "ai_outlook": f"The {sector} sector is entering a phase of steady transition. Driven by structural shifts, digital initiatives, and capacity expansion, market leaders are expected to maintain operational leverage. Key monitorables include wage pressures and raw material price stability over the next fiscal quarters."
    }

async def get_market_regime_diagnostics() -> Dict[str, Any]:
    """
    Evaluates current macroeconomic factors (Repo rates, CPI inflation, VIX volatility, and market breadth)
    to determine the current Market Regime (RISK ON, RISK OFF, or NEUTRAL).
    Returns a dictionary with 'regime', 'confidence', and 'explanation'.
    """
    if not gemini_configured:
        return _generate_mock_market_regime()
        
    prompt = """
You are a Chief Global Macro Strategist and CFA.
Analyze the current macroeconomic and market conditions for Indian equities.
Evaluate the current setup across:
1. Interest Rate Cycle (RBI Repo rates, Fed interest rate decisions)
2. Inflation pressures (CPI)
3. Market Volatility (VIX index)
4. Market Breadth (Advancers vs Decliners ratio)

Based on these parameters, diagnose the current Market Regime.
Choose one of these regimes exactly: RISK ON, RISK OFF, or NEUTRAL.

Output format:
Return ONLY a JSON object with this exact schema:
{
  "regime": "RISK ON" | "RISK OFF" | "NEUTRAL",
  "confidence": float,  // Confidence level from 0 to 100
  "explanation": "A professional 2-sentence explanation of the macro indicators and market variables driving this regime diagnosis."
}
"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text.strip())
    except Exception as e:
        logger.error(f"Gemini market regime diagnostics failed: {e}")
        return _generate_mock_market_regime()

def _generate_mock_market_regime() -> Dict[str, Any]:
    return {
        "regime": "RISK ON",
        "confidence": 78.0,
        "explanation": "Equity markets display strong momentum. Repo rates are peaking with expected cuts, inflation is moderating toward target ranges, and the VIX is low, indicating a supportive environment for equity inflows."
    }

async def generate_stock_comparison(s1_data: Dict[str, Any], s2_data: Dict[str, Any]) -> str:
    """
    Generates a comparative research analysis between two equities using gemini-2.5-flash.
    """
    if not gemini_configured:
        return _generate_mock_stock_comparison(s1_data, s2_data)
        
    prompt = f"""
You are a Lead Portfolio Manager and CFA. Compare the following two equities and write a professional, comparative analysis.

Stock 1: {s1_data.get('company_name')} ({s1_data.get('symbol')})
- Sector: {s1_data.get('sector')}
- Market Cap: ₹{s1_data.get('market_cap')} Cr
- PE Ratio: {s1_data.get('pe_ratio')}
- PB Ratio: {s1_data.get('pb_ratio')}
- ROE: {s1_data.get('roe')}%
- Debt/Equity: {s1_data.get('debt_equity')}
- Beta: {s1_data.get('beta')}
- Alpha Score: {s1_data.get('alpha_score')}/100
- 1-Year CAGR: {round((s1_data.get('cagr_1y') or 0)*100, 2)}%
- 3-Year CAGR: {round((s1_data.get('cagr_3y') or 0)*100, 2)}%

Stock 2: {s2_data.get('company_name')} ({s2_data.get('symbol')})
- Sector: {s2_data.get('sector')}
- Market Cap: ₹{s2_data.get('market_cap')} Cr
- PE Ratio: {s2_data.get('pe_ratio')}
- PB Ratio: {s2_data.get('pb_ratio')}
- ROE: {s2_data.get('roe')}%
- Debt/Equity: {s2_data.get('debt_equity')}
- Beta: {s2_data.get('beta')}
- Alpha Score: {s2_data.get('alpha_score')}/100
- 1-Year CAGR: {round((s2_data.get('cagr_1y') or 0)*100, 2)}%
- 3-Year CAGR: {round((s2_data.get('cagr_3y') or 0)*100, 2)}%

Provide a clean markdown output containing:
1. **Financial Comparison**: Comparative analysis of valuations, debt structure, and capital efficiency (ROE).
2. **Risk & Volatility**: Risk profiles, Beta implications, and balance sheet safety.
3. **Growth & Performance**: Momentum analysis of returns.
4. **AI Stance & Verdict**: A definitive conclusion on which equity is more favorable under current market conditions (or if they suit different investor profiles).

Safety Constraint: Use probability-based language. Avoid absolute statements.
"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini comparison failed: {e}")
        return _generate_mock_stock_comparison(s1_data, s2_data)

def _generate_mock_stock_comparison(s1: Dict[str, Any], s2: Dict[str, Any]) -> str:
    sym1 = s1.get("symbol")
    sym2 = s2.get("symbol")
    score1 = s1.get("alpha_score", 50)
    score2 = s2.get("alpha_score", 50)
    
    preferred = sym1 if score1 > score2 else sym2
    
    return f"""### Financial Comparison
**{s1.get('company_name')} ({sym1})** shows a P/E multiple of {s1.get('pe_ratio')} and ROE of {s1.get('roe')}%, whereas **{s2.get('company_name')} ({sym2})** operates at a P/E of {s2.get('pe_ratio')} and ROE of {s2.get('roe')}%. {sym1 if s1.get('roe', 0) > s2.get('roe', 0) else sym2} shows superior capital efficiency.

### Risk & Volatility
{sym1} exhibits a Beta of {s1.get('beta')} and Debt/Equity of {s1.get('debt_equity')}. In comparison, {sym2} features a Beta of {s2.get('beta')} and Debt/Equity of {s2.get('debt_equity')}. {sym1 if s1.get('beta', 0) < s2.get('beta', 0) else sym2} represents a relatively more defensive risk profile.

### Growth & Performance
Over a 3-year trailing period, {sym1} has achieved a CAGR of {round((s1.get('cagr_3y') or 0)*100, 2)}% compared to {sym2}'s CAGR of {round((s2.get('cagr_3y') or 0)*100, 2)}%. Momentum indicators show strong support for {sym1 if s1.get('cagr_1y', 0) > s2.get('cagr_1y', 0) else sym2}.

### AI Stance & Verdict
Based on the multi-factor Alpha Scores ({sym1}: {score1}/100, {sym2}: {score2}/100), **{preferred}** appears to represent a more favorable risk-adjusted combination of pricing power and valuation safety under current market conditions.
"""



