"""
Tests for FastAPI Application Endpoints, Authentication, and Security Headers (tests/app/test_routes.py).
"""

import pytest
from fastapi.testclient import TestClient

from Backend.app.main import app
from Backend.app.repo import reset_mock_store


@pytest.fixture
def client():
    return TestClient(app, base_url="http://localhost:8000")


@pytest.fixture(autouse=True)
def clean_mock_store():
    reset_mock_store()


def test_health_check_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert resp.headers.get("X-Request-ID") is not None
    assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")


def test_auth_signup_neutral_message(client):
    resp = client.post(
        "/api/auth/signup",
        json={"email": "newuser@example.com", "password": "SecurePassword123!"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "If this email can be used, check your inbox."


def test_auth_login_sets_cookies(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "SecurePassword123!"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Login successful."
    assert "aegis_access_token" in resp.cookies


def test_auth_me_authenticated(client):
    # Login first
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "SecurePassword123!"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    access_cookie = login_resp.cookies.get("aegis_access_token")

    # Get /me with cookie
    me_resp = client.get("/api/auth/me", cookies={"aegis_access_token": access_cookie})
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == "00000000-0000-0000-0000-000000000002"


def test_auth_me_unauthorized_without_cookie(client):
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 401
    assert me_resp.json()["error"]["code"] == "unauthorized"


def test_auth_logout_clears_cookies(client):
    resp = client.post(
        "/api/auth/logout",
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Logged out successfully."


def test_csrf_protection_rejects_missing_header_on_post(client):
    resp = client.post(
        "/api/auth/signup",
        json={"email": "newuser@example.com", "password": "SecurePassword123!"},
        # Omits X-AEGIS-CSRF
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_extensions_list_empty(client):
    resp = client.get("/api/extensions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "imported"
    assert isinstance(data["extensions"], list)


def test_extension_detail_404(client):
    resp = client.get("/api/extensions/non-existent-uuid")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_ai_analyze_endpoint_returns_404_ai_unavailable(client):
    resp = client.post(
        "/api/extensions/some-ext-id/analyze",
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ai_unavailable"
