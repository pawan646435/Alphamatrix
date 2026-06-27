import pytest


class TestFundSearch:
    def test_search_returns_results(self, client):
        resp = client.get("/api/v1/funds/search?query=HDFC")
        assert resp.status_code == 200

    def test_search_empty_query(self, client):
        resp = client.get("/api/v1/funds/search")
        assert resp.status_code == 422

    def test_search_min_length_query(self, client):
        resp = client.get("/api/v1/funds/search?query=a")
        assert resp.status_code == 200


class TestFundList:
    def test_list_default(self, client):
        resp = client.get("/api/v1/funds/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        vals = [f.get("cagr_3y") for f in data if f.get("cagr_3y") is not None]
        if vals:
            assert vals == sorted(vals, reverse=True)

    def test_list_filter_by_category(self, client):
        resp = client.get("/api/v1/funds/?category=Large Cap")
        assert resp.status_code == 200
        data = resp.json()
        assert all(f["category"] == "Large Cap" for f in data)

    def test_list_invalid_sort(self, client):
        resp = client.get("/api/v1/funds/?sort_by=invalid")
        # Invalid sort_by silently falls back to default ordering
        assert resp.status_code == 200

    def test_list_pagination(self, client):
        resp = client.get("/api/v1/funds/?skip=0&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestFundDetail:
    def test_detail_found(self, client):
        resp = client.get("/api/v1/funds/120687")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fund"]["scheme_code"] == 120687
        assert "HDFC" in data["fund"]["fund_name"]

    def test_detail_returns_all_fields(self, client):
        resp = client.get("/api/v1/funds/120687")
        assert resp.status_code == 200
        data = resp.json()
        fund = data["fund"]
        assert fund["expense_ratio"] == 0.35
        assert fund["alpha"] == 0.12
        assert fund["beta"] == 1.0
        assert fund["sharpe_ratio"] == 0.85

    def test_detail_sbi_fund(self, client):
        resp = client.get("/api/v1/funds/118550")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fund"]["scheme_code"] == 118550
        assert "SBI" in data["fund"]["fund_name"]
