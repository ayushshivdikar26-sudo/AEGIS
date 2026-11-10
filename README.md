# AEGIS — Automated Extension Governance & Inspection Suite

AEGIS is an open-source, deterministic security auditor for browser extension manifests. It provides deep permission analysis, detects cross-version permission creep, calculates objective risk scores, and generates transparent explainability reports without relying on opaque LLMs.

---

## 🚀 Beginner Quickstart: Run AEGIS Locally & Audit Your Own Extensions

> 💡 **For Friends & Reviewers:**  
> If you double-click `dashboard.html` directly from your file manager, your browser will open it as `file:///...` and block the scripts and API for security reasons (you will see an offline/file error).  
> **Follow these simple steps to run the live app and automatically inspect the extensions installed on your own browser:**

### Step 1: Prerequisites
* **Python 3.11+** installed ([Download Python](https://www.python.org/downloads/)).  
  ⚠️ **Important on Windows:** During Python installation, check the box that says **"Add python.exe to PATH"**.
* **Google Chrome, Microsoft Edge, Brave, or Opera** installed (if you want your installed extensions auto-detected).

---

### Step 2: Clone & Open the Project
Open your terminal (PowerShell, Command Prompt, or Terminal on macOS/Linux):

```bash
git clone https://github.com/ayushshivdikar26-sudo/AEGIS.git
cd AEGIS
```

---

### Step 3: Set Up Python Virtual Environment & Install Dependencies

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

*(If PowerShell shows an execution policy script error, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` then activate again).*

**On macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### Step 4: Run the Application

```bash
# Windows
.venv\Scripts\uvicorn Backend.app.main:app --port 8000

# macOS / Linux
uvicorn Backend.app.main:app --port 8000
```

---

### Step 5: Open the App in Your Browser
Open your browser and navigate to:  
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

#### 🔍 How to See Your Own Extensions on Your Machine:
1. **Automatic Detection:** On startup, AEGIS automatically discovers extensions installed in your default Chrome, Edge, Brave, or Opera browser profiles. They will appear right in the sidebar with their real names, icons, permission breakdowns, and calculated risk scores!
2. **Manual File / ZIP Import:** Click the **`+ Import Custom Manifest`** button on the landing page or sidebar to upload any unpacked extension folder's `manifest.json`, upload an extension `.zip`, or paste raw manifest JSON.

---

## ❓ Frequently Asked Questions (FAQ)

### Q: Why aren't API keys committed to GitHub? How will the website work without them?
**Secrets (like `.env` containing private API keys) are deliberately excluded from GitHub via `.gitignore`.** This is an industry-standard security practice to prevent unauthorized access, database tampering, and API billing exhaustion.

**Does AEGIS need API keys to work? NO!**
* **100% Offline Local Engine (Default):** AEGIS is built with a zero-configuration local fallback. In `development` mode, it uses a local SQLite database (`Backend/data/aegis.db`) and local browser profile scanner. It does **not** require Supabase credentials, cloud accounts, or an active internet connection to evaluate manifests, compute risk scores, check for permission creep, or scan your installed extensions.
* **AI Overview Fallback:** If Groq LLM API keys are not supplied, AEGIS automatically generates a deterministic, rule-based security summary without throwing errors or breaking the UI.

### Q: Can my friend connect to my Supabase database by pasting the API keys?
**YES!** If you share your `.env` configuration with your friend privately (e.g. via direct message or password manager):
1. They copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Paste your project's `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` (and `SUPABASE_SECRET_KEY` if running admin synchronizations).
3. The moment AEGIS boots with those credentials in `.env`, it automatically connects to your Supabase project with Row-Level Security (RLS) and synchronizes audit snapshots!

> ⚠️ **Security Tip:** Never post your `SUPABASE_SECRET_KEY` (service role key) or `GROQ_API_KEY` publicly on GitHub. Share `.env` files only through private, secure channels with trusted collaborators.

---

## Key Capabilities

- **Deterministic Risk Scoring:** Mathematical assessment (0–100) based on permission criticality weights, host pattern scope, and danger floors (40/70). Zero stochastic AI hallucinations.
- **Permission Creep & Host Broadening:** Chronological version comparison identifying added, removed, retained, and broadened host patterns (e.g., `github.com` $\to$ `<all_urls>`).
- **Live Local Scanner:** Automatically discovers extensions installed in local Chrome, Edge, Brave, and Opera user data directories, extracting manifests and native icons.
- **Purpose Justification Engine:** Matches declared functional intent against requested capabilities using 15 taxonomies and 6 deterministic rules (R1–R6).
- **Enterprise-Grade Security:** Supabase JWKS token authentication, forced Row-Level Security (RLS) tenant isolation, Redis rate limiting, and strict CSP (`default-src 'self'`).
- **Responsive Dashboard:** Accessible interface featuring a dynamic SVG speedometer gauge, mobile drawer, and WCAG 2.1 AA compliant color contrast.

---

## Architecture Overview

```
       +--------------------------------------------------------+
       |             Browser / Client (Vanilla ES2022)          |
       |  - Semantic CSS (Dark Slate Palette)                   |
       |  - Dynamic SVG Speedometer Gauge                       |
       |  - Strict CSP: default-src 'self'                      |
       +---------------------------+----------------------------+
                                   |
                          HTTP / Secure Cookies
                                   |
       +---------------------------v----------------------------+
       |             FastAPI Application Layer                  |
       |  - Security & Request-ID Middleware                    |
       |  - Asymmetric JWKS Authentication (RS256/ES256)        |
       |  - Redis-Backed Sliding Window Rate Limiting           |
       +-------------+----------------------------+-------------+
                     |                            |
       +-------------v------------+  +------------v-------------+
       |  AEGIS Analysis Engine   |  |   Database & Persistence |
       |  - Manifest Parser (NFC) |  |   - Supabase PostgreSQL  |
       |  - Scoring Engine (R1-R6)|  |   - Local SQLite (Default|
       |  - Creep Analyzer (V1-V7)|  |   - Row-Level Security   |
       +--------------------------+  +--------------------------+
```

---

## Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Environment mode (`development` or `production`). |
| `SUPABASE_URL` | `https://localhost.supabase.co` | Supabase project URL (must use HTTPS in production). |
| `SUPABASE_PUBLISHABLE_KEY` | `mock-publishable-key` | Supabase publishable/anon API key. |
| `SUPABASE_SECRET_KEY` | `mock-secret-key` | Service role key. Used **only** for administrative tasks and test setup. |
| `SUPABASE_JWT_SECRET` | *(empty)* | Optional legacy HS256 secret fallback for token decoding. |
| `DATABASE_URL` | `Backend/data/aegis.db` | Persistent relational connection string (defaults to local SQLite file). |
| `RATE_LIMIT_STORAGE_URI` | `redis://localhost:6379/0` | Redis URI for distributed sliding-window rate limiting. |
| `ALLOWED_ORIGINS` | *(empty)* | Comma-separated CORS allowed origins. Prohibits `*` in production. |
| `COOKIE_SECURE` | `false` | Sets `Secure` flag on session cookies (must be `true` in production). |
| `AI_ENABLED` | `false` | Enables optional Groq LLM explanations. Default `false`. |
| `GROQ_API_KEY` | *(empty)* | Groq API key when `AI_ENABLED=true`. |

---

## Security Architecture

AEGIS is built from the ground up according to strict defensive engineering principles:

- **Asymmetric Authentication:** JWT tokens issued by Supabase Auth are validated asymmetrically via JWKS (`RS256`/`ES256`). Tokens with `alg: none` or invalid signatures are rejected.
- **Zero Secret Exposure:** Credentials and tokens are stored exclusively in server memory and `HttpOnly`, `SameSite=Lax` cookies. No API keys exist in client-side code.
- **Fail-Closed Rate Limiting:** Critical routes (`/api/auth/login`, `/api/auth/signup`, `/api/extensions/import`, `/api/ai-overview`) enforce token-bucket rate limits.
- **Input Sanitization & Attack Resistance:**
  - Manifest parser normalizes text with Unicode NFC and strips Right-to-Left Override controls (`\u202e`) to prevent Trojan Source attacks.
  - Nesting depth in JSON manifests is strictly capped at 32 levels to prevent recursion DoS.
  - Streaming file uploads enforce a 1MB maximum manifest size; oversized payload bombs are rejected.
  - Icon uploads are verified against magic byte signatures (`PNG`, `JPEG`, `WEBP`). SVG files are rejected to prevent SVG-embedded XSS/XXE attacks.
- **Content Security Policy (CSP):**
  ```text
  default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self';
  img-src 'self' data: <supabase_host>; connect-src 'self' <supabase_host>;
  object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
  ```
- **Auditing & Verification:** Full details and evidence citations are documented in [`SECURITY_AUDIT.md`](file:///c:/vs%20code/AEGIS/SECURITY_AUDIT.md).

---

## Scoring & Justification Rules

The AEGIS analysis engine scores extensions between **0 and 100** using deterministic rules:

### Risk Thresholds
- **Low Risk (0–34):** Minimal exposure; routine API permissions (e.g., `storage`, `alarms`) with narrow host access.
- **Medium Risk (35–69):** Moderate exposure; access to active tabs or broad host patterns (`*://*.example.com/*`).
- **High Risk (70–100):** High exposure; broad host access (`<all_urls>`, `*://*/*`) combined with sensitive APIs (`webRequestBlocking`, `cookies`, `nativeMessaging`) or Danger Floors (40/70).

### Danger Floors
- **Critical Danger Floor (70):** Any manifest requesting weight-5 capabilities (`debugger`, `nativeMessaging`, `proxy`, `all_sites`) is clamped to a minimum score of 70 (High Risk).
- **High Danger Floor (40):** Any manifest requesting weight-4 capabilities (`cookies`, `webRequest`, `tabs`, `clipboardRead`) is clamped to a minimum score of 40 (Medium/High Risk).

### Justification Rules (R1–R6)
- **R1 (Declared & Aligned):** Permission declared in manifest and justified by keywords in description $\rightarrow$ `justified`.
- **R2 (Broad Host Without Narrower):** Broad host access where no narrower host pattern is viable $\rightarrow$ `potentially_excessive`.
- **R3 (High-Risk Capability):** Dangerous capabilities (`webRequestBlocking`, `management`) requiring elevated scrutiny $\rightarrow$ `flagged`.
- **R4 (Unknown / Insufficient Info):** Keyword match inconclusive or description missing $\rightarrow$ `unknown`.
- **R5 (Potentially Excessive):** Sensitive API requested without corroborating functionality in description $\rightarrow$ `potentially_excessive`.
- **R6 (Optional Permission):** Declared as optional, granted only on user demand $\rightarrow$ `optional`.

Full mathematical definitions and scoring formulas are detailed in [`docs/SCORING.md`](file:///c:/vs%20code/AEGIS/docs/SCORING.md) and [`docs/RULES.md`](file:///c:/vs%20code/AEGIS/docs/RULES.md).

---

## Test Suite Execution

### 1. Full Backend Test Suite (Pytest)
Executes all core engine, API, rate limiting, and database schema integrity tests:
```bash
.venv\Scripts\pytest tests/core tests/app tests/db/test_schema_integrity.py -v
```

### 2. Adversarial "Break-It" Suite
Executes all 19 attack-surface tests (fuzzing, XSS, Unicode spoofing, depth bombs, SQLi, tenant isolation, rate limit hammer):
```bash
.venv\Scripts\pytest tests/app/test_break_it.py -v
```

### 3. Frontend JavaScript Unit Tests
Executes client-side filtering, gauge math, and risk level mapping tests using Node's native test runner:
```bash
node tests/unit_js/test_filter.js
node tests/unit_js/test_risk.js
```

### 4. Dependency Vulnerability Audit
Scans installed Python packages against the National Vulnerability Database (NVD):
```bash
.venv\Scripts\pip-audit
```

---

## Known Limitations

1. **Static Manifest Inspection:** AEGIS analyzes declarative manifest specifications (`manifest.json`). It does not dynamically execute extension JavaScript in an isolated browser sandbox.
2. **Heuristic Keyword Matching:** Purpose alignment is determined through heuristic taxonomy matching between declared capabilities and published descriptions.
3. **AI Explanations (Optional):** Natural language AI explanations are disabled by default (`AI_ENABLED=false`) to ensure complete determinism, audit reproducibility, and zero external LLM dependencies.

---

## License

This project is licensed under the Apache 2.0 License.
