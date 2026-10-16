# AEGIS Part 2c: FastAPI connecting frontend and backend (prompt for Antigravity)

## 0. Context and rules

AEGIS is a browser-extension Permission Creep Auditor. Source of truth: `AEGIS_Handover_Document.md`. Stack and security rules: `AEGIS_Antigravity_Build_Prompt.md`. Done so far: Part 1 (frontend, API contract v1 in `AEGIS_Part1_Frontend_Prompt.md` section 9), 2a (core analysis modules), 2b (Supabase schema with RLS).

| Step | Scope |
|---|---|
| 2a, 2b | Done |
| **2c (this prompt)** | FastAPI app, auth, every security control the server needs, import, frontend wiring |
| 2d | `justification_checker`, `ai_analyzer` (stubbed here) |
| 3 | Testing and security checks (verifies and fixes what you build here) |

**Important.** Part 3 only tests. All security controls (auth, ownership checks, rate limits, CORS, headers, validation, error handling) must be **built in this step**, not postponed.

**Rules.** Modify the existing codebase; this replaces the Flask layer. Preserve working behaviour and prove parity for any existing route. Never invent data. Keep scoring in `core/`; routes only call it. Never ask me to paste secrets into chat, never log them, never commit them. Do not claim anything works unless you ran it.

---

## 1. Phase 0: inspect and plan (do this first)

Report the existing Flask routes and their response shapes, how the frontend currently calls them (`Frontend/js/api.js`), what the repository serves statically, and the current state of secrets, debug settings, and CORS. Propose a file-by-file plan, including how you will keep or retire each Flask route. **Stop and wait for my approval before editing.**

---

## 2. Backend structure

```text
Backend/
├── core/                     # from 2a, unchanged and framework-free
├── data/
├── app/
│   ├── main.py               # app factory, middleware order, routers, static mount
│   ├── config.py             # pydantic-settings, validated at start-up, fails fast
│   ├── security.py           # JWT verification, cookies, CSRF check
│   ├── deps.py               # current_user, user-scoped Supabase client, rate-limit keys
│   ├── errors.py             # typed exceptions and handlers
│   ├── middleware.py         # request id, security headers, body-size limit
│   ├── logging_setup.py      # structured logs with redaction
│   ├── schemas.py            # request and response models (contract v1)
│   ├── repo.py               # ALL database access lives here
│   ├── services/
│   │   ├── assessment.py     # stored snapshot rows -> core objects -> responses
│   │   ├── justification.py  # stub until 2d: every status is "unknown"
│   │   └── ai.py             # stub until 2d: capabilities.ai_analysis is false
│   └── routers/{auth,extensions,imports,health}.py
├── requirements.txt          # pinned versions
└── pyproject.toml            # ruff, mypy, pytest config
```

Use sync `def` routes with the sync Supabase client (they run in a thread pool), or async throughout with an async client; pick one in the plan and be consistent. Pin all dependencies and justify each one. Remove Flask and SQLite code only after parity is shown.

---

## 3. Configuration

`config.py` reads environment variables only and refuses to start if a required one is missing or malformed. It never logs values.

`ENVIRONMENT` (`development` or `production`), `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (only for the isolated admin module, never for user reads), `SUPABASE_JWT_SECRET` (only if the project still uses legacy HS256 keys), `ALLOWED_ORIGINS` (default empty, see section 7), `COOKIE_SECURE`, `TRUSTED_PROXY_COUNT`, `AI_ENABLED`, `GROQ_API_KEY`, `GROQ_MODEL`. In production, reject `COOKIE_SECURE=false`, wildcard origins, and debug flags.

---

## 4. How the backend talks to Supabase

- Per request, build a Supabase client that carries **the caller's access token**, so RLS decides what is visible. This is the default for every read and write of user data.
- The service role key lives in one small module (`admin.py`) used only for explicit admin actions, of which there are none right now. If you find you need it for normal requests, stop and tell me.
- `repo.py` is the only module that touches the database. Every function takes the user-scoped client. Queries use the client's parameterized interface only, never string-built filters.
- Every route that takes `{id}` also verifies ownership through the RLS-scoped query. A record owned by someone else returns **404**, not 403.

---

## 5. Authentication (backend-mediated, cookie-based)

The browser never sees a Supabase key or a raw token in JavaScript.

**Endpoints**
- `POST /api/auth/signup` `{email, password}`: calls Supabase Auth. Always responds with the same neutral message ("If this email can be used, check your inbox") so accounts cannot be enumerated.
- `POST /api/auth/login` `{email, password}`: signs in with Supabase Auth, then sets cookies.
- `POST /api/auth/refresh`: rotates the session from the refresh cookie.
- `POST /api/auth/logout`: revokes the session and clears cookies.
- `GET /api/auth/me`: `{email}` or 401.
- Password reset is out of scope; list it as a follow-up unless Supabase makes it trivial.

**Cookies.** Access and refresh tokens in `HttpOnly`, `Secure`, `SameSite=Strict` cookies. In production use the right prefixes (`__Host-` needs `Path=/` and no Domain; the refresh cookie may need a different prefix if you scope it to `/api/auth`). Locally over plain `http://localhost`, allow `COOKIE_SECURE=false` and unprefixed names, and make that impossible in production.

