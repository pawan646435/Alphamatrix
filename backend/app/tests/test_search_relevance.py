import pytest
from app.api.v1.search import calculate_relevance_score

def test_relevance_score_exact_symbol():
    item = {"symbol": "TCS", "name": "Tata Consultancy Services"}
    # Exact symbol match (case-insensitive)
    score = calculate_relevance_score("tcs", "stock", item)
    assert score == 1000.0

def test_relevance_score_exact_name():
    item = {"symbol": "TCS", "name": "Tata Consultancy Services"}
    score = calculate_relevance_score("tata consultancy services", "stock", item)
    assert score == 900.0

def test_relevance_score_symbol_starts_with():
    item1 = {"symbol": "TCS", "name": "Tata Consultancy Services"}
    item2 = {"symbol": "TCSNEW", "name": "Tata Consultancy Services Next"}
    
    score1 = calculate_relevance_score("tc", "stock", item1)
    score2 = calculate_relevance_score("tc", "stock", item2)
    
    assert score1 >= 800.0
    assert score2 >= 800.0
    # Shorter symbol should have higher score
    assert score1 > score2

def test_relevance_score_name_starts_with():
    item = {"symbol": "TCS", "name": "Tata Consultancy Services"}
    score = calculate_relevance_score("tata", "stock", item)
    assert score >= 700.0

def test_relevance_score_word_starts_with():
    item = {"symbol": "TCS", "name": "Tata Consultancy Services"}
    score = calculate_relevance_score("consultancy", "stock", item)
    assert score >= 600.0

def test_relevance_score_substring_symbol():
    item = {"symbol": "INFYTCS", "name": "Infosys Tata"}
    score = calculate_relevance_score("tcs", "stock", item)
    assert score == 500.0

def test_relevance_score_substring_name():
    item = {"symbol": "INFY", "name": "Infosys Tata"}
    score = calculate_relevance_score("ata", "stock", item)
    assert score == 400.0

def test_relevance_score_fuzzy():
    item = {"symbol": "TCS", "name": "Tata Consultancy Services"}
    score = calculate_relevance_score("tata cnsultancy", "stock", item)
    assert 0.0 < score < 400.0
