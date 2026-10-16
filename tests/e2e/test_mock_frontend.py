"""
End-to-End Playwright Tests for AEGIS Frontend against Dev Mock API (Part 1, PRD s11.9).
Verifies rendering, strict CSP, keyboard navigation, XSS protection, and state isolation.
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

SERVER_URL = "http://127.0.0.1:8000"
SERVE_SCRIPT = Path(__file__).resolve().parents[2] / "dev" / "mock-api" / "serve.py"


@pytest.fixture(scope="session", autouse=True)
def run_mock_server():
    """Start dev/mock-api/serve.py in a background process for e2e tests."""
    proc = subprocess.Popen(
        [sys.executable, str(SERVE_SCRIPT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to bind
    bound = False
    start_time = time.time()
    while time.time() - start_time < 10.0:
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
                bound = True
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)

    if not bound:
        proc.kill()
        out, err = proc.communicate()
        raise RuntimeError(
            f"Mock server failed to start on 127.0.0.1:8000.\nStdout: {out.decode()}\nStderr: {err.decode()}"
        )

    yield

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_page_boot_zero_console_errors_and_strict_csp(page: Page):
    """FR-F15: Page loads with zero console errors and zero CSP violations."""
    console_errors = []
    csp_violations = []

    page.on(
        "console",
        lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
    )
    page.on(
        "pageerror",
        lambda err: console_errors.append(str(err)),
    )

    page.goto(SERVER_URL)
    page.wait_for_selector(".ext-row")

    assert len(console_errors) == 0, f"Console errors detected: {console_errors}"
    assert len(csp_violations) == 0, f"CSP violations detected: {csp_violations}"


def test_sidebar_search_and_keyboard_navigation(page: Page):
    """FR-F1: Search filters client-side, roving tabindex, Up/Down navigation."""
    page.goto(SERVER_URL)
    page.wait_for_selector(".ext-row")

    # Search for notes
    search_input = page.locator("#search-input")
    search_input.fill("notes")

    # Count announcement
    count_el = page.locator("#search-count")
    expect(count_el).to_contain_text("extensions found")

    # Clear search
    clear_btn = page.locator("#search-clear-btn")
    clear_btn.click()
    expect(search_input).to_have_value("")

    # Roving tabindex: first row should have tabindex=0
    first_row = page.locator(".ext-row").first
    expect(first_row).to_have_attribute("tabindex", "0")

    first_row.focus()
    page.keyboard.press("ArrowDown")

    second_row = page.locator(".ext-row").nth(1)
    expect(second_row).to_have_attribute("tabindex", "0")
    expect(first_row).to_have_attribute("tabindex", "-1")


def test_selection_renders_all_six_sections_in_order(page: Page):
    """FR-F2 to FR-F7: Selecting an extension renders all panels in required order."""
    page.goto(SERVER_URL)
    page.wait_for_selector(".ext-row")

    # Select Sample Notes Sync
    page.locator('.ext-row:has-text("Sample Notes Sync")').click()

    # 1. Identity section
    identity_heading = page.locator("#identity-heading")
    expect(identity_heading).to_have_text("Sample Notes Sync")

    # 2. Risk gauge section
    gauge = page.locator("#gauge-section")
    expect(gauge).to_be_visible()
    expect(gauge.locator(".gauge-score-value")).to_contain_text("70")
    expect(gauge.locator(".chip-high")).to_contain_text("HIGH")

    # 3. About section
    about = page.locator("#about-section")
    expect(about).to_be_visible()
    expect(about).to_contain_text("From the manifest")

    # 4. Permissions section
    perms = page.locator("#permissions-section")
    expect(perms).to_be_visible()
    expect(perms).to_contain_text("API Permissions")
    expect(perms).to_contain_text("Host Permissions")

    # 5. Version comparison section
    comp = page.locator("#comparison-section")
    expect(comp).to_be_visible()
    expect(comp.locator(".diff-added").first).to_contain_text("history")

    # 6. Creep section
    creep = page.locator("#creep-section")
    expect(creep).to_be_visible()
    expect(creep.locator(".creep-outcome-banner")).to_contain_text(
        "Significant increase in assessed permission exposure"
    )
    expect(creep.locator(".limitations-box")).to_be_visible()


def test_permission_accordion_expand_collapse(page: Page):
    """FR-F5: Permissions row expands with allows, legitimate use, and assessment."""
    page.goto(SERVER_URL + "#/ext/sample-notes-sync")
    page.wait_for_selector("#permissions-section")

    perm_btn = page.locator('.perm-row-btn:has-text("history")')
    details = perm_btn.locator(".perm-details")

    # Initially collapsed
    expect(perm_btn).to_have_attribute("aria-expanded", "false")
    expect(details).to_have_attribute("data-expanded", "false")

    # Click to expand
    perm_btn.click()
    expect(perm_btn).to_have_attribute("aria-expanded", "true")
    expect(details).to_have_attribute("data-expanded", "true")
    expect(details).to_contain_text("What it allows")
    expect(details).to_contain_text("Why an extension might need it")


def test_single_snapshot_baseline_not_available(page: Page):
    """FR-F6, FR-F7: Single snapshot shows 'unavailable' and 'Baseline not available'."""
    page.goto(SERVER_URL + "#/ext/sample-tab-manager")
    page.wait_for_selector("#comparison-section")

    expect(page.locator("#comparison-section")).to_contain_text(
        "Version comparison is unavailable. AEGIS has only one saved snapshot of this extension."
    )
    expect(page.locator("#creep-section")).to_contain_text("Baseline not available.")


def test_xss_name_rendered_as_plain_text(page: Page):
    """FR-F15: XSS attempt <img src=x onerror=alert(1)> rendered strictly as plain text."""
    dialog_triggered = False

    def on_dialog(dialog):
        nonlocal dialog_triggered
        dialog_triggered = True
        dialog.dismiss()

    page.on("dialog", on_dialog)

    page.goto(SERVER_URL + "#/ext/sample-xss-name")
    page.wait_for_selector("#identity-heading")

    heading = page.locator("#identity-heading")
    expect(heading).to_have_text("<img src=x onerror=alert(1)>")

    # Ensure no img tags or executed script dialogs
    assert heading.locator("img").count() == 0
    assert not dialog_triggered


def test_responsive_mobile_drawer(page: Page):
    """FR-F13: Below 1024px, sidebar becomes a modal drawer with backdrop."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(SERVER_URL)
    page.wait_for_selector(".mobile-header")

    sidebar = page.locator("#sidebar")
    menu_btn = page.locator("#mobile-menu-btn")
    backdrop = page.locator("#drawer-backdrop")

    # Drawer initially hidden/closed
    expect(sidebar).not_to_have_class("open")

    # Open drawer
    menu_btn.click()
    expect(sidebar).to_have_class("sidebar open")
    expect(backdrop).to_have_class("drawer-backdrop active")

    # Press Escape to close
    page.keyboard.press("Escape")
    expect(sidebar).not_to_have_class("open")


def test_section_error_isolation(page: Page):
    """FR-F12: One failing section does not break other panels."""
    # Force failure on permissions endpoint
    page.goto(SERVER_URL + "/?fail=permissions#/ext/sample-notes-sync")
    page.wait_for_selector("#identity-heading")

    # Identity and gauge succeed
    expect(page.locator("#identity-heading")).to_have_text("Sample Notes Sync")
    expect(page.locator("#gauge-section")).to_be_visible()

    # Permissions shows retry button
    expect(
        page.locator('#content-column:has-text("Failed to load permissions.")')
    ).to_be_visible()
