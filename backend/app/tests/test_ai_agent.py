import pytest
from app.services.ai_agent import _mock_parse_semantic_query

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
