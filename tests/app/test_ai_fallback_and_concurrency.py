"""
Tests for AI Overview Fallback, Error Resilience, Caching and Concurrency De-duplication (tests/app/test_ai_fallback_and_concurrency.py).
Verifies:
1. Timeout gives 200 plus fallback (is_fallback=True, model="llama-3.1-8b-instant-fallback").
2. 500 from Groq gives 200 plus fallback.
3. Success is cached and the second call does not hit Groq.
4. Fallback is NOT cached under the real key.
5. Ten concurrent identical requests produce exactly ONE Groq call.
"""

import asyncio
import json
from unittest.mock import patch
import httpx
import pytest
from fastapi.testclient import TestClient

from Backend.app.config import settings
from Backend.app.db import (
    db_delete_ai_overview,
    db_get_ai_overview,
    db_insert_snapshot,
    db_upsert_extension,
    init_db,
)
from Backend.app.main import app
from Backend.app.rate_limiter import limiter
from Backend.app.repo import _MOCK_STORE
from Backend.app.services.ai import PROMPT_VERSION


@pytest.fixture(autouse=True)
def setup_test_ext():
    init_db()

    # Disable limiter for resilience unit tests
    old_limiter_enabled = limiter.enabled
    limiter.enabled = False

    # Force settings to have a dummy key so it attempts Groq calls rather than skipping to mock
    old_key = settings.GROQ_API_KEY
    settings.GROQ_API_KEY = "gsk_test_mock_key_1234567890abcdef"

    ext_id = "test-resilience-ext-001"
    ext_record = {
        "id": ext_id,
        "user_id": "00000000-0000-0000-0000-000000000001",
        "browser": "chrome",
        "store_id": ext_id,
        "name": "Resilience Test Extension",
        "is_public": True,
        "description": "Tests AI fallback and concurrency resilience.",
        "updated_at": "2026-10-20T12:00:00Z",
    }
    db_upsert_extension(ext_record)

    snap = {
        "id": f"snap-{ext_id}-1.0.0",
        "extension_id": ext_id,
        "user_id": "00000000-0000-0000-0000-000000000001",
        "version": "1.0.0",
        "api_permissions": ["storage", "alarms"],
        "host_permissions": ["https://example.com/*"],
        "manifest_sha256": "hash_resilience_test_v1",
        "captured_at": "2026-10-20T10:00:00Z",
    }
    db_insert_snapshot(snap)

    _MOCK_STORE["extensions"][ext_id] = ext_record
    _MOCK_STORE["snapshots"][snap["id"]] = snap

    # Clean any cached entry before each test
    db_delete_ai_overview(ext_id, "1.0.0", "hash_resilience_test_v1", PROMPT_VERSION)

    yield ext_id

    db_delete_ai_overview(ext_id, "1.0.0", "hash_resilience_test_v1", PROMPT_VERSION)
    limiter.enabled = old_limiter_enabled
    settings.GROQ_API_KEY = old_key


