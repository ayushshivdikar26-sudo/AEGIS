"""
AEGIS Milestone 2 Verification Script (tools/verify_milestone2.py)
Automated verification for Part D acceptance checklist using Playwright.
"""

import os
import sys
import json
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
OUT_DIR = "verification_screenshots"
os.makedirs(OUT_DIR, exist_ok=True)

def run_verification():
    results = {}
    console_errors = []
    network_requests = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # -------------------------------------------------------------
        # 1. 1920x1080 Verification
        # -------------------------------------------------------------
        print("\n--- Testing 1920x1080 Viewport ---")
        context_1080 = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context_1080.new_page()

        # Listen to console messages and network requests
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)
        page.on("request", lambda req: network_requests.append(req.url))

        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_timeout(2800) # Wait for hero logo convergence animation (1.2s delay + 1.4s fly-in)

        # Check network requests: Verify /api/extensions requested before scroll
        ext_requested = any("/api/extensions" in url for url in network_requests)
        results["preload_api_extensions_at_0pct"] = ext_requested
        print(f"Preload /api/extensions requested at 0% scroll: {ext_requested}")

        # Screenshot 1: Hero at 0% scroll
        page.screenshot(path=f"{OUT_DIR}/hero_1080p_0pct.png")
        print("Captured: hero_1080p_0pct.png")

        # Scroll to 30% of hero track (track is 180vh = 1944px, hero scrollable range is 80vh = 864px)
        hero_track_h = page.evaluate("() => document.getElementById('hero-track').offsetHeight - window.innerHeight")
        
        # 30% scroll
        page.evaluate(f"window.scrollTo(0, {hero_track_h * 0.3})")
        page.wait_for_timeout(200)
        page.screenshot(path=f"{OUT_DIR}/hero_1080p_30pct.png")
        print("Captured: hero_1080p_30pct.png")

        # 60% scroll
        page.evaluate(f"window.scrollTo(0, {hero_track_h * 0.6})")
        page.wait_for_timeout(200)
        page.screenshot(path=f"{OUT_DIR}/hero_1080p_60pct.png")
        print("Captured: hero_1080p_60pct.png")

        # 100% scroll (dashboard in full view)
        page.evaluate(f"window.scrollTo(0, {hero_track_h})")
        page.wait_for_timeout(800)
        page.screenshot(path=f"{OUT_DIR}/dashboard_1080p_100pct.png")
        print("Captured: dashboard_1080p_100pct.png")

        # Scroll right pane to Permissions (Row 4)
        perms_section = page.locator("#permissions-section")
        if perms_section.count() > 0:
            perms_section.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            page.screenshot(path=f"{OUT_DIR}/dashboard_1080p_permissions.png")
            print("Captured: dashboard_1080p_permissions.png")

        # Scroll right pane to Versions + Creep (Row 5)
        creep_section = page.locator("#creep-section")
        if creep_section.count() > 0:
            creep_section.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            page.screenshot(path=f"{OUT_DIR}/dashboard_1080p_versions_creep.png")
            print("Captured: dashboard_1080p_versions_creep.png")

        context_1080.close()

        # -------------------------------------------------------------
        # 2. 1366x768 Verification (Common Laptop)
        # -------------------------------------------------------------
        print("\n--- Testing 1366x768 Viewport ---")
        context_laptop = browser.new_context(viewport={"width": 1366, "height": 768})
        page_laptop = context_laptop.new_page()
        page_laptop.goto(BASE_URL, wait_until="networkidle")
        page_laptop.wait_for_timeout(2800)

        page_laptop.screenshot(path=f"{OUT_DIR}/hero_1366x768_0pct.png")
        print("Captured: hero_1366x768_0pct.png")

        # Scroll to dashboard
        laptop_hero_track_h = page_laptop.evaluate("() => document.getElementById('hero-track').offsetHeight - window.innerHeight")
        page_laptop.evaluate(f"window.scrollTo(0, {laptop_hero_track_h})")
        page_laptop.wait_for_timeout(800)
        page_laptop.screenshot(path=f"{OUT_DIR}/dashboard_1366x768.png")
        print("Captured: dashboard_1366x768.png")

        context_laptop.close()

        # -------------------------------------------------------------
        # 3. 390x844 Verification (Mobile iPhone 14/15 size)
        # -------------------------------------------------------------
        print("\n--- Testing 390x844 Mobile Viewport ---")
        context_mobile = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
        page_mobile = context_mobile.new_page()
        page_mobile.goto(BASE_URL, wait_until="networkidle")
        page_mobile.wait_for_timeout(2800)

        # Hero view
        page_mobile.screenshot(path=f"{OUT_DIR}/hero_mobile_390x844.png")
        print("Captured: hero_mobile_390x844.png")

        # Scroll to dashboard
        mobile_hero_h = page_mobile.evaluate("() => document.getElementById('hero-track').offsetHeight - window.innerHeight")
        page_mobile.evaluate(f"window.scrollTo(0, {mobile_hero_h})")
        page_mobile.wait_for_timeout(800)

        # Open drawer
        menu_btn = page_mobile.locator("#mobile-menu-btn")
        if menu_btn.is_visible():
            menu_btn.click()
            page_mobile.wait_for_timeout(400)
            page_mobile.screenshot(path=f"{OUT_DIR}/sidebar_mobile_drawer.png")
            print("Captured: sidebar_mobile_drawer.png")

            # Close drawer
            page_mobile.keyboard.press("Escape")
            page_mobile.wait_for_timeout(400)

        # Dashboard stacked view
        page_mobile.screenshot(path=f"{OUT_DIR}/dashboard_mobile_stacked.png")
        print("Captured: dashboard_mobile_stacked.png")

        context_mobile.close()

        # -------------------------------------------------------------
        # 4. Reduced-Motion Mode Verification
        # -------------------------------------------------------------
        print("\n--- Testing Reduced-Motion Mode ---")
        context_reduced = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            reduced_motion="reduce"
        )
        page_reduced = context_reduced.new_page()
        page_reduced.goto(BASE_URL, wait_until="networkidle")
        page_reduced.wait_for_timeout(500)

        # Verify static lockup image is displayed instead of canvas
        static_visible = page_reduced.locator(".hero-logo-static").is_visible()
        canvas_visible = page_reduced.locator("#hero-logo").is_visible()
        results["reduced_motion_static_logo"] = static_visible and not canvas_visible
        print(f"Reduced motion static logo visible: {static_visible}, canvas visible: {canvas_visible}")

        page_reduced.screenshot(path=f"{OUT_DIR}/hero_reduced_motion.png")
        print("Captured: hero_reduced_motion.png")

        context_reduced.close()

        # -------------------------------------------------------------
        # 5. Resilience: WebGL Fallback Simulation
        # -------------------------------------------------------------
        print("\n--- Testing WebGL Fallback ---")
        context_fallback = browser.new_context(viewport={"width": 1920, "height": 1080})
        # Inject script to simulate WebGL failure
        context_fallback.add_init_script("""
            const origGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, ...args) {
                if (type && type.includes('webgl')) {
                    return null;
                }
                return origGetContext.apply(this, [type, ...args]);
            };
        """)
        page_fallback = context_fallback.new_page()
        fallback_errors = []
        page_fallback.on("console", lambda msg: fallback_errors.append(msg.text) if msg.type == "error" else None)

        page_fallback.goto(BASE_URL, wait_until="networkidle")
        page_fallback.wait_for_timeout(2800)

        # Check if SVG fallback or fallback canvas rendered without throwing uncaught errors
        has_threads = page_fallback.locator("#hero-threads").count() > 0
        has_logo = page_fallback.locator("#hero-logo").is_visible() or page_fallback.locator(".hero-logo-static").is_visible()
        results["webgl_fallback_resilient"] = has_threads and has_logo and (len(fallback_errors) == 0)
        print(f"WebGL fallback resilient: {results['webgl_fallback_resilient']}, errors: {fallback_errors}")

        page_fallback.screenshot(path=f"{OUT_DIR}/hero_webgl_fallback.png")
        print("Captured: hero_webgl_fallback.png")

        context_fallback.close()

        # -------------------------------------------------------------
        # 6. Accessibility: Keyboard Navigation & Screen Reader Labels
        # -------------------------------------------------------------
        print("\n--- Testing Accessibility ---")
        context_a11y = browser.new_context(viewport={"width": 1920, "height": 1080})
        page_a11y = context_a11y.new_page()
        page_a11y.goto(BASE_URL, wait_until="networkidle")
        page_a11y.wait_for_timeout(1000)

        # Check Wordmark screen reader accessibility
        wordmark_aria = page_a11y.locator(".sidebar-brand .aegis-wordmark").first.get_attribute("aria-label")
        results["wordmark_aria_label"] = wordmark_aria
        print(f"Sidebar wordmark aria-label: '{wordmark_aria}'")

        # Tab navigation test
        focused_tags = []
        for _ in range(8):
            page_a11y.keyboard.press("Tab")
            focused_id = page_a11y.evaluate("() => document.activeElement ? (document.activeElement.id || document.activeElement.className || document.activeElement.tagName) : null")
            focused_tags.append(focused_id)

        results["tab_sequence_sample"] = focused_tags
        print(f"Tab focus sequence: {focused_tags}")

        context_a11y.close()
        browser.close()

    print("\n--- Console Errors in Standard Operation ---")
    print(f"Total error/warn messages: {len(console_errors)}")
    for err in console_errors:
        print("  ", err)

    results["console_errors_count"] = len(console_errors)
    return results

if __name__ == "__main__":
    res = run_verification()
    print("\nVerification Results Summary:")
    print(json.dumps(res, indent=2))
