# AEGIS — Project Handover & System Status Document
**Generated**: October 20, 2026  
**Repository Branch**: `master` (up to date with `origin/master`)  
**Commit Reference**: `9138425` (PR #1 `sprint/demo-readiness` merged)

---

## 1. Project Overview & Architecture

AEGIS is a browser extension security and permission-creep intelligence platform. It audits WebExtension manifests, computes permission risk scores (0–100), visualizes host permission scope, tracks version-over-version permission expansions, and provides AI-powered security summaries.

### Architecture Topology
* **Frontend**: Vanilla ES6 modules, CSS tokens, canvas animation (`threads.js`), accessible DOM rendering (no heavyweight JS framework).
* **Backend**: FastAPI (Python 3.13), Uvicorn ASGI server, Pydantic v2 schemas.
* **Database Strategy (Hybrid Model)**:
  * **Supabase (Cloud PostgreSQL + RLS)**: Primary production store for user-scoped extensions, snapshots, permissions, and creep records.
  * **Local SQLite (`Backend/data/aegis.db`)**: Local offline cache used primarily for persistent AI overview results (`ai_overviews` table) and local fallback when Supabase is unconfigured.
  * **In-Memory Store (`_MOCK_STORE`)**: Ephemeral dev/test store populated from `dev/mock-api/fixtures/dataset.json`.

---

## 2. Recent Updates & Fixes (Session Log)

### A. Merged Pull Request #1 (`sprint/demo-readiness`)
* **Interactive Manifest Import Modal**: Direct `.json` upload and paste capability in the sidebar with target browser selection and Store ID tracking.
* **Preflight Validation**: Client-side instant schema checks in `Frontend/js/lib/validate_manifest.js` (8 passing unit tests).
* **Non-Technical UX Enhancements**:
  * "How to Read AEGIS" drawer (`Frontend/js/render/guide.js`).
  * Plain-language version diff explanations and risk badges (`Frontend/js/render/versions.js`).
  * "Sample" badging for catalog/demo extensions vs. live installed extensions.
* **Demo Fixtures**: Versioned demo manifests (`fixtures/demo/v1_narrow_manifest.json` and `v2_expanded_manifest.json`) with end-to-end golden path verification.
* **Server Performance**: Decoupled `browser_scanner` from web-server startup path in `Backend/app/repo.py`.

### B. Resolved Manifest Import 500 Error
* **Problem**: Uploading a manifest in unauthenticated dev mode triggered HTTP 500 (`Key (user_id)=(00000000-0000-0000-0000-000000000001) is not present in table "users"` and `PGRST204: Could not find 'source' column`).
* **Fix Applied**:
  1. Provisioned the system demo user `00000000-0000-0000-0000-000000000001` in Supabase Auth.
  2. Filtered out the non-existent `source` column in `Backend/app/repo.py` (`insert_snapshot`) before sending records to Supabase.
  3. Verified golden path test `tests/app/test_demo_fixtures.py` passes 100%.

---

## 3. Current Issues & Identified Solutions

### Issue 1: SQLite Foreign Key Failure on `POST /api/ai-overview` (HTTP 500)
* **Symptom**: When clicking extensions, the AI overview card crashes with `sqlite3.IntegrityError: FOREIGN KEY constraint failed`.
* **Root Cause**: In `Backend/app/db.py`, the `ai_overviews` table enforces `FOREIGN KEY (extension_id) REFERENCES extensions(id)`. When running against Supabase, extensions have Supabase UUIDs that do not exist in the local SQLite `extensions` table.
* **Fix Required**:
  1. Remove `FOREIGN KEY (extension_id) REFERENCES extensions(id)` from `ai_overviews` definition in `Backend/app/db.py`.
  2. In `init_db()`, check if the existing table has the constraint and migrate/recreate it cleanly without the foreign key.

### Issue 2: Groq API Timeouts & Missing Fallback on Error (HTTP 400)
* **Symptom**: Rapidly clicking extensions causes Groq API to timeout (`15s`), resulting in HTTP 400 errors and broken UI cards.
* **Root Cause**: Because Issue 1 prevented caching, every click hit Groq live. Under concurrent calls, Groq takes > 15s.
* **Fix Required**:
  1. Increase `REQUEST_TIMEOUT_SECONDS` from `15.0s` to `25.0s` in `Backend/app/services/ai.py`.
  2. On timeout (`httpx.TimeoutException`) or upstream error, fall back to `generate_fallback_overview(...)` with `model="llama-3.1-8b-instant-fallback"` instead of raising an unhandled exception.

### Issue 3: Remote Supabase Latency & N+1 Query on `GET /api/extensions`
* **Symptom**: Initial dashboard loading takes 3–7 seconds due to sequential cross-continental round-trips from India to remote Supabase data centers.
* **Root Cause**: `Backend/app/routers/extensions.py` queries `repo.list_extensions()` and then loops through each extension calling `repo.get_latest_snapshot()`, resulting in 1 + N sequential HTTPS round-trips.
* **Fix Required (Approach A)**:
  1. Optimize `repo.list_extensions()` to fetch extensions and their latest snapshots in a **single PostgREST join query** (`.select("*, extension_snapshots(*)")`).
  2. Implement an in-memory TTL cache (60 seconds) on the backend for catalog extensions so subsequent requests respond in `< 2ms`.

---

## 4. Planned Feature: Hero / Intro Section with Perceived Zero-Latency Preloading

### Concept
A modern full-viewport landing section at the top of the application that seamlessly connects to the dashboard:
1. **Visual Elements**:
   * Interactive **Indigo Threads canvas animation** running dynamically in the background (`threads.js`).
   * **Animated AEGIS Shield Logo**: Centered glowing neon shield mark with breathing/pulse glow and shimmer animations.
   * **Typography & Content**: Title, tagline, clear value proposition description, and feature chips (`🛡️ Real-Time Risk Scoring`, `🔍 Permission Creep Auditing`, `🤖 AI Overview Analysis`).
   * **Interactive CTA**: "Explore Extensions Dashboard ↓" button and bouncing scroll indicator that smoothly scrolls into `#app-dashboard`.
2. **Zero-Latency Pre-loading Mechanism**:
   * While the user spends 2–3 seconds reading the intro and watching the animation, the frontend immediately fires the background single-join query (`getExtensions()`).
   * By the time the user scrolls down, all extension details and permissions are **already fetched, rendered, and cached in browser memory**.
   * Transition delivers an instantaneous, zero-spinner experience.

---

## 5. File & Route Directory

| Component | File Path | Key Responsibilities |
|---|---|---|
| **App Entry & Server** | `Backend/app/main.py` | FastAPI setup, middleware stack, CORS, rate limiting |
| **Repository Layer** | `Backend/app/repo.py` | Supabase / SQLite / Mock multi-store repository |
| **Local SQLite DB** | `Backend/app/db.py` | SQLite schema, migration, `ai_overviews` cache |
| **Extension Routes** | `Backend/app/routers/extensions.py` | Extension listing, detail, permissions, version diffs |
| **Import Routes** | `Backend/app/routers/imports.py` | Manifest upload, preflight parsing, deduplication |
| **AI Overview Route** | `Backend/app/routers/ai.py` | AI overview generation, prompt defense, cache checking |
| **AI LLM Service** | `Backend/app/services/ai.py` | Groq chat completion API, fallback generator, prompt builder |
| **Frontend HTML** | `Frontend/dashboard.html` | Page markup, modal dialogs, SVG symbol catalog |
| **Frontend Main JS** | `Frontend/js/main.js` | App bootstrap, event bindings, router, preloading |
| **Threads Canvas** | `Frontend/js/threads.js` | Dual-pass mathematical strand canvas animation |
| **API Client** | `Frontend/js/api.js` | Client-side fetch wrapper, CSRF injection, error handling |
| **CSS Styles** | `Frontend/css/` | `tokens.css`, `base.css`, `layout.css`, `components.css`, `motion.css` |

---

## 6. How to Run the Project Locally

```powershell
# In PowerShell from C:\vs code\AEGIS:
.\.venv\Scripts\python.exe -m uvicorn Backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
Access in browser: `http://127.0.0.1:8000`

---

## 7. Suggested Prompt for Next Step

You can copy and send the prompt below (or customize it) to begin implementation:

```text
Please proceed with implementing the planned enhancements:
1. Fix the backend database issues:
   - Remove the foreign key constraint on the local SQLite `ai_overviews` table in Backend/app/db.py so AI overviews cache cleanly without 500 errors.
   - Update Backend/app/services/ai.py to increase timeout to 25s and use the deterministic fallback overview if Groq times out or errors.
2. Implement Approach A performance optimization:
   - Eliminate the N+1 query in Backend/app/routers/extensions.py and Backend/app/repo.py using a single join query and short in-memory cache.
3. Build the Hero / Intro section on Frontend/dashboard.html:
   - Add full-screen hero landing with the animated threads background, pulsing AEGIS shield logo, description, feature chips, and smooth scroll down button.
   - Enable parallel background preloading in Frontend/js/main.js so the dashboard is instantly ready when scrolling down.
4. Verify all tests pass and ensure smooth end-to-end functionality.
```
