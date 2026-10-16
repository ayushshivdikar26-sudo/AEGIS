"""
Tests for Manifest and Icon Multipart Import Flow (tests/app/test_import_route.py).
"""

import io
import json

import pytest
from fastapi.testclient import TestClient

from Backend.app.main import app
from Backend.app.repo import reset_mock_store

client = TestClient(app, base_url="http://localhost:8000")


@pytest.fixture(autouse=True)
def clean_store():
    reset_mock_store()


def get_auth_cookies():
    resp = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "SecurePassword123!"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    return {"aegis_access_token": resp.cookies.get("aegis_access_token")}


def test_import_valid_manifest_v3():
    cookies = get_auth_cookies()
    manifest_data = {
        "manifest_version": 3,
        "name": "Password Keeper",
        "version": "1.0.0",
        "description": "Secure password manager extension.",
        "permissions": ["storage", "alarms"],
        "host_permissions": ["https://api.keeper.com/*"],
    }
    manifest_bytes = json.dumps(manifest_data).encode("utf-8")

    files = {
        "manifest": ("manifest.json", io.BytesIO(manifest_bytes), "application/json"),
    }
    data = {
        "browser": "chrome",
        "store_id": "keeper-extension-id",
    }

    resp = client.post(
        "/api/extensions/import",
        files=files,
        data=data,
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )

    assert resp.status_code == 201
    res = resp.json()
    assert res["extension"]["name"] == "Password Keeper"
    assert res["extension"]["version"] == "1.0.0"
    assert res["extension"]["risk_score"] > 0
    assert res["snapshot"]["created"] is True
    assert res["matched_existing"] is False

    ext_id = res["extension"]["id"]

    # Verify extension detail query
    detail_resp = client.get(f"/api/extensions/{ext_id}", cookies=cookies)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["name"] == "Password Keeper"

    # Verify permissions query
    perms_resp = client.get(f"/api/extensions/{ext_id}/permissions", cookies=cookies)
    assert perms_resp.status_code == 200
    assert len(perms_resp.json()["api"]) == 2
    assert len(perms_resp.json()["host"]) == 1


def test_import_idempotent_reimport_same_version():
    cookies = get_auth_cookies()
    manifest_data = {
        "manifest_version": 3,
        "name": "Sync Utility",
        "version": "1.0.0",
        "permissions": ["storage"],
    }
    manifest_bytes = json.dumps(manifest_data).encode("utf-8")

    # First import -> 201
    resp1 = client.post(
        "/api/extensions/import",
        files={"manifest": ("manifest.json", io.BytesIO(manifest_bytes), "application/json")},
        data={"browser": "chrome", "store_id": "sync-util"},
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp1.status_code == 201
    assert resp1.json()["snapshot"]["created"] is True

    # Second import with identical manifest -> 201 (or 200) with created: False
    resp2 = client.post(
        "/api/extensions/import",
        files={"manifest": ("manifest.json", io.BytesIO(manifest_bytes), "application/json")},
        data={"browser": "chrome", "store_id": "sync-util"},
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp2.status_code in (200, 201)
    assert resp2.json()["snapshot"]["created"] is False
    assert resp2.json()["matched_existing"] is True


def test_import_version_conflict_same_version_diff_manifest():
    cookies = get_auth_cookies()
    manifest_data_1 = {
        "manifest_version": 3,
        "name": "Conflict Ext",
        "version": "1.0.0",
        "permissions": ["storage"],
    }
    manifest_data_2 = {
        "manifest_version": 3,
        "name": "Conflict Ext",
        "version": "1.0.0",
        "permissions": ["storage", "history"],  # Different permissions!
    }

    # Import v1
    client.post(
        "/api/extensions/import",
        files={"manifest": ("manifest.json", io.BytesIO(json.dumps(manifest_data_1).encode()), "application/json")},
        data={"browser": "chrome", "store_id": "conflict-ext"},
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )

    # Re-import same version with different content -> 409 Conflict
    resp_conflict = client.post(
        "/api/extensions/import",
        files={"manifest": ("manifest.json", io.BytesIO(json.dumps(manifest_data_2).encode()), "application/json")},
        data={"browser": "chrome", "store_id": "conflict-ext"},
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp_conflict.status_code == 409
    assert resp_conflict.json()["error"]["code"] == "conflict"


def test_import_unresolved_placeholder_requires_display_name():
    cookies = get_auth_cookies()
    manifest_data = {
        "manifest_version": 3,
        "name": "__MSG_extension_name__",
        "version": "1.0.0",
    }
    resp = client.post(
        "/api/extensions/import",
        files={"manifest": ("manifest.json", io.BytesIO(json.dumps(manifest_data).encode()), "application/json")},
        data={"browser": "chrome"},
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "name_unresolved"

    # With display_name override -> succeeds
    resp_ok = client.post(
        "/api/extensions/import",
        files={"manifest": ("manifest.json", io.BytesIO(json.dumps(manifest_data).encode()), "application/json")},
        data={"browser": "chrome", "display_name": "Resolved Name"},
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp_ok.status_code == 201
    assert resp_ok.json()["extension"]["name"] == "Resolved Name"


def test_import_rejects_svg_icon():
    cookies = get_auth_cookies()
    manifest_data = {"manifest_version": 3, "name": "Icon Test", "version": "1.0.0"}
    svg_icon = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'/></svg>"

    resp = client.post(
        "/api/extensions/import",
        files={
            "manifest": ("manifest.json", io.BytesIO(json.dumps(manifest_data).encode()), "application/json"),
            "icon": ("icon.svg", io.BytesIO(svg_icon), "image/svg+xml"),
        },
        data={"browser": "chrome"},
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "svg_prohibited"


def test_import_accepts_valid_png_icon():
    cookies = get_auth_cookies()
    manifest_data = {"manifest_version": 3, "name": "PNG Icon Test", "version": "1.0.0"}
    # Minimal 1x1 valid PNG header
    png_icon = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"

    resp = client.post(
        "/api/extensions/import",
        files={
            "manifest": ("manifest.json", io.BytesIO(json.dumps(manifest_data).encode()), "application/json"),
            "icon": ("icon.png", io.BytesIO(png_icon), "image/png"),
        },
        data={"browser": "chrome"},
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 201
    assert resp.json()["extension"]["icon_url"] is not None
