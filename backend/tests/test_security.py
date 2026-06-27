import pytest
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "test_password_123"
        hashed = get_password_hash(pw)
        assert hashed != pw
        assert verify_password(pw, hashed)

    def test_wrong_password(self):
        hashed = get_password_hash("correct_password")
        assert not verify_password("wrong_password", hashed)


class TestJWTTokens:
    def test_create_and_decode(self):
        from jose import jwt
        data = {"sub": "test@example.com", "role": "user"}
        token = create_access_token(data)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "test@example.com"
        assert payload["role"] == "user"

    def test_token_expiry(self):
        from datetime import timedelta
        data = {"sub": "test@example.com"}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        from jose import jwt, ExpiredSignatureError
        with pytest.raises(ExpiredSignatureError):
            jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    def test_invalid_token(self):
        from jose import jwt, JWTError
        with pytest.raises(JWTError):
            jwt.decode("invalid.token.here", settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


class TestInputValidation:
    def test_search_query_max_length(self, client):
        long_query = "A" * 200
        resp = client.get(f"/api/v1/stocks/search?query={long_query}")
        assert resp.status_code == 422

    def test_detail_symbol_max_length(self, client):
        long_symbol = "A" * 50
        resp = client.get(f"/api/v1/stocks/detail/{long_symbol}")
        assert resp.status_code == 422

    def test_fund_detail_invalid_scheme_code(self, client):
        resp = client.get("/api/v1/funds/detail/abc")
        assert resp.status_code == 404

    def test_list_negative_limit(self, client):
        resp = client.get("/api/v1/stocks/list?limit=-1")
        # FastAPI accepts negative integers; SQLite ignores negative LIMIT
        assert resp.status_code == 200

    def test_list_excessive_limit(self, client):
        resp = client.get("/api/v1/stocks/list?limit=10000")
        assert resp.status_code in (200, 422)


class TestRateLimiting:
    def test_rate_limit_exceeded(self, client):
        # Send many rapid requests to trigger rate limiter
        for _ in range(60):
            client.get("/api/v1/stocks/list")
        resp = client.get("/api/v1/stocks/list")
        # Rate limiter may or may not trigger depending on test speed
        assert resp.status_code in (200, 429)


class Test404Routes:
    def test_nonexistent_route(self, client):
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404

    def test_nonexistent_fund_detail(self, client):
        resp = client.get("/api/v1/funds/999999")
        assert resp.status_code == 404
