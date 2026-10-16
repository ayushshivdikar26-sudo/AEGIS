"""
Tests for Static File Serving, Sensitive File Shielding, and Headers (tests/app/test_static_mount.py).
"""

from fastapi.testclient import TestClient

from Backend.app.main import app

client = TestClient(app, base_url="http://localhost:8000")


def test_serve_dashboard_html_at_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "AEGIS" in resp.text
    assert resp.headers.get("Content-Type", "").startswith("text/html")
    assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")


def test_serve_css_and_js_assets():
    css_resp = client.get("/css/tokens.css")
    assert css_resp.status_code == 200
    assert "--bg" in css_resp.text

    js_resp = client.get("/js/main.js")
    assert js_resp.status_code == 200
    assert "selectExtension" in js_resp.text


def test_sensitive_files_shielded_return_404():
    """Verify that source code, migrations, tests, and environment files are blocked from static serving."""
    blocked_paths = [
        "/.env",
        "/.git/config",
        "/Backend/app/main.py",
        "/scripts/gen_rules_doc.py",
        "/supabase/migrations/0001_initial_schema.sql",
        "/tests/core/test_risk_scoring.py",
        "/PRD/AEGIS_PRD.md",
    ]
    for path in blocked_paths:
        resp = client.get(path)
        assert resp.status_code == 404, f"Path {path} should return 404 but returned {resp.status_code}"


def test_security_headers_present_on_404():
    resp = client.get("/non-existent-static-file.xyz")
    assert resp.status_code == 404
    assert resp.headers.get("X-Request-ID") is not None
    assert "nosniff" in resp.headers.get("X-Content-Type-Options", "")
    assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")
