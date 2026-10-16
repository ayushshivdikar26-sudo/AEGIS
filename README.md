# AEGIS — Automated Extension Governance & Inspection Suite

AEGIS is an open-source, deterministic security auditor for browser extension manifests. It provides deep permission analysis, detects cross-version permission creep, calculates objective risk scores, and generates transparent explainability reports without relying on opaque LLMs.

---

## Key Capabilities

- **Deterministic Risk Scoring:** Mathematical assessment (0–100) based on permission criticality weights, host pattern scope, and keyword-justified purpose alignment. Zero LLM hallucinations.
- **Permission Creep Engine:** Compares versions chronologically to identify added, removed, retained, and broadened permissions with clear outcome classifications (`approved`, `needs_review`, `high_risk`).
- **Live Local Scanner:** Discovers installed extensions directly from local Chrome and Edge profiles, parsing real manifest data and rendering native 128px icons under strict security policies.
- **Enterprise-Grade Security:** Asymmetric JWT verification via Supabase JWKS, Row-Level Security (RLS) tenant isolation, Redis-backed sliding-window rate limiting, and strict CSP (`default-src 'self'`).
- **Responsive Dashboard:** Accessible interface featuring a continuous linear gradient speedometer gauge, keyboard navigation, and WCAG 2.1 AA compliant color contrast.

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
       |  - Scoring Engine (R1-R6)|  |   - Row-Level Security   |
       |  - Creep Analyzer (V1-V7)|  |   - Upstash / Local Redis|
       +--------------------------+  +--------------------------+
```

---

## Quickstart & Installation

### Prerequisites
- **Python 3.11+** (Python 3.13 recommended)
- **Node.js 18+** (for frontend unit test execution)
- **Git**

### 1. Clone the Repository
```bash
git clone https://github.com/your-org/aegis.git
cd aegis
```

### 2. Set Up Virtual Environment
```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
For local offline testing, default values work out of the box with in-memory fallbacks. For production or Supabase-backed mode, configure your credentials in `.env`.

---

## Running the Application

### Development Mode (Local Live Dashboard)
Starts the backend server with hot-reload enabled. Serves both the FastAPI endpoints and the frontend dashboard:

```bash
# Windows PowerShell
.venv\Scripts\uvicorn Backend.app.main:app --reload --host 127.0.0.1 --port 8000

# Linux / macOS
uvicorn Backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser and navigate to:  
👉 **http://127.0.0.1:8000/**

### Production Deployment Mode
In production, run Uvicorn behind a reverse proxy (e.g., Nginx, Cloudflare) with multiple worker processes and a shared Redis rate-limit store:

```bash
uvicorn Backend.app.main:app \
  --workers 4 \
  --host 0.0.0.0 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips='*'
```

> **Production Security Checklist:**
> - Set `ENVIRONMENT=production` in `.env`.
> - Set `COOKIE_SECURE=true` (requires HTTPS).
> - Configure `RATE_LIMIT_STORAGE_URI` to a reliable shared Redis cluster (e.g., Upstash or Redis Enterprise).
> - In production, API documentation (`/docs`, `/redoc`) is automatically disabled.

---

## Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Environment mode (`development` or `production`). |
| `SUPABASE_URL` | `https://localhost.supabase.co` | Supabase project URL (must use HTTPS in production). |
| `SUPABASE_PUBLISHABLE_KEY` | `mock-publishable-key` | Supabase publishable/anon API key. |
| `SUPABASE_SECRET_KEY` | `mock-secret-key` | Service role key. Used **only** for administrative tasks and test setup. |
| `SUPABASE_JWT_SECRET` | *(empty)* | Optional legacy HS256 secret fallback for token decoding. |
| `RATE_LIMIT_STORAGE_URI` | `redis://localhost:6379/0` | Redis URI for distributed sliding-window rate limiting. |
| `ALLOWED_ORIGINS` | *(empty)* | Comma-separated CORS allowed origins. Prohibits `*` in production. |
| `COOKIE_SECURE` | `false` | Sets `Secure` flag on session cookies (must be `true` in production). |
| `TRUSTED_PROXY_COUNT` | `0` | Number of upstream reverse proxies to trust for client IP detection. |
| `AI_ENABLED` | `false` | Enables optional Groq LLM explanations (Milestone M8). Default `false`. |

---

## Security Architecture

AEGIS is built from the ground up according to strict defensive engineering principles:

- **Asymmetric Authentication:** JWT tokens issued by Supabase Auth are validated asymmetrically via JWKS (`RS256`/`ES256`). Tokens with `alg: none` or invalid signatures are rejected.
- **Zero Secret Exposure:** Credentials and tokens are stored exclusively in server memory and `HttpOnly`, `SameSite=Lax` cookies. No API keys exist in client-side code.
- **Fail-Closed Rate Limiting:** Critical routes (`/api/auth/login`, `/api/auth/signup`, `/api/extensions/import`) fail closed (HTTP 503) if the shared Redis limiter becomes unavailable. Read endpoints fail open with a logged warning.
- **Input Sanitization & Attack Resistance:**
  - Manifest parser normalizes text with Unicode NFC and strips Right-to-Left Override controls (`\u202e`) to prevent Trojan Source attacks.
  - Nesting depth in JSON manifests is strictly capped at 32 levels.
  - Streaming file uploads enforce a 2MB maximum manifest size; 50MB payload bombs are rejected with HTTP 413.
  - Icon uploads are verified against magic byte signatures (`PNG`, `JPEG`, `WEBP`). SVG files are rejected to prevent SVG-embedded XSS/SSRF.
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
- **Low Risk (0–29):** Minimal exposure; routine API permissions (e.g., `storage`, `alarms`) with narrow host access.
- **Medium Risk (30–69):** Moderate exposure; access to active tabs or broad host patterns (`*://*.example.com/*`).
- **High Risk (70–100):** High exposure; broad host access (`<all_urls>`, `*://*/*`) combined with sensitive APIs (`webRequestBlocking`, `cookies`, `nativeMessaging`).

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

### 5. Static Linting & Type Checking
```bash
.venv\Scripts\ruff check Backend/
.venv\Scripts\mypy Backend/
```

---

## Known Limitations

1. **Static Manifest Inspection:** AEGIS analyzes declarative manifest specifications (`manifest.json`). It does not dynamically execute extension JavaScript or analyze minified background scripts in an isolated sandbox.
2. **Heuristic Keyword Matching:** Purpose alignment is determined through heuristic pattern matching between declared permissions and published extension descriptions. While deterministic and reproducible, it may misclassify novel descriptions lacking conventional terminology.
3. **AI Explanations (Deferred M8):** AI-powered natural language explanations are disabled by default (`AI_ENABLED=false`) to ensure complete determinism, audit reproducibility, and zero external LLM dependencies.

---

## License

This project is licensed under the Apache 2.0 License.
