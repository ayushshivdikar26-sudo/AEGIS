"""
Verification tests for the AEGIS 48-Hour Demo Readiness synthetic fixtures (tests/app/test_demo_fixtures.py).
Verifies the end-to-end golden path:
1. Version 1 imported with narrow permissions.
2. Version 2 imported with expanded host access and added API permissions.
3. Snapshots linked chronologically.
4. Core engine calculates risk score and detects host broadening.
5. Permission creep assessment explains reasons for review.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Backend.app.main import app
from Backend.app.repo import reset_mock_store

DEMO_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "demo"


@pytest.fixture(autouse=True)
def clean_store():
    def _cleanup():
        reset_mock_store()
        try:
            from Backend.app.admin import get_admin_client
            client = get_admin_client()
            if client:
                client.table("extensions").delete().eq("store_id", "quicknote-clipper").execute()
        except Exception:
            pass

    _cleanup()
    yield
    _cleanup()


def test_demo_fixture_golden_path():
    client = TestClient(app, base_url="http://localhost:8000")

    # Read synthetic demo manifests
    v1_path = DEMO_DIR / "v1_narrow_manifest.json"
    v2_path = DEMO_DIR / "v2_expanded_manifest.json"

    assert v1_path.exists(), "v1_narrow_manifest.json must exist"
    assert v2_path.exists(), "v2_expanded_manifest.json must exist"

    v1_bytes = v1_path.read_bytes()
    v2_bytes = v2_path.read_bytes()

    # Step 1: Import v1 (Narrow permissions)
    r1 = client.post(
        "/api/extensions/import",
        files={"manifest": ("manifest.json", v1_bytes, "application/json")},
        data={"browser": "chrome", "store_id": "quicknote-clipper"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert r1.status_code == 201
    res1 = r1.json()
    ext_id = res1["extension"]["id"]
    assert res1["extension"]["name"] == "QuickNote Clipper (Synthetic Demo)"
    assert res1["extension"]["risk_level"] == "low"
    assert res1["extension"]["risk_score"] < 35

    # Step 2: Import v2 (Expanded permissions)
    r2 = client.post(
        "/api/extensions/import",
        files={"manifest": ("manifest.json", v2_bytes, "application/json")},
        data={"browser": "chrome", "store_id": "quicknote-clipper"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert r2.status_code == 201
    res2 = r2.json()
    assert res2["matched_existing"] is True
    assert res2["extension"]["id"] == ext_id
    assert res2["extension"]["version"] == "1.1.0"
    assert res2["extension"]["risk_level"] == "high"
    assert res2["extension"]["risk_score"] >= 70

    # Step 3: Check chronological versions
    v_resp = client.get(f"/api/extensions/{ext_id}/versions")
    assert v_resp.status_code == 200
    versions = [v["version"] for v in v_resp.json()["versions"]]
    assert versions == ["1.1.0", "1.0.0"]

    # Step 4: Verify version comparison
    c_resp = client.get(f"/api/extensions/{ext_id}/compare?from=1.0.0&to=1.1.0")
    assert c_resp.status_code == 200
    comp = c_resp.json()

    # Added API permissions: cookies, history
    added_api = [item["name"] for item in comp["api"]["added"]]
    assert "history" in added_api
    assert "cookies" in added_api

    # Broadened host access: single_host -> all_sites
    assert len(comp["host"]["broadened"]) >= 1
    broadened_entry = comp["host"]["broadened"][0]
    assert broadened_entry["from_pattern"] == "https://api.quicknote.example/*"
    assert broadened_entry["to_pattern"] == "*://*/*"
    assert broadened_entry["from_tier"] == "single_host"
    assert broadened_entry["to_tier"] == "all_sites"

    # Step 5: Verify creep assessment
    cr_resp = client.get(f"/api/extensions/{ext_id}/creep")
    assert cr_resp.status_code == 200
    creep = cr_resp.json()
    assert creep["available"] is True
    assert creep["outcome"] == "Significant increase in assessed permission exposure"
    assert creep["score_to"] > creep["score_from"]
    assert "limitations" in creep and len(creep["limitations"]) > 0
