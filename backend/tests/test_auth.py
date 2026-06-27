import pytest


class TestLogin:
    def test_login_success(self, client):
        resp = client.post("/api/v1/auth/login", data={"username": "test@example.com", "password": "testpass123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["access_token"].startswith("mock-user-token-")

    def test_login_admin(self, client):
        resp = client.post("/api/v1/auth/login", data={"username": "admin@alphamatrix.com", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "mock-admin-token-alphamatrix"

    def test_login_short_password(self, client):
        resp = client.post("/api/v1/auth/login", data={"username": "test@example.com", "password": "12345"})
        assert resp.status_code == 401

    def test_login_empty_password(self, client):
        resp = client.post("/api/v1/auth/login", data={"username": "test@example.com", "password": ""})
        # OAuth2PasswordRequestForm validator rejects empty password with 422
        assert resp.status_code == 422


class TestSignup:
    def test_signup_success(self, client):
        resp = client.post("/api/v1/auth/signup?email=new@example.com&password=newpass123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["is_active"] is True
        assert "id" in data

    def test_signup_short_password(self, client):
        resp = client.post("/api/v1/auth/signup?email=new@example.com&password=12345")
        assert resp.status_code == 400

    def test_signup_invalid_email(self, client):
        resp = client.post("/api/v1/auth/signup?email=invalid&password=newpass123")
        assert resp.status_code == 422


class TestMe:
    def test_me_with_mock_token(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer mock-user-token-testuser"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is True
        assert "id" in data

    def test_me_with_admin_token(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer mock-admin-token-alphamatrix"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@alphamatrix.com"

    def test_me_without_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401 or resp.status_code == 403

    def test_me_with_login_token(self, client):
        login_resp = client.post("/api/v1/auth/login", data={"username": "user@test.com", "password": "validpass123"})
        token = login_resp.json()["access_token"]
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "user@alphamatrix.com"
