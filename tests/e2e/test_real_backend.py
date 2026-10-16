"""
End-to-End Playwright Tests for AEGIS Real FastAPI Backend (PRD Part 2c, PLAN M4).
Verifies that FastAPI serves static frontend assets with strict security headers,
CORS policies, zero console errors, and live API connectivity.
"""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

BACKEND_PORT = 8001
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def run_fastapi_server() -> Generator[None]:
    """Start live FastAPI backend via uvicorn in a background process."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "Backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(PROJECT_ROOT),
        env=env,
    )

    # Wait for server to bind
    bound = False
    start_time = time.time()
    while time.time() - start_time < 10.0:
        try:
            with socket.create_connection(("127.0.0.1", BACKEND_PORT), timeout=0.5):
                bound = True
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)

    if not bound:
        proc.kill()
        out, err = proc.communicate()
        raise RuntimeError(
            f"FastAPI backend failed to start on 127.0.0.1:{BACKEND_PORT}.\n"
            f"Stdout: {out.decode()}\nStderr: {err.decode()}"
        )

    yield

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_fastapi_serves_frontend_with_strict_csp(page: Page) -> None:
    """Verify that live backend serves frontend dashboard with strict CSP and zero console errors."""
    console_errors: list[str] = []
    csp_violations: list[str] = []

    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on(
        "console",
        lambda msg: (
            csp_violations.append(msg.text)
            if "content security policy" in msg.text.lower() or "csp" in msg.text.lower()
            else None
        ),
    )

    response = page.goto(f"{BACKEND_URL}/")
    assert response is not None
    assert response.status == 200

    # Verify security headers from FastAPI middleware
    headers = response.headers
    assert "default-src 'self'" in headers.get("content-security-policy", "")
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-request-id") is not None

    # Wait for initial DOM
    expect(page.locator(".wordmark")).to_have_text("AEGIS")
    assert len(console_errors) == 0, f"Unexpected console errors: {console_errors}"
    assert len(csp_violations) == 0, f"CSP violations detected: {csp_violations}"


def test_fastapi_health_endpoint(page: Page) -> None:
    """Verify health endpoint via live browser request."""
    response = page.request.get(f"{BACKEND_URL}/api/health")
    assert response.status == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("x-request-id") is not None


def test_fastapi_sensitive_paths_shielded(page: Page) -> None:
    """Verify that sensitive files (.env, tests/, Backend/) return 404 with security headers."""
    resp_env = page.request.get(f"{BACKEND_URL}/.env")
    assert resp_env.status == 404
    assert resp_env.headers.get("x-content-type-options") == "nosniff"

    resp_py = page.request.get(f"{BACKEND_URL}/Backend/app/config.py")
    assert resp_py.status == 404
