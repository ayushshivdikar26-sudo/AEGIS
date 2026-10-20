"""
End-to-End Playwright Verification for Milestone 2: AI Overview Feature.
Starts FastAPI on port 8002, tests loading skeleton, live Groq output,
actions list, disclaimer, and screenshot capture.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 8002
BASE_URL = f"http://127.0.0.1:{PORT}"
ROOT_DIR = Path(__file__).resolve().parents[2]
ARTIFACT_IMG = Path("C:/Users/Ayush/.gemini/antigravity/brain/9d46e272-04dc-44ad-a9a4-fa2f75a69ecb/ai_overview_live.png")


def run_e2e_verification():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)

    print(f"Starting server on {BASE_URL}...")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "Backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for port to open
        bound = False
        start = time.time()
        while time.time() - start < 10.0:
            try:
                with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
                    bound = True
                    break
            except (OSError, ConnectionRefusedError):
                time.sleep(0.1)

        if not bound:
            raise RuntimeError("FastAPI server failed to bind on port 8002.")

        print("Server is bound. Launching Playwright Chromium...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 900})

            # Track console errors
            errors = []
            page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)

            # Navigate to MyLOFT extension
            target_ext = "edge-fpipfdkmjmeppohgfomgkaniobddgjjc"
            print(f"Navigating to {BASE_URL}/#/ext/{target_ext} ...")
            page.goto(f"{BASE_URL}/#/ext/{target_ext}")

            # 1. Verify extension identity renders
            page.wait_for_selector("#identity-heading", timeout=10000)
            title = page.locator("#identity-heading").inner_text()
            print(f"Extension identity loaded: {title}")

            # 2. Verify AI section exists
            page.wait_for_selector("#ai-overview-section", timeout=15000)
            print("AI overview container found.")

            # 3. Wait for AI content to replace loading skeleton (max 15s for Groq response)
            page.wait_for_selector(".ai-summary-text", timeout=20000)
            summary = page.locator(".ai-summary-text").inner_text()
            print(f"AI Summary rendered: {summary[:80]}...")

            fit = page.locator(".ai-fit-text").inner_text()
            print(f"Permission Fit rendered: {fit[:80]}...")

            actions = page.locator(".ai-action-item").all_inner_texts()
            print(f"Recommended actions count: {len(actions)}")
            assert len(actions) > 0, "No recommended actions rendered!"

            disclaimer = page.locator(".ai-disclaimer").first.inner_text()
            print(f"Disclaimer: {disclaimer}")
            assert "AEGIS does not inspect extension code" in disclaimer, "Disclaimer missing or incorrect!"

            # 4. Check regenerate button
            regen_btn = page.locator(".ai-regen-btn")
            assert regen_btn.is_visible(), "Regenerate button not visible!"
            print("Regenerate button is visible.")

            # 5. Capture screenshot of the AI Overview card specifically
            ARTIFACT_IMG.parent.mkdir(parents=True, exist_ok=True)
            ai_card = page.locator("#ai-overview-section")
            ai_card.scroll_into_view_if_needed()
            ai_card.screenshot(path=str(ARTIFACT_IMG))
            print(f"Screenshot of AI card saved successfully to {ARTIFACT_IMG}")

            browser.close()

        print("PLAYWRIGHT VERIFICATION SUCCEEDED!")

    finally:
        print("Stopping uvicorn server...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    run_e2e_verification()
