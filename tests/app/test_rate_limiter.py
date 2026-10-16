"""
Tests for Redis Rate Limiter and Fail-Closed Security Policy (tests/app/test_rate_limiter.py).
"""

from unittest.mock import patch

import pytest
from starlette.requests import Request

from Backend.app.config import settings
from Backend.app.deps import get_rate_limit_key
from Backend.app.errors import AppError
from Backend.app.rate_limiter import enforce_critical_route_rate_limit


def test_rate_limit_key_unauthenticated_ip():
    scope = {"type": "http", "client": ("192.168.1.50", 12345), "headers": []}
    req = Request(scope)
    key = get_rate_limit_key(req)
    assert key == "ip:192.168.1.50"


def test_fail_closed_in_production_when_redis_unavailable():
    scope = {"type": "http", "client": ("192.168.1.50", 12345), "headers": []}
    req = Request(scope)

    with (
        patch.object(settings, "ENVIRONMENT", "production"),
        patch("Backend.app.rate_limiter.is_redis_available", return_value=False),
        pytest.raises(AppError) as exc,
    ):
        enforce_critical_route_rate_limit(req, "login", max_requests=5, window_seconds=60)
    assert exc.value.status_code == 503
    assert exc.value.code == "rate_limiter_unavailable"