**CSRF.** Every non-GET request must carry a custom header (for example `X-AEGIS-CSRF: 1`) and a same-origin `Origin` or `Referer`. Reject otherwise with 403. `SameSite=Strict` is the first layer, this is the second.

**JWT verification.** Verify locally with PyJWT: signature, `exp`, `iss` (your Supabase auth URL), and `aud == "authenticated"`. Prefer the project's asymmetric keys through the JWKS endpoint (cached with a TTL); fall back to the legacy HS256 secret only if the project still uses it. Document which one the project uses in the plan. Reject `alg: none` and any algorithm not on a short allow-list.

**Roles.** Authorization uses `app_metadata.role` only, never `user_metadata` (users can edit that). There are no admin routes now, so do not create any. If an old admin route exists, delete it and tell me.

---

## 6. Endpoints

Follow contract v1 exactly; additive fields are allowed. Every route has a Pydantic `response_model`, so no database column ever leaks by accident. Request models use `extra="forbid"`. Path IDs are typed as UUID.

| Method and path | Behaviour |
|---|---|
| `GET /api/health` | Public. `{"status":"ok"}` and nothing else. |
| `GET /api/extensions` | The caller's extensions, each from its latest snapshot (highest `version_key`, then newest `captured_at`). `source` is `"imported"`. `limit` up to 200. |
| `GET /api/extensions/{id}` | Metadata and `assessment` from `risk_scoring`. `description.origin` is `manifest` or `unavailable` (never claim `store`). `capabilities.ai_analysis` comes from `services/ai.py`. Additive: `potential_score`, `notes`, `unrecognized`, `formula_version`, `knowledge_version`, `name_is_placeholder`. |
| `GET /api/extensions/{id}/permissions` | `{api, host, optional}`; each item as `Perm`. `status`, `reason`, and `evidence` come from `services/justification.py`; until 2d every item is `unknown` with the reason "Justification checker not installed yet". Never fabricate a status. |
| `GET /api/extensions/{id}/versions` | Snapshots sorted newest first. |
| `GET /api/extensions/{id}/compare?from=&to=` | `core.version_comparison.compare`. Both versions must be snapshots of this extension, otherwise 404. Version strings are validated (length, charset). |
| `GET /api/extensions/{id}/creep` | Compares the latest two snapshots. With only one, return `available: false, reason: "baseline_not_available"`; never a zero score. |
| `POST /api/extensions/{id}/analyze` | Stub until 2d: 404 with code `ai_unavailable` while `capabilities.ai_analysis` is false. |
| `POST /api/extensions/import` | See section 6.1. |
| `DELETE /api/extensions/{id}` | Deletes the caller's extension and, by cascade, its snapshots and icon. 204. |

Scores and statuses are recomputed from stored columns on each read, using the current rules. Responses include `formula_version` and `knowledge_version` so any number can be reproduced.

### 6.1 Import (`POST /api/extensions/import`)

Manifest import is the only way data enters AEGIS (a web page cannot list installed extensions), so this route matters.

- `multipart/form-data` fields: `manifest` (required, `.json`), `browser` (required, one of chrome, edge, firefox, brave, opera, other), `store_id` (optional), `display_name` (optional), `messages` (optional `messages.json` for localized names), `icon` (optional).
- Limits: whole request at most 1.5 MB, `manifest` at most 1 MB, `icon` at most 256 KB. Enforce with a streaming body-size limit, not only the `Content-Length` header. Reject any other content type with 415.
- Parse with `core.manifest_parser` only. Never `eval`, never execute or unpack anything. Map `ManifestError` codes to 422 with the code and a safe message.
- If the name is a placeholder and no `display_name` or `messages` resolves it, return 422 `name_unresolved` asking for one of them.
- **Icon:** accept only PNG, JPEG, or WebP, verified by magic bytes (not the filename or declared type), size-capped, and re-encoded or at minimum dimension-checked. Reject SVG. Store in the private bucket and serve through short-lived signed URLs. Return `icon_url` as a signed URL or null.
- **Matching to an existing extension:** by `(user, browser, store_id)` if `store_id` is given; otherwise by normalized name plus browser within the user's records. No match creates a new extension. The response says `matched_existing: true|false` so the UI can tell the user.
- **Snapshots are append-only.** Same version and same SHA-256: 200, idempotent, `created: false`. Same version, different manifest: **409** `version_conflict`. New version: 201, `created: true`.
- Response: `{extension: <list item>, snapshot: {version, created}, matched_existing, warnings: [...]}`.
- Store the sanitized manifest (size-capped) plus the normalized columns from `ParsedManifest`.

---

## 7. Security controls (build all of them now)

