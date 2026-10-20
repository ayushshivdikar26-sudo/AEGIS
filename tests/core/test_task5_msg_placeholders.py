"""
Tests for Milestone 1 Task 5:
- Placeholder resolution for name from _locales/<default_locale>/messages.json
- Placeholder resolution for description
- Fallback for description when locale data is missing (lone manifest upload)
- Fallback to catalog description if available
- Normal descriptions remain unchanged
- Guarantee that raw __MSG_...__ tokens never reach the UI, AI prompt, or exports
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from Backend.app.main import app
from Backend.app.repo import _MOCK_STORE, reset_mock_store
from Backend.app.services.ai import StructuredAIOutput
from Backend.core.manifest_parser import (
    TRANSLATED_DESC_FALLBACK,
    parse_manifest,
)


@pytest.fixture(autouse=True)
def clean_mock():
    reset_mock_store()
    yield
    reset_mock_store()


def test_name_resolved_from_messages():
    manifest = {
        "manifest_version": 3,
        "name": "__MSG_extName__",
        "version": "1.0.0",
        "default_locale": "en",
    }
    messages = {
        "_locales": {
            "en": {
                "messages": {
                    "extName": {"message": "AdBlock Pro"}
                }
            }
        }
    }
    parsed = parse_manifest(manifest, messages=messages)
    assert parsed.name == "AdBlock Pro"
    assert parsed.name_is_placeholder is False


def test_description_resolved_from_messages():
    manifest = {
        "manifest_version": 3,
        "name": "uBlock Origin",
        "version": "1.50.0",
        "description": "__MSG_extShortDesc__",
        "default_locale": "en_US",
    }
    messages = {
        "_locales": {
            "en_us": {
                "extShortDesc": {
                    "message": "Finally, an efficient blocker. Easy on CPU and memory."
                }
            }
        }
    }
    parsed = parse_manifest(manifest, messages=messages)
    assert parsed.description == "Finally, an efficient blocker. Easy on CPU and memory."
    assert parsed.description_is_placeholder is False


def test_description_missing_locale_fallback():
    # Lone manifest upload without messages.json
    manifest = {
        "manifest_version": 3,
        "name": "uBlock Origin",
        "version": "1.50.0",
        "description": "__MSG_extShortDesc__",
    }
    parsed = parse_manifest(manifest, messages=None)
    assert parsed.description == TRANSLATED_DESC_FALLBACK
    assert parsed.description_is_placeholder is True
    assert any(w.code == "unresolved_placeholder" for w in parsed.warnings)
    assert not parsed.description.startswith("__MSG_")


def test_description_catalog_fallback():
    manifest = {
        "manifest_version": 3,
        "name": "uBlock Origin",
        "version": "1.50.0",
        "description": "__MSG_extShortDesc__",
    }
    parsed = parse_manifest(
        manifest,
        messages=None,
        catalog_description="An efficient wide-spectrum content blocker.",
    )
    assert parsed.description == "An efficient wide-spectrum content blocker."
    assert not parsed.description.startswith("__MSG_")


def test_normal_description_unchanged():
    normal_desc = "This is a standard English description without any localization placeholders."
    manifest = {
        "manifest_version": 3,
        "name": "Normal Extension",
        "version": "1.0.0",
        "description": normal_desc,
    }
    parsed = parse_manifest(manifest)
    assert parsed.description == normal_desc
    assert parsed.description_is_placeholder is False
    assert not any(w.code == "unresolved_placeholder" for w in parsed.warnings)


def test_raw_msg_never_reaches_ui_ai_or_export():
    # Seed mock store with an extension having raw __MSG_ in legacy records
    ext_id = "test-ublock-raw-msg"
    _MOCK_STORE["extensions"][ext_id] = {
        "id": ext_id,
        "user_id": "00000000-0000-0000-0000-000000000001",
        "name": "uBlock Origin",
        "browser": "chrome",
        "store_id": "ublock-origin",
        "is_public": True,
        "icon_path": None,
    }
    _MOCK_STORE["snapshots"]["snap-ublock"] = {
        "id": "snap-ublock",
        "extension_id": ext_id,
        "user_id": "00000000-0000-0000-0000-000000000001",
        "version": "1.50.0",
        "name": "uBlock Origin",
        "description": "__MSG_extShortDesc__",
        "captured_at": "2026-10-15T12:00:00Z",
        "manifest_version": 3,
        "api_permissions": ["storage"],
        "host_permissions": [],
        "manifest": {},
        "manifest_sha256": "3" * 64,
    }

    client = TestClient(app, base_url="http://localhost:8000")

    # 1. UI Detail Endpoint: GET /api/extensions/{id}
    detail_res = client.get(f"/api/extensions/{ext_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert "__MSG_" not in detail["description"]["text"]
    assert detail["description"]["text"] == TRANSLATED_DESC_FALLBACK

    # 2. AI Overview Endpoint: POST /api/ai-overview
    with patch("Backend.app.routers.ai.call_groq_api", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = (
            StructuredAIOutput(
                summary="Safe ad blocker",
                permission_fit="Tight and justified",
                creep_detected=False,
                creep_risks=[],
                recommended_actions=["No action needed"],
            ),
            "llama-3.3-70b-versatile",
        )
        ai_res = client.post(
            "/api/ai-overview",
            json={"extension_id": ext_id, "version": "1.50.0"},
            headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
        )
        assert ai_res.status_code == 200
        # Verify the description sent to Groq never had __MSG_
        mock_groq_kwargs = mock_groq.call_args.kwargs
        assert "__MSG_" not in mock_groq_kwargs.get("description", "")
        assert mock_groq_kwargs.get("description") == TRANSLATED_DESC_FALLBACK

    # 3. History Export Endpoint: GET /api/history/export
    export_res = client.get("/api/history/export")
    assert export_res.status_code == 200
    export_json_str = json.dumps(export_res.json())
    assert "__MSG_" not in export_json_str