def test_groq_timeout_returns_200_fallback(setup_test_ext):
    """Timeout from Groq returns HTTP 200 with is_fallback=True and fallback model."""
    client = TestClient(app, base_url="http://localhost:8000")
    headers = {"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"}

    orig_post = httpx.AsyncClient.post

    async def mock_timeout_post(self, url, *args, **kwargs):
        if "groq.com" in str(url):
            raise httpx.TimeoutException("Read timed out after 25s")
        return await orig_post(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "post", new=mock_timeout_post):
        resp = client.post(
            "/api/ai-overview",
            json={"extension_id": setup_test_ext, "force_refresh": True},
            headers=headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_fallback"] is True
        assert data["model"] == "llama-3.1-8b-instant-fallback"
        assert isinstance(data["summary"], str) and len(data["summary"]) > 10


def test_groq_500_returns_200_fallback(setup_test_ext):
    """HTTP 500 error from Groq returns HTTP 200 with is_fallback=True and fallback model."""
    client = TestClient(app, base_url="http://localhost:8000")
    headers = {"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"}

    dummy_req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    orig_post = httpx.AsyncClient.post

    async def mock_500_post(self, url, *args, **kwargs):
        if "groq.com" in str(url):
            return httpx.Response(500, text="Internal Server Error", request=dummy_req)
        return await orig_post(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "post", new=mock_500_post):
        resp = client.post(
            "/api/ai-overview",
            json={"extension_id": setup_test_ext, "force_refresh": True},
            headers=headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_fallback"] is True
        assert data["model"] == "llama-3.1-8b-instant-fallback"
        assert isinstance(data["summary"], str)


def test_success_is_cached_and_second_call_skips_groq(setup_test_ext):
    """A genuine Groq success is cached; the second call does not hit Groq."""
    client = TestClient(app, base_url="http://localhost:8000")
    headers = {"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"}

    genuine_output = {
        "summary": "Genuine Groq analysis of permissions.",
        "permission_fit": "Permissions fit extension workflow.",
        "creep_detected": False,
        "creep_risks": [],
        "recommended_actions": ["Keep up to date."],
    }
    dummy_req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    groq_resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(genuine_output),
                }
            }
        ]
    }

    call_count = 0
    orig_post = httpx.AsyncClient.post

    async def mock_success_post(self, url, *args, **kwargs):
        nonlocal call_count
        if "groq.com" in str(url):
            call_count += 1
            return httpx.Response(200, json=groq_resp, request=dummy_req)
        return await orig_post(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "post", new=mock_success_post):
        # Call 1: hits Groq
        r1 = client.post(
            "/api/ai-overview",
            json={"extension_id": setup_test_ext, "force_refresh": True},
            headers=headers,
        )
        assert r1.status_code == 200
        data1 = r1.json()
        assert data1["cached"] is False
        assert data1["is_fallback"] is False
        assert data1["summary"] == genuine_output["summary"]
        assert call_count == 1

        # Call 2: served from DB cache without calling Groq
        r2 = client.post(
            "/api/ai-overview",
            json={"extension_id": setup_test_ext, "force_refresh": False},
            headers=headers,
        )
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["cached"] is True
        assert data2["is_fallback"] is False
        assert data2["summary"] == genuine_output["summary"]
        assert call_count == 1  # Still 1, didn't hit Groq!


def test_fallback_is_not_cached_under_real_key(setup_test_ext):
    """Fallback responses must NOT be written to the cache under the real key."""
    client = TestClient(app, base_url="http://localhost:8000")
    headers = {"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"}

    orig_post = httpx.AsyncClient.post

    async def mock_timeout_post(self, url, *args, **kwargs):
        if "groq.com" in str(url):
            raise httpx.TimeoutException("Read timed out")
        return await orig_post(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "post", new=mock_timeout_post):
        resp = client.post(
            "/api/ai-overview",
            json={"extension_id": setup_test_ext, "force_refresh": True},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_fallback"] is True

        # Verify DB cache table has NO entry for this manifest hash
        cached = db_get_ai_overview(setup_test_ext, "1.0.0", "hash_resilience_test_v1", PROMPT_VERSION)
        assert cached is None, "Fallback output must not be stored in cache"


def test_ten_concurrent_identical_requests_produce_one_groq_call(setup_test_ext):
    """Ten concurrent identical requests must be de-duplicated to exactly one Groq API call."""
    genuine_output = {
        "summary": "Concurrent deduplication test summary.",
        "permission_fit": "Aligned",
        "creep_detected": False,
        "creep_risks": [],
        "recommended_actions": ["No action needed."],
    }
    dummy_req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    groq_resp = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(genuine_output),
                }
            }
        ]
    }

    groq_call_count = 0
    orig_post = httpx.AsyncClient.post

    async def mock_slow_groq_post(self, url, *args, **kwargs):
        nonlocal groq_call_count
        if "groq.com" in str(url):
            groq_call_count += 1
            await asyncio.sleep(0.08)  # Simulate network latency
            return httpx.Response(200, json=groq_resp, request=dummy_req)
        return await orig_post(self, url, *args, **kwargs)

    async def run_concurrent_test():
        headers = {"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000") as c:
            tasks = [
                c.post(
                    "/api/ai-overview",
                    json={"extension_id": setup_test_ext, "force_refresh": True},
                    headers=headers,
                )
                for _ in range(10)
            ]
            responses = await asyncio.gather(*tasks)
            return responses

    with patch.object(httpx.AsyncClient, "post", new=mock_slow_groq_post):
        responses = asyncio.run(run_concurrent_test())

        assert len(responses) == 10
        for r in responses:
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
            data = r.json()
            assert data["summary"] == genuine_output["summary"]
            assert data["is_fallback"] is False

        assert groq_call_count == 1, f"Expected exactly 1 Groq call, but got {groq_call_count}"
