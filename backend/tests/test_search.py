import pytest


class TestGlobalSearch:
    def test_search_empty_without_fts(self, client):
        resp = client.get("/api/v1/search?query=RELIANCE")
        # Returns 200 even without FTS tables - query is processed
        assert resp.status_code == 200

    def test_search_short_query(self, client):
        resp = client.get("/api/v1/search?query=a")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_type_stock(self, client):
        resp = client.get("/api/v1/search?query=RELIANCE&type=stock")
        assert resp.status_code == 200

    def test_search_type_fund(self, client):
        resp = client.get("/api/v1/search?query=HDFC&type=fund")
        assert resp.status_code == 200