**Middleware order:** request id, security headers, body-size limit, CORS (only if configured), rate limiting, routes.

- **Errors.** Every error uses `{"error": {"code", "message", "request_id"}}`. Validation errors list field names but never echo submitted values. Unhandled exceptions return a generic 500 with the request id; details go only to the server log. Never forward Supabase or Groq error text to the client.
- **Request id.** Always generate your own UUID, return it in `X-Request-ID`, and include it in logs.
- **Logging.** Structured JSON. Redact `Authorization`, cookies, passwords, and manifest bodies. Log method, path, status, latency, user id hash, request id. No `print` debugging anywhere.
- **Rate limits** (slowapi or equivalent, keyed by user id when signed in, else client IP; trust `X-Forwarded-For` only for the configured number of proxies). Return 429 with `Retry-After`.

| Route group | Limit |
|---|---|
| login | 5 per minute and 20 per hour per IP |
| signup | 3 per minute and 10 per hour per IP |
| refresh | 30 per minute per IP |
| import | 10 per minute and 100 per day per user |
| analyze (2d) | 5 per minute and 30 per day per user |
| delete | 20 per minute per user |
| other reads | 120 per minute per user |

  In-memory counters are per process. If more than one worker will run, say so and propose a shared store.
- **CORS.** The app serves the frontend itself, so it is same-origin and **no CORS middleware is installed** unless `ALLOWED_ORIGINS` is non-empty. If set: explicit origins only, no `*`, only the methods and headers actually used, credentials only with an explicit origin.
- **Security headers** on every response, including errors and static files: `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data: <the Supabase storage origin>; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`, `Strict-Transport-Security` (production), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, a `Permissions-Policy` that turns everything off, `Cross-Origin-Opener-Policy: same-origin`, and `Cache-Control: no-store` on `/api/*`.
- **Docs and debug.** In production, `docs_url`, `redoc_url`, and `openapi_url` are disabled. No `debug=True`, no `--reload`, no stack traces in responses.
- **Static files.** Mount only the `Frontend/` directory at `/`, last, after the API routers. Symlinks are not followed. `.env`, `.git`, `dev/`, `supabase/`, `tests/`, `docs/`, and Python files must all return 404. No directory listing.
- **Input handling.** Strict Pydantic models for every body, query, and path parameter, with length and size caps. No SQL or filter strings built from user input.

---

## 8. Frontend wiring (small, inside the Part 1 design system)

Keep every Part 1 rule: no `innerHTML`, no inline scripts or styles, no banned patterns, strict CSP, accessibility, reduced motion.

- `api.js`: switch to the real backend (same contract). Add the CSRF header on non-GET requests, keep `credentials: 'same-origin'`. The fixture banner only appears when a response says `"source": "fixture"`, which the real backend never sends.
- **Auth view.** On `aegis:unauthorized` (401), show a sign-in and sign-up view **inside the single page** (a state of the main panel, not a new page). Fields have labels, errors are announced, the sign-up message is the neutral one from section 5. A sign-out button sits at the bottom of the sidebar. No tokens or user data are kept in JavaScript or `localStorage`.
- **Import control** at the bottom of the sidebar: a compact button opening an accessible dialog with the manifest file input, the browser select, optional store id, optional display name, optional icon. Show the result clearly: created, already imported, `version_conflict`, `name_unresolved` (then reveal the display name field), parse errors with their codes.
- **Delete** an extension from its identity panel, with an accessible confirmation dialog.
- **429** shows "Too many requests. Try again in N seconds." using `Retry-After`.
- Empty state for a signed-in user with no extensions: the lockup logo and "No extensions yet. Import a manifest to begin."
- Keep the mock API usable for development, but production serves only the real backend.

---

## 9. Tests (required)

- `pytest` with FastAPI's test client. Use an in-memory fake of `repo.py` for fast route tests, plus integration tests against the **dev** Supabase gated by `AEGIS_INTEGRATION=1`.
- Cover: every route's happy path and its response against contract v1; 401 without or with an invalid, expired, or wrong-audience token; 404 for another user's records; CSRF rejection; 429 behaviour; import success, idempotent re-import, `version_conflict`, `name_unresolved`, oversized and malformed manifests, a fake PNG with a wrong extension, an SVG icon; error bodies never contain stack traces or Supabase text; security headers present on `/`, on `/api/*`, and on a 404; docs routes return 404 in production mode; sensitive files return 404.
- Run the frontend against the real backend once end to end in the browser (sign up with a dev test account, import a fictional manifest, select it, compare two versions) and report what you saw, with screenshots.

---

## 10. Deliverables and report

1. The FastAPI app, wiring, tests, pinned requirements, updated `.env.example`, and a `README` section with exact run commands for development and production.
2. A report: changed files, the route parity table (old Flask route to new route), decisions you made (sync vs async, JWT method), what is stubbed until 2d, every limitation, and anything I must do by hand.

Do not describe anything as working unless you ran it.
