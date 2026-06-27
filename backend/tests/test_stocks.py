import pytest


class TestStockSearch:
    def test_search_by_symbol(self, client):
        resp = client.get("/api/v1/stocks/search?query=RELIANCE")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert data[0]["symbol"] == "RELIANCE"

    def test_search_by_company_name(self, client):
        resp = client.get("/api/v1/stocks/search?query=HDFC")
        assert resp.status_code == 200
        data = resp.json()
        assert any("HDFC" in item["company_name"] for item in data)

    def test_search_no_results(self, client):
        resp = client.get("/api/v1/stocks/search?query=NONEXISTENT123")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_empty_query(self, client):
        resp = client.get("/api/v1/stocks/search")
        assert resp.status_code == 422


class TestStockList:
    def test_list_default(self, client):
        resp = client.get("/api/v1/stocks/list")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5

    def test_list_with_sector_filter(self, client):
        resp = client.get("/api/v1/stocks/list?sector=IT")
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["sector"] == "IT" for s in data)

    def test_list_sort_by_cagr_3y(self, client):
        resp = client.get("/api/v1/stocks/list?sort_by=cagr_3y")
        assert resp.status_code == 200
        data = resp.json()
        vals = [s["cagr_3y"] for s in data if s["cagr_3y"] is not None]
        assert vals == sorted(vals, reverse=True)

    def test_list_sort_by_alpha_score(self, client):
        resp = client.get("/api/v1/stocks/list?sort_by=alpha_score")
        assert resp.status_code == 200
        data = resp.json()
        scores = [s["alpha_score"] for s in data if s["alpha_score"] is not None]
        assert scores == sorted(scores, reverse=True)

    def test_list_invalid_sort_field(self, client):
        resp = client.get("/api/v1/stocks/list?sort_by=invalid_field")
        # Invalid sort_by silently falls back to default ordering
        assert resp.status_code == 200

    def test_list_pagination(self, client):
        resp = client.get("/api/v1/stocks/list?skip=0&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestStockDetail:
    def test_detail_found(self, client):
        resp = client.get("/api/v1/stocks/detail/RELIANCE")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stock"]["symbol"] == "RELIANCE"
        assert data["stock"]["company_name"] == "Reliance Industries Ltd"

    def test_detail_not_found(self, client):
        # First call triggers dynamic ingestion and returns 202
        resp = client.get("/api/v1/stocks/detail/INVALID")
        assert resp.status_code in (202, 404)
        
        # Subsequent call returns 404 since it gets saved as Invalid
        resp = client.get("/api/v1/stocks/detail/INVALID")
        assert resp.status_code == 404


class TestStockCompare:
    def test_compare_two_symbols(self, client):
        resp = client.get("/api/v1/stocks/compare?s1=RELIANCE&s2=TCS")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stock1"]["symbol"] == "RELIANCE"
        assert data["stock2"]["symbol"] == "TCS"

    def test_compare_invalid_symbol(self, client):
        resp = client.get("/api/v1/stocks/compare?s1=RELIANCE&s2=INVALID")
        assert resp.status_code == 404


class TestStockAnalytics:
    def test_price_history(self, client):
        resp = client.get("/api/v1/stocks/detail/RELIANCE")
        assert resp.status_code == 200
        data = resp.json()
        # price_history may be empty but endpoint should still work
        assert "price_history" in data

    def test_stock_status(self, client):
        resp = client.get("/api/v1/stocks/status/RELIANCE")
        assert resp.status_code == 200


class TestWatchlist:
    def test_get_empty_watchlist(self, client):
        resp = client.get("/api/v1/stocks/watchlist")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_to_watchlist(self, client):
        resp = client.post("/api/v1/stocks/watchlist?symbol=RELIANCE")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_add_nonexistent_stock(self, client):
        resp = client.post("/api/v1/stocks/watchlist?symbol=INVALID")
        assert resp.status_code == 404

    def test_add_duplicate_to_watchlist(self, client):
        client.post("/api/v1/stocks/watchlist?symbol=RELIANCE")
        resp = client.post("/api/v1/stocks/watchlist?symbol=RELIANCE")
        assert resp.status_code == 200
        assert resp.json()["status"] == "already_added"

    def test_get_watchlist_after_add(self, client):
        client.post("/api/v1/stocks/watchlist?symbol=RELIANCE")
        client.post("/api/v1/stocks/watchlist?symbol=TCS")
        resp = client.get("/api/v1/stocks/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        symbols = {item["symbol"] for item in data}
        assert symbols == {"RELIANCE", "TCS"}

    def test_remove_from_watchlist(self, client):
        client.post("/api/v1/stocks/watchlist?symbol=RELIANCE")
        resp = client.delete("/api/v1/stocks/watchlist/RELIANCE")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_remove_not_in_watchlist(self, client):
        resp = client.delete("/api/v1/stocks/watchlist/RELIANCE")
        assert resp.status_code == 404

    def test_watchlist_after_remove(self, client):
        client.post("/api/v1/stocks/watchlist?symbol=RELIANCE")
        client.post("/api/v1/stocks/watchlist?symbol=TCS")
        client.delete("/api/v1/stocks/watchlist/RELIANCE")
        resp = client.get("/api/v1/stocks/watchlist")
        data = resp.json()
        assert "TCS" in [item["symbol"] for item in data]
        assert "RELIANCE" not in [item["symbol"] for item in data]


class TestWatchlistAnalytics:
    def test_watchlist_analytics_empty(self, client):
        resp = client.get("/api/v1/stocks/watchlist/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert "health_score" in data

    def test_watchlist_analytics_with_stocks(self, client):
        client.post("/api/v1/stocks/watchlist?symbol=RELIANCE")
        client.post("/api/v1/stocks/watchlist?symbol=TCS")
        resp = client.get("/api/v1/stocks/watchlist/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["health_score"] > 0
        assert "sector_exposure" in data


class TestSectorLab:
    def test_sector_lab(self, client):
        resp = client.get("/api/v1/stocks/sector/ENERGY")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sector"] == "Energy"
        assert len(data["top_stocks"]) >= 1

    def test_sector_lab_invalid(self, client):
        resp = client.get("/api/v1/stocks/sector/INVALID")
        assert resp.status_code == 404


class TestMarketRegime:
    def test_market_regime(self, client):
        resp = client.get("/api/v1/stocks/market-regime")
        assert resp.status_code == 200
        data = resp.json()
        assert "regime" in data
