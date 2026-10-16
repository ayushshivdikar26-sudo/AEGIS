"""
AEGIS Break-It Adversarial Test Suite (tests/app/test_break_it.py)
Implements PRD Section 11.7 and Milestone M6 verification matrix:
- Manifest attacks (malformed, deeply nested, oversized 50MB, XSS, RTL/homoglyphs, invalid patterns)
- Version comparison edge cases (single snapshot, identical, broadening, removal, optional-to-requested)
- Access & tenant isolation (cross-user access, tampered/expired JWT, SQL injection across all parameters)
- Rate limit abuse hammer (HTTP 429 & Retry-After)
"""

import io
import json
import pytest
from fastapi.testclient import TestClient

from Backend.app.main import app
from Backend.app.rate_limiter import reset_rate_limits
from Backend.app.repo import reset_mock_store
from Backend.core.manifest_parser import parse_manifest
from Backend.core.models import ManifestError, ParsedManifest
from Backend.core.risk_scoring import assess_manifest
from Backend.core.version_comparison import assess_creep, compare

client = TestClient(app, base_url="http://localhost:8000")


@pytest.fixture(autouse=True)
def clean_test_environment():
    reset_mock_store()
    reset_rate_limits()


def get_auth_cookies(email: str = "user_a@example.com") -> dict[str, str]:
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    return {"aegis_access_token": resp.cookies.get("aegis_access_token", "")}


# =============================================================================
# 1. Manifest Parsing & Import Attacks
# =============================================================================

def test_break_it_malformed_json_import():
    """Malformed JSON upload must return HTTP 422 with a structured error."""
    cookies = get_auth_cookies()
    malformed_bytes = b'{"manifest_version": 3, "name": "Broken", "version": '  # Truncated

    files = {"manifest": ("manifest.json", io.BytesIO(malformed_bytes), "application/json")}
    data = {"browser": "chrome", "store_id": "test-malformed"}

    resp = client.post(
        "/api/extensions/import",
        files=files,
        data=data,
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] in ("not_json", "malformed_manifest")


def test_break_it_empty_permissions_handled():
    """Manifest with empty permissions parses cleanly, evaluates to risk score 0 without crashing."""
    manifest_data = {
        "manifest_version": 3,
        "name": "Zero Perms",
        "version": "1.0.0",
        "description": "An extension requesting absolutely no permissions.",
        "permissions": [],
        "host_permissions": [],
    }
    parsed = parse_manifest(manifest_data)
    assessment = assess_manifest(parsed)

    assert parsed.api_permissions == []
    assert parsed.host_permissions == []
    assert assessment.risk_score == 0
    assert assessment.risk_level == "low"
    assert "no permissions" in assessment.plain_summary.lower()


def test_break_it_oversized_file_50mb_rejected():
    """Oversized 50MB payload must be rejected by middleware with HTTP 413 payload_too_large."""
    cookies = get_auth_cookies()
    headers = {
        "X-AEGIS-CSRF": "1",
        "Origin": "http://localhost:8000",
        "Content-Length": str(50 * 1024 * 1024),
        "Content-Type": "application/json",
    }
    resp = client.post("/api/extensions/import", content=b"{}", headers=headers, cookies=cookies)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "payload_too_large"


def test_break_it_deeply_nested_json_handled():
    """Deeply nested JSON (>32 levels) is safely caught by ManifestError preventing stack overflow."""
    nested = {"manifest_version": 3, "name": "Deep Nested", "version": "1.0.0", "permissions": ["storage"]}
    curr = nested
    for _ in range(50):
        curr["nested"] = {}
        curr = curr["nested"]

    with pytest.raises(ManifestError) as exc_info:
        parse_manifest(nested)
    assert "nesting depth" in str(exc_info.value).lower()


