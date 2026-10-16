"""
Tests for Security, JWT Verification, and CSRF Protection (tests/app/test_security.py).
"""

import asyncio

import pytest
from starlette.requests import Request

from Backend.app.errors import ForbiddenError, UnauthorizedError
from Backend.app.security import (
    ACCESS_COOKIE_NAME,
    extract_token_from_request,
    verify_csrf_protection,
    verify_jwt_token,
)


def test_jwt_verification_rejects_empty():
    with pytest.raises(UnauthorizedError):
        asyncio.run(verify_jwt_token(""))


def test_jwt_verification_rejects_malformed():
    with pytest.raises(UnauthorizedError):
        asyncio.run(verify_jwt_token("not-a-valid-jwt-token"))


def test_jwt_mock_token_in_dev():
    payload = asyncio.run(verify_jwt_token("mock-user-token-00000000-0000-0000-0000-000000000009"))
    assert payload["sub"] == "00000000-0000-0000-0000-000000000009"
    assert payload["aud"] == "authenticated"


def test_csrf_allows_safe_methods():
    scope = {"type": "http", "method": "GET", "headers": []}
    req = Request(scope)
    # Should not raise
    verify_csrf_protection(req)


def test_csrf_rejects_missing_custom_header():
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"origin", b"http://localhost:8000"), (b"host", b"localhost:8000")],
    }
    req = Request(scope)
    with pytest.raises(ForbiddenError) as exc:
        verify_csrf_protection(req)
    assert "Missing required X-AEGIS-CSRF header" in str(exc.value)


def test_csrf_rejects_mismatched_origin():
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [
            (b"x-aegis-csrf", b"1"),
            (b"origin", b"https://evil-attacker.com"),
            (b"host", b"localhost:8000"),
        ],
    }
    req = Request(scope)
    with pytest.raises(ForbiddenError) as exc:
        verify_csrf_protection(req)
    assert "Cross-origin request rejected" in str(exc.value)


def test_csrf_accepts_valid_header_and_origin():
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [
            (b"x-aegis-csrf", b"1"),
            (b"origin", b"http://localhost:8000"),
            (b"host", b"localhost:8000"),
        ],
    }
    req = Request(scope)
    # Should not raise
    verify_csrf_protection(req)


def test_extract_token_from_cookie():
    scope = {
        "type": "http",
        "headers": [
            (b"cookie", f"{ACCESS_COOKIE_NAME}=token123".encode()),
        ],
    }
    req = Request(scope)
    assert extract_token_from_request(req) == "token123"


def test_extract_token_from_authorization_header():
    scope = {
        "type": "http",
        "headers": [
            (b"authorization", b"Bearer header-token-456"),
        ],
    }
    req = Request(scope)
    assert extract_token_from_request(req) == "header-token-456"
