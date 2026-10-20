"""
Tests for Milestone 1 Task 4:
Regression checks on manifest import:
- Upload v1_narrow_manifest.json (status 201, score 20)
- Upload v2_expanded_manifest.json (status 201, score 75)
- Version comparison confirms 20 -> 75 expansion, added APIs (history, cookies), and host broadening
- Paste JSON manually (status 201)
- Re-import identical manifest (status 200, snapshot deduplication, never 500)
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Backend.app.main import app
from Backend.app.repo import Repository, reset_mock_store

DEMO_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "demo"


@pytest.fixture(autouse=True)
def clean_fixtures():
    reset_mock_store()
    try:
        from Backend.app.admin import get_admin_client
        client = get_admin_client()
        if client:
            client.table("extensions").delete().eq("name", "QuickNote Clipper (Synthetic Demo)").execute()
            client.table("extensions").delete().eq("name", "Regression Manual Pasted Ext").execute()
    except Exception:
        pass
    yield
    try:
        from Backend.app.admin import get_admin_client
        client = get_admin_client()
        if client:
            client.table("extensions").delete().eq("name", "QuickNote Clipper (Synthetic Demo)").execute()
            client.table("extensions").delete().eq("name", "Regression Manual Pasted Ext").execute()
    except Exception:
        pass


def test_import_regression_v1_v2_compare_and_paste():
    client = TestClient(app, base_url="http://localhost:8000")

    v1_path = DEMO_DIR / "v1_narrow_manifest.json"
    v2_path = DEMO_DIR / "v2_expanded_manifest.json"
    assert v1_path.exists()
    assert v2_path.exists()

    v1_bytes = v1_path.read_bytes()
    v2_bytes = v2_path.read_bytes()

    # 1. Upload v1_narrow_manifest.json
    r1 = client.post(
        "/api/extensions/import",
        files={"manifest": ("v1_narrow_manifest.json", v1_bytes, "application/json")},
        data={"browser": "chrome"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert r1.status_code == 201, f"Expected 201, got {r1.status_code}: {r1.text}"
    data1 = r1.json()
    ext_id = data1["extension"]["id"]
    assert data1["extension"]["name"] == "QuickNote Clipper (Synthetic Demo)"
    assert data1["extension"]["risk_score"] == 20
    assert data1["extension"]["risk_level"] == "low"
    assert data1["snapshot"]["created"] is True

    # 2. Upload v2_expanded_manifest.json
    r2 = client.post(
        "/api/extensions/import",
        files={"manifest": ("v2_expanded_manifest.json", v2_bytes, "application/json")},
        data={"browser": "chrome"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert r2.status_code == 201, f"Expected 201, got {r2.status_code}: {r2.text}"
    data2 = r2.json()
    assert data2["matched_existing"] is True
    assert data2["extension"]["id"] == ext_id
    assert data2["extension"]["version"] == "1.1.0"
    assert data2["extension"]["risk_score"] == 75
    assert data2["extension"]["risk_level"] == "high"

    # 3. Confirm version comparison shows 20 -> 75 expansion
    r_comp = client.get(f"/api/extensions/{ext_id}/compare?from=1.0.0&to=1.1.0")
    assert r_comp.status_code == 200
    comp = r_comp.json()
    assert comp["score_from"] == 20
    assert comp["score_to"] == 75

    added_api = [item["name"] for item in comp["api"]["added"]]
    assert "history" in added_api
    assert "cookies" in added_api

    broadened = comp["host"]["broadened"]
    assert len(broadened) >= 1
    assert broadened[0]["from_pattern"] == "https://api.quicknote.example/*"
    assert broadened[0]["to_pattern"] == "*://*/*"

    # 4. Paste JSON manually
    pasted_json = {
        "manifest_version": 3,
        "name": "Regression Manual Pasted Ext",
        "version": "1.0.0",
        "description": "Pasted JSON test for regression suite",
        "permissions": ["alarms"],
    }
    r3 = client.post(
        "/api/extensions/import",
        files={"manifest": ("manifest.json", json.dumps(pasted_json).encode("utf-8"), "application/json")},
        data={"browser": "chrome"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert r3.status_code == 201, f"Expected 201, got {r3.status_code}: {r3.text}"
    assert r3.json()["extension"]["name"] == "Regression Manual Pasted Ext"

    # 5. Re-import identical manifest (must succeed with 200, created=False, never 500)
    r4 = client.post(
        "/api/extensions/import",
        files={"manifest": ("v1_narrow_manifest.json", v1_bytes, "application/json")},
        data={"browser": "chrome"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert r4.status_code == 200, f"Expected 200 on duplicate, got {r4.status_code}: {r4.text}"
    assert r4.json()["snapshot"]["created"] is False
