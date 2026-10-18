"""
Tests for Backend Configuration and Production Security Validation (tests/app/test_config.py).
"""

import pytest
from pydantic import ValidationError

from Backend.app.config import Settings


def test_settings_development_defaults():
    s = Settings(_env_file=None, ENVIRONMENT="development", SUPABASE_URL="https://localhost.supabase.co")
    assert s.ENVIRONMENT == "development"
    assert s.COOKIE_SECURE is False
    assert s.AI_ENABLED is False


def test_settings_allowed_origins_parsing():
    s = Settings(ALLOWED_ORIGINS="http://localhost:3000, https://app.aegis.com")
    assert s.ALLOWED_ORIGINS == ["http://localhost:3000", "https://app.aegis.com"]

    s_empty = Settings(ALLOWED_ORIGINS="")
    assert s_empty.ALLOWED_ORIGINS == []


def test_settings_production_rejects_insecure_cookies():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            COOKIE_SECURE=False,
            SUPABASE_URL="https://prod.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_pub_real",
            SUPABASE_SECRET_KEY="sb_sec_real",
        )
    assert "COOKIE_SECURE must be true in production" in str(exc.value)


def test_settings_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            COOKIE_SECURE=True,
            ALLOWED_ORIGINS="*",
            SUPABASE_URL="https://prod.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_pub_real",
            SUPABASE_SECRET_KEY="sb_sec_real",
        )
    assert "Wildcard origins '*' are prohibited" in str(exc.value)


def test_settings_production_rejects_dummy_keys():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            COOKIE_SECURE=True,
            SUPABASE_URL="https://prod.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="your-supabase-publishable-key",
            SUPABASE_SECRET_KEY="your-supabase-secret-key",
        )
    assert "Valid SUPABASE_PUBLISHABLE_KEY is required" in str(exc.value)
