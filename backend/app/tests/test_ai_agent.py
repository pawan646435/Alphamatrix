import pytest
from app.services.ai_agent import _mock_parse_semantic_query, clean_r1_response


def test_mock_parser_lost_money_sharpe():
    query = "Which funds lost money over the last year but still maintain a Sharpe ratio above 1"
    filters = _mock_parse_semantic_query(query)
    
    assert filters["max_cagr_1y"] == 0.0
    assert filters["min_sharpe_ratio"] == 1.0
    assert "cagr_1y <= 0.0" in filters["sql_explanation"]
    assert "sharpe_ratio >= 1.0" in filters["sql_explanation"]
    
    # State leakage check: make sure pe_ratio doesn't bleed from the word "sharpe"
    assert filters["min_pe_ratio"] is None
    assert filters["max_pe_ratio"] is None

def test_mock_parser_category_and_cagr():
    query = "small cap funds with cagr > 15% in 3y"
    filters = _mock_parse_semantic_query(query)
    
    assert filters["category"] == "SMALL_CAP"
    assert filters["min_cagr_3y"] == 15.0
    assert filters["max_cagr_3y"] is None

def test_mock_parser_low_pe_and_large_cap():
    query = "large cap bluechip funds with pe ratio below 25"
    filters = _mock_parse_semantic_query(query)
    
    assert filters["category"] == "LARGE_CAP"
    assert filters["max_pe_ratio"] == 25.0
    assert filters["min_pe_ratio"] is None

def test_mock_parser_low_expense():
    query = "index funds with expense ratio under 0.8"
    filters = _mock_parse_semantic_query(query)
    
    assert filters["category"] == "INDEX"
    assert filters["max_expense_ratio"] == 0.8

def test_mock_parser_sorting_overrides():
    query = "mid cap sorted by sharpe descending"
    filters = _mock_parse_semantic_query(query)
    
    assert filters["category"] == "MID_CAP"
    assert filters["sort_by"] == "sharpe_ratio"
    assert filters["sort_order"] == "desc"

def test_mock_parser_dropped_constraints():
    query = "index funds with positive 1-year returns"
    filters = _mock_parse_semantic_query(query)
    
    # Verify both index category and positive return constraint are parsed
    assert filters["category"] == "INDEX"
    assert filters["min_cagr_1y"] == 0.0
    assert filters["max_cagr_1y"] is None

def test_mock_parser_fresh_state_leakage():
    # Call once with PE
    _mock_parse_semantic_query("funds with pe ratio above 15")
    
    # Call again with just returns and sharpe
    query = "index funds with positive 1-year returns and sharpe ratio above 1.2"
    filters = _mock_parse_semantic_query(query)
    
    assert filters["category"] == "INDEX"
    assert filters["min_cagr_1y"] == 0.0
    assert filters["min_sharpe_ratio"] == 1.2
    
    # Verify no pe_ratio constraint has bled in
    assert filters["min_pe_ratio"] is None
    assert filters["max_pe_ratio"] is None

def test_clean_r1_response_no_thinking():
    assert clean_r1_response("Here is the clean response.") == "Here is the clean response."

def test_clean_r1_response_with_thinking():
    text = "<think>\nThinking process here...\n</think>\nActual response output."
    assert clean_r1_response(text) == "Actual response output."

def test_clean_r1_response_case_insensitive_and_multiline():
    text = "<THINK>first step\nsecond step</THINK>Response with different casing."
    assert clean_r1_response(text) == "Response with different casing."

def test_clean_r1_response_multiple_thinking_blocks():
    text = "<think>first block</think>Middle part<think>second block</think>Final response."
    assert clean_r1_response(text) == "Middle partFinal response."

def test_clean_r1_response_empty_or_none():
    assert clean_r1_response("") == ""
    assert clean_r1_response(None) == ""

from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_parse_semantic_query_with_groq():
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "<think>reasoning</think>{\n  \"category\": \"MID_CAP\",\n  \"min_cagr_1y\": 10.0,\n  \"sql_explanation\": \"mapped mid cap\"\n}"
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    
    with patch("app.services.ai_agent.groq_client", mock_client), \
         patch("app.services.ai_agent.groq_configured", True):
        from app.services.ai_agent import parse_semantic_query
        result = await parse_semantic_query("mid cap funds with cagr > 10%")
        
        # Verify result is parsed correctly and <think> is stripped
        assert result["category"] == "MID_CAP"
        assert result["min_cagr_1y"] == 10.0
        assert result["sort_order"] == "desc"  # Default fallback
        mock_client.chat.completions.create.assert_called_once()