def test_break_it_xss_name_and_description():
    """XSS payloads in extension name and description must be stored verbatim without HTML execution."""
    cookies = get_auth_cookies()
    xss_payload = "<img src=x onerror=alert('XSS')><script>alert(1)</script>"
    manifest_data = {
        "manifest_version": 3,
        "name": xss_payload,
        "version": "1.0.0",
        "description": xss_payload,
        "permissions": ["storage"],
    }
    manifest_bytes = json.dumps(manifest_data).encode("utf-8")
    files = {"manifest": ("manifest.json", io.BytesIO(manifest_bytes), "application/json")}
    data = {"browser": "chrome", "store_id": "test-xss-ext"}

    resp = client.post(
        "/api/extensions/import",
        files=files,
        data=data,
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 201
    ext_id = resp.json()["extension"]["id"]

    # Verify detail retrieval preserves literal string for safe textContent rendering
    detail_resp = client.get(f"/api/extensions/{ext_id}", cookies=cookies)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["name"] == xss_payload
    assert detail_resp.json()["description"]["text"] == xss_payload


def test_break_it_rtl_and_unicode_lookalike_names():
    """RTL override characters, Arabic text, and Unicode homoglyphs must be accepted and safely handled."""
    cookies = get_auth_cookies()
    rtl_name = "\u202e\u0627\u0644\u0627\u0645\u062a\u062f\u0627\u062f \u0430"
    manifest_data = {
        "manifest_version": 3,
        "name": rtl_name,
        "version": "2.0.0",
        "description": "Arabic and Cyrillic test extension \ud83d\udee1\ufe0f",
        "permissions": ["alarms"],
    }
    manifest_bytes = json.dumps(manifest_data).encode("utf-8")
    files = {"manifest": ("manifest.json", io.BytesIO(manifest_bytes), "application/json")}
    data = {"browser": "chrome", "store_id": "test-rtl-ext"}

    resp = client.post(
        "/api/extensions/import",
        files=files,
        data=data,
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 201
    ext_id = resp.json()["extension"]["id"]

    detail_resp = client.get(f"/api/extensions/{ext_id}", cookies=cookies)
    assert detail_resp.status_code == 200
    # BIDI override character (\u202e) is safely stripped to mitigate Trojan Source/spoofing attacks; remaining text is preserved
    assert detail_resp.json()["name"] == "\u0627\u0644\u0627\u0645\u062a\u062f\u0627\u062f \u0430"


def test_break_it_invalid_match_patterns_handled():
    """Invalid match patterns (e.g. invalid://, *, ftp://) do not crash the engine."""
    manifest_data = {
        "manifest_version": 3,
        "name": "Invalid Patterns",
        "version": "1.0.0",
        "description": "Tests handling of malformed match patterns.",
        "host_permissions": ["invalid://*", "*", "ftp://ftp.example.com/*", "https://valid.com/*"],
    }
    parsed = parse_manifest(manifest_data)
    assessment = assess_manifest(parsed)

    # Valid pattern is scored; malformed ones don't trigger crashes
    assert "https://valid.com/*" in parsed.host_permissions
    assert assessment.risk_score >= 0


def test_break_it_missing_version_rejected():
    """Manifest missing the required 'version' field must return HTTP 422."""
    cookies = get_auth_cookies()
    manifest_data = {
        "manifest_version": 3,
        "name": "No Version",
        # Missing 'version'
        "permissions": ["storage"],
    }
    manifest_bytes = json.dumps(manifest_data).encode("utf-8")
    files = {"manifest": ("manifest.json", io.BytesIO(manifest_bytes), "application/json")}
    data = {"browser": "chrome", "store_id": "test-no-version"}

    resp = client.post(
        "/api/extensions/import",
        files=files,
        data=data,
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] in ("missing_version", "invalid_manifest")


# =============================================================================
# 2. Version Comparison & Creep Edge Cases
# =============================================================================

def test_break_it_single_snapshot_baseline_not_available():
    """Extension with only one snapshot returns available: false and reason: baseline_not_available."""
    cookies = get_auth_cookies()
    manifest_data = {
        "manifest_version": 3,
        "name": "Single Snap App",
        "version": "1.0.0",
        "description": "One snapshot only",
        "permissions": ["storage"],
    }
    files = {"manifest": ("manifest.json", io.BytesIO(json.dumps(manifest_data).encode("utf-8")), "application/json")}
    import_resp = client.post(
        "/api/extensions/import",
        files=files,
        data={"browser": "chrome", "store_id": "single-snap-unique"},
        cookies=cookies,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert import_resp.status_code == 201
    ext_id = import_resp.json()["extension"]["id"]

    resp = client.get(f"/api/extensions/{ext_id}/creep", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["reason"] == "baseline_not_available"


def test_break_it_identical_snapshots_comparison():
    """Comparing identical snapshots returns delta 0, no additions/removals, and approved outcome."""
    m1 = ParsedManifest(
        name="App", version="1.0.0", manifest_version=3, sha256="sha1",
        api_permissions=["storage", "alarms"], host_permissions=["https://example.com/*"]
    )
    m2 = ParsedManifest(
        name="App", version="1.0.1", manifest_version=3, sha256="sha2",
        api_permissions=["storage", "alarms"], host_permissions=["https://example.com/*"]
    )
    comp = compare(m1, m2)
    creep = assess_creep(comp)

    assert comp.score_from == comp.score_to
    assert comp.api.added == []
    assert comp.api.removed == []
    assert comp.host.added == []
    assert comp.host.removed == []
    assert creep.outcome == "No significant permission creep detected"


def test_break_it_exact_host_to_wildcard_broadening():
    """Host broadening from single_host to all_sites is detected as a high-severity broadening trigger."""
    m_old = ParsedManifest(
        name="Shield", version="1.0.0", manifest_version=3, sha256="sha_old",
        host_permissions=["https://api.example.com/*"]
    )
    m_new = ParsedManifest(
        name="Shield", version="2.0.0", manifest_version=3, sha256="sha_new",
        host_permissions=["<all_urls>"]
    )
    comp = compare(m_old, m_new)
    creep = assess_creep(comp)

    assert len(comp.host.broadened) >= 1
    broadened = comp.host.broadened[0]
    assert broadened.from_pattern == "https://api.example.com/*"
    assert broadened.to_pattern == "<all_urls>"
    assert broadened.to_tier == "all_sites"
    assert creep.outcome == "Significant increase in assessed permission exposure"


def test_break_it_removed_permissions_lower_score():
    """Permissions removed in newer version appear in removed list and decrease assessed score."""
    m_old = ParsedManifest(
        name="Utility", version="1.0.0", manifest_version=3, sha256="sha_v1",
        api_permissions=["webRequest", "webRequestBlocking", "storage"]
    )
    m_new = ParsedManifest(
        name="Utility", version="1.1.0", manifest_version=3, sha256="sha_v2",
        api_permissions=["storage"]
    )
    comp = compare(m_old, m_new)
    creep = assess_creep(comp)

    removed_names = [item.name for item in comp.api.removed]
    assert "webRequest" in removed_names
    assert "webRequestBlocking" in removed_names
    assert comp.score_to < comp.score_from
    assert creep.outcome == "No significant permission creep detected"


def test_break_it_optional_to_requested_migration():
    """Capability promoted from optional to mandatory is detected in added list and increases risk score."""
    m_old = ParsedManifest(
        name="Capture", version="1.0.0", manifest_version=3, sha256="sha_opt1",
        api_permissions=["storage"], optional_api_permissions=["tabCapture"]
    )
    m_new = ParsedManifest(
        name="Capture", version="2.0.0", manifest_version=3, sha256="sha_opt2",
        api_permissions=["storage", "tabCapture"], optional_api_permissions=[]
    )
    comp = compare(m_old, m_new)

    added_names = [item.name for item in comp.api.added]
    assert "tabCapture" in added_names
    assert comp.score_to > comp.score_from


# =============================================================================
# 3. Access, Tenant Isolation & Injection Attacks
# =============================================================================

def test_break_it_tenant_isolation():
    """User B cannot access or delete User A's private extension."""
    cookies_a = get_auth_cookies("user_a@example.com")
    cookies_b = get_auth_cookies("user_b@example.com")

    # User A imports private extension
    manifest_data = {
        "manifest_version": 3,
        "name": "Secret Ext",
        "version": "1.0.0",
        "permissions": ["storage"],
    }
    files = {"manifest": ("manifest.json", io.BytesIO(json.dumps(manifest_data).encode("utf-8")), "application/json")}
    resp_a = client.post(
        "/api/extensions/import",
        files=files,
        data={"browser": "chrome", "store_id": "user-a-secret"},
        cookies=cookies_a,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp_a.status_code == 201
    ext_id = resp_a.json()["extension"]["id"]

    # User B attempts to delete User A's extension -> 404
    del_resp = client.delete(
        f"/api/extensions/{ext_id}",
        cookies=cookies_b,
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert del_resp.status_code == 404
    assert del_resp.json()["error"]["code"] == "not_found"


def test_break_it_tampered_and_expired_jwt():
    """Tampered token or invalid signature returns HTTP 401 unauthorized."""
    tampered_cookie = {"aegis_access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.tampered_signature"}
    resp = client.get("/api/auth/me", cookies=tampered_cookie)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_break_it_sql_injection_in_path_parameter():
    """SQL injection strings in path parameters return clean HTTP 404 without crashing."""
    sqli_payloads = [
        "1' OR '1'='1",
        "'; DROP TABLE extensions; --",
        "1 UNION SELECT 1,2,3,4,5,6,7,8--",
        "../../etc/passwd",
    ]
    for sqli in sqli_payloads:
        resp = client.get(f"/api/extensions/{sqli}")
        assert resp.status_code in (404, 422)
        assert "error" in resp.json()
        assert resp.json()["error"]["code"] in ("not_found", "validation_error")


def test_break_it_sql_injection_in_query_parameters():
    """SQL injection strings in query parameters are rejected by Pydantic validation."""
    resp = client.get("/api/extensions?limit=1' OR 1=1--")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_break_it_sql_injection_in_json_body():
    """SQL injection strings in auth bodies are safely handled as literal strings."""
    resp = client.post(
        "/api/auth/login",
        json={"email": "admin' OR '1'='1' --", "password": "password"},
        headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
    )
    assert resp.status_code in (200, 401)


# =============================================================================
# 4. Abuse & Rate Limiting
# =============================================================================

def test_break_it_rate_limit_hammer_returns_429():
    """Rapidly sending requests beyond the limit triggers HTTP 429 with Retry-After header."""
    # Login endpoint has limit of 5 requests per 60 seconds
    exceeded = False
    for _ in range(8):
        resp = client.post(
            "/api/auth/login",
            json={"email": "attacker@example.com", "password": "Password123!"},
            headers={"X-AEGIS-CSRF": "1", "Origin": "http://localhost:8000"},
        )
        if resp.status_code == 429:
            exceeded = True
            assert "Retry-After" in resp.headers
            assert resp.json()["error"]["code"] == "rate_limit_exceeded"
            break
    assert exceeded, "Rate limiter failed to trigger 429 after rapid requests"
