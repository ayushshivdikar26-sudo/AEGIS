# AEGIS Part 1 of 5: Frontend (prompt for Antigravity)

## 0. Where this fits

AEGIS is a browser-extension Permission Creep Auditor. The work is split into five parts, each with its own prompt:

| Part | Scope |
|---|---|
| **1. Frontend (this prompt)** | Design system, logo, animated threads background, the single-page dashboard, API client, dev-only mock API |
| 2. Backend core | FastAPI migration, Supabase schema and RLS, scoring parity, snapshots, comparison, creep endpoints |
| 3. Auth and hardening | Supabase Auth, cookies and CSRF, admin role, rate limits, CORS, headers, uploads, error handling |
| 4. Groq analyzer | Optional AI explanation, strictly bounded |
| 5. QA and audit | Break-it testing, test-data removal, `SECURITY_AUDIT.md`, README |

**Do only Part 1.** Do not touch the backend, the database, or auth in this part, except for the dev-only mock API described in section 10.

**Attached to this prompt**
1. `AEGIS_Handover_Document.md`: product source of truth. Follow its sections 2, 3, 6 (UI only), 7 (UI only), 9, and 11.
2. Threads reference image: indigo light threads on near-black. Sets the palette and the background motion. Ignore the heart icon and card frame in the screenshot.
3. Logo reference image (green and cyan shield with an eye) and three finished indigo SVG logos: `aegis-mark.svg`, `aegis-lockup.svg`, `favicon.svg`. The mark source is also in Appendix A.
4. The master build prompt (`AEGIS_Antigravity_Build_Prompt.md`) for palette, banned patterns, and security rules. Where it conflicts with this prompt, this prompt wins for the frontend.

**Working rules.** Modify the existing codebase and keep working features. Never invent extension metadata, versions, permission changes, or scores. Never present sample data as live data. Do not claim something works unless you tested it.

---

## 1. Phase 0: inspect and plan (do this first)

Before editing, read the repository and report:

- The frontend entry file (the handover calls it `dashboard.html`), the CSS and JS files, and how the selected extension is rendered today.
- The existing API routes and the JSON shapes the frontend already consumes.
- Whether manifest import already exists in the UI.
- Anything in the frontend that uses `innerHTML`, inline scripts, inline styles, or external resources (CDNs, Google Fonts).

Then give a file-by-file plan that maps the existing files onto the structure in section 2. **Stop and wait for my approval before changing files.**

---

## 2. App structure

Keep it a single page of plain HTML, CSS, and ES modules. No framework and no build step unless the plan justifies one. If the existing entry file has a different name, keep that name.

```text
Frontend/
├── dashboard.html              # one page: landmarks + empty mount points, no inline script or style
├── assets/
│   ├── logo/
│   │   ├── aegis-mark.svg
│   │   ├── aegis-lockup.svg
│   │   └── favicon.svg
│   ├── icons.svg               # sprite: search, chevron, close, menu, check (hand-drawn, 5 icons max)
│   └── fonts/                  # self-hosted IBM Plex Sans + Mono, woff2
├── css/
│   ├── tokens.css              # colors, type scale, spacing, motion durations
│   ├── base.css                # reset, typography, focus ring, @font-face
│   ├── layout.css              # shell, sidebar, main column, drawer, breakpoints
│   ├── components.css          # rows, chips, gauge, accordion, selects, buttons
│   └── motion.css              # all transitions and keyframes + reduced-motion overrides
└── js/
    ├── main.js                 # boot: threads, load list, wire events, hash routing
    ├── state.js                # tiny store: extensions, query, selectedId, per-section status
    ├── api.js                  # the only file that calls fetch (section 9)
    ├── dom.js                  # h(tag, attrs, ...children) builder; textContent only
    ├── threads.js              # canvas background (section 6)
    ├── lib/
    │   ├── risk.js             # score -> level, score -> needle angle, arc path math (pure)
    │   └── filter.js           # list search (pure)
    └── render/
        ├── sidebar.js
        ├── identity.js
        ├── gauge.js
        ├── about.js
        ├── permissions.js
        ├── versions.js
        ├── creep.js
        └── states.js           # loading, empty, error, retry blocks
dev/                            # NEVER served by the app, excluded from production
└── mock-api/
    ├── serve.py
    └── fixtures/*.json
```

**Data flow.** `main.js` calls `api.js`. `api.js` returns plain objects or throws a typed error. `state.js` holds them. `render/*` functions take data and return DOM nodes built with `dom.js`. Render functions never fetch and never calculate scores.

**Scoring stays in Python.** The frontend only displays `risk_score`, `risk_level`, labels, and breakdowns that the API returns. The only math allowed in JS is geometry for the gauge and the progress bar.

---

## 3. Design system

One hue family: indigo, around 240 degrees. No purple. No gradients anywhere in the UI.

```css
:root {
  --bg:          #07061A;  /* page */
  --surface:     #0F0E2A;  /* panels, sidebar (opaque) */
  --surface-2:   #151338;  /* inputs, selected row, icon tiles */
  --border:      #2A2760;  /* neutral hairlines only */
  --accent:      #5B5BF0;  /* fills; white text on it is 5:1 */
  --accent-text: #8B8BFF;  /* links, focus ring (6.8:1 on bg) */
  --text:        #F5F5FF;
  --text-muted:  #A9A8D4;  /* 8:1 on surface */

  --risk-low:    #22C55E;
  --risk-mid:    #F59E0B;
  --risk-high:   #EF4444;

  /* thread ramp: used by threads.js only */
  --thread-1: #2B2A8F; --thread-2: #4747E0; --thread-3: #6B6BF5; --thread-4: #9A9AFF;

  /* spacing: 4px base, no other values allowed */
  --s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px; --s-5: 24px; --s-6: 32px; --s-7: 48px;

  --radius: 8px;
  --ease: cubic-bezier(.2,.7,.2,1);
}
```

**Type.** IBM Plex Sans for UI, IBM Plex Mono for permission names, host patterns, versions, and the score number. Self-host woff2 (400, 500, 600). Scale: 12, 14, 16, 20, 28. Section labels are 12 px uppercase with 0.08em tracking in `--text-muted`, as in the wireframe. Everything else is sentence case.

**Shape.** Panels are opaque `--surface` with a 1 px neutral `--border` and 8 px radius. No colored borders, no glass, no heavy shadows. Selected sidebar row: `--surface-2` tint, 600 weight name, `aria-current="true"`.

**Risk chips** (LOW, MEDIUM, HIGH, CRITICAL): filled with the risk color and `--bg` text (all pass 4.5:1), 12 px, mono, uppercase. Color is never the only signal: the word is always shown.

**Icons.** Use the extension's own logo wherever one exists. Hand-draw the 5 UI icons in `assets/icons.svg`. No icon library.

**Hover and focus.** Hover is an instant solid color change, never an opacity fade. Focus is a 2 px `--accent-text` outline with a 2 px offset on every interactive element.

---

## 4. Logo

The reference logo (shield with notched shoulders, an upward chevron like an eyelid, a quartered circle pupil) has been redrawn in the thread indigo ramp with flat facets instead of the original green-cyan gradient. Keep the construction. Do not redraw or recolor it. If something looks wrong, tell me instead of fixing it.

- `aegis-mark.svg`: inline it once in `dashboard.html` for the sidebar header (28 px tall) and reuse with `<use>`. Its internal ids are prefixed `aegis-`, so inline it only once per document.
- Next to the mark in the sidebar, write "AEGIS" as live text: IBM Plex Sans 600, 16 px, letter-spacing 0.2em, `--text`.
- `aegis-lockup.svg`: for the empty state in the main panel, 160 px wide, centered. This is where the threads show most.
- `favicon.svg`: `<link rel="icon" type="image/svg+xml" href="assets/logo/favicon.svg">`.
- Never stretch, rotate, or put effects on the logo. Clear space around the mark is at least half its width.

---

## 5. Layout and wireframe

```text
┌──────────────────┬──────────────────────────────────────────┐
│                  │                                          │
│   AEGIS          │       [ LARGE EXTENSION LOGO ]            │
│                  │                                          │
│   Extensions     │       Google Docs Offline                │
│                  │       Google Chrome · v2.4.0             │
│   [ Search ]     │                                          │
│                  │          [ RISK SPEEDOMETER ]             │
│   [ Extension ]  │                                          │
│   [ Extension ]  │       Risk Score: 72 / 100                │
│   [ Extension ]  │                                          │
│   [ Extension ]  │       ABOUT                               │
│                  │       Extension description              │
│                  │                                          │
│                  │       PERMISSIONS                         │
│                  │       storage                      LOW    │
│                  │       alarms                       LOW    │
│                  │       history                     HIGH    │
│                  │                                          │
│                  │       VERSION COMPARISON                  │
│                  │       [Old version] → [New version]       │
│                  │       Highlight added permissions        │
│                  │                                          │
│                  │       PERMISSION CREEP                    │
│                  │       Changes and explanation             │
│                  │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

The names in the wireframe are placeholders. Do not ship them as data.

**Desktop (1024 px and up).**
- Sidebar: fixed 320 px, full height, opaque `--surface`, its own scroll. Header (mark and "AEGIS"), the label "Extensions", the search field, then the list. If manifest import already exists, keep it as a compact button at the bottom of the sidebar. If it does not exist, do not build it here.
- Main: scrolls independently. Content column max 880 px, centered in the remaining space.
- **Threads visibility.** The main area background is transparent so the threads show. Each section is its own opaque `--surface` panel with a 24 px gap between panels. The threads show in the gaps, the side gutters, and the empty state. Text never sits directly on threads.

**Below 1024 px.** The sidebar becomes a drawer. A 56 px top bar shows the menu button, the mark, and the selected extension name. The drawer is a modal dialog: slides in from the left, focus is trapped, Esc and backdrop click close it, and focus returns to the menu button. Selecting an extension closes it.

**Below 600 px.** Panels go full width with 16 px side margins. The version selectors stack vertically. Touch targets are at least 44 px high.

---

## 6. Threads background (the main visual)

Recreate the reference as generated code in `js/threads.js`. Do not ship the reference image.

**Element.** One `<canvas id="threads" aria-hidden="true">`, `position: fixed; inset: 0; z-index: -1; pointer-events: none`.

**Geometry (normalized coordinates, u runs 0 to 1 across the canvas).**
- Bundle centerline `c(u)`: a diagonal from lower left (u=0, y=0.85) to upper right (u=1, y=0.15), plus a gentle S-curve `0.06 * sin(2π(0.8u + t/T))`.
- Bundle width `w(u) = 0.03 + 0.5 * (u - 0.45)^2`. This is narrow near u=0.45, where strands bunch into a bright band, and fans out toward both ends, as in the reference.
- Strand i has a fixed spread `s_i` in [-1, 1]. Its y is `c(u) + s_i * w(u) + 0.015 * sin(2π(f_i u + t/T_i + φ_i))`.
- Strand count: 18 on desktop, 8 below 600 px.

**Rendering.**
- Sample 60 points per strand, draw as a smooth quadratic path.
- Two passes per strand: a glow pass (line width 6, alpha ×0.15) and a core pass (line width 1.2).
- Alpha: `0.06 + 0.3 * (1 - |s_i|)^2`, multiplied by an edge fade `sin(πu)^0.8`. This fades the strands to near-black at the canvas edges without using a gradient.
- Color by `|s_i|`: below 0.25 use `--thread-4`, below 0.5 `--thread-3`, below 0.75 `--thread-2`, else `--thread-1`. Read these from CSS custom properties.
- Cap the device pixel ratio at 1.5. Resize with a 150 ms debounce.

**Motion.** `T` and each `T_i` are between 20 and 30 seconds. Cap at 30 fps. Pause when `document.hidden`. With `prefers-reduced-motion: reduce`, draw one static frame and stop the loop.

**Fallbacks.** No canvas support: render a static inline SVG of the same strands.

**Never.** Grain, noise, particles, cursor reaction, scroll reaction, strong neon glow, or any change that makes data harder to read. Verify the empty state against the reference image side by side and report the differences.

---

## 7. Dashboard sections (right panel, in this order)

Each section is an opaque panel with a 12 px uppercase label and its own loading, error, and empty states.

### 7.1 Identity
Large extension logo (96 px, in a `--surface-2` tile, `object-fit: contain`). If there is no icon, show a tile with the first letter of the name, not a fake logo. Then `<h1>` name, a line "Browser · v2.4.0" (version in mono), a short description if available, and developer or other metadata only when the API returns it. Anything unavailable is omitted, not guessed.

### 7.2 Risk gauge
- SVG semicircle, viewBox `0 0 240 140`, center (120, 120), radius 100, stroke 14.
- Three **flat** arc segments with 1.5 degree gaps: green 0 to 35, amber 35 to 70, red 70 to 100. Take the thresholds from the API (`thresholds`), not constants.
- Arc point math: for score s, `θ = π * (1 - s/100)`, `x = 120 + 100 * cos θ`, `y = 120 - 100 * sin θ`.
- Needle: a line from the center, rotated by `s * 1.8 - 90` degrees (0 points left, 50 up, 100 right). Set the angle through `el.style.setProperty('--needle', ...)`, transitioned in CSS.
- Tick labels 0, 35, 70, 100 in 12 px muted.
- Under the gauge: "Risk score: **72** / 100" with the number in mono at 28 px, the level word with its chip, and the line "Permission risk. This does not show that the extension is malicious."
- **Main contributors:** a short list from `assessment.breakdown` (top 3). Never show a score without it.
- Accessibility: wrapper has `role="img"` and `aria-label="Permission risk 72 of 100, high"`.
- Animation: needle and number run 800 to 1200 ms when a different extension is selected. The number counts up with `requestAnimationFrame`. Reduced motion: jump to the value.

### 7.3 About
Description text with an origin line: "From the manifest", "From the store listing", or "No description available". Verified and unavailable information must be visibly distinct. Add `Developer` and similar rows only when present.

### 7.4 Permissions
- Three groups, each with its own heading and count: **API permissions**, **Host permissions**, **Optional permissions** (only if present). Never mix API and host.
- Row: mono name on the left; on the right the risk chip. Below the name, a muted status in words: Justified, Needs review, Potentially excessive, or Unknown.
- Sort by weight descending, then name.
- Each row is a `<button>` with `aria-expanded` and `aria-controls`. Expanding reveals three labeled blocks: **What it allows**, **Why an extension might need it**, **AEGIS assessment** (with the evidence as a list). Expand and collapse over 200 ms (grid-rows technique), instant under reduced motion.
- Empty group: "No permissions of this type."

### 7.5 Version comparison
- Two `<select>`s labeled "Older version" and "Newer version", with an arrow between them. Default to the two newest snapshots. Prevent selecting the same version on both sides.
- Fewer than two snapshots: replace the controls with "Version comparison is unavailable. AEGIS has only one saved snapshot of this extension." Never show a zero or an empty diff.
- Result summary line: "3 added, 1 removed, 12 retained, 1 broadened" and "Risk score 41 to 72".
- Separate API, host, and optional groups. Within each, four row styles:
  - **Added:** amber tinted row (`rgba(245,158,11,.14)` on `--surface`), "Added" label, listed first.
  - **Broadened** (host scope): amber tinted row showing `old pattern -> new pattern` and the API's explanation.
  - **Retained:** neutral row, small green dot, "Retained" label.
  - **Removed:** muted grey text, strikethrough not used, "Removed" label.
- Changing a selector aborts the previous request and shows a loading state for this section only.

### 7.6 Permission creep
- One of exactly three outcomes, from the API, shown as a status word with a dot: "No significant permission creep detected", "Permission changes require review", "Significant increase in assessed permission exposure".
- Then: summary paragraph; lists of added, removed, broadened; "What the added access could allow"; "Fit with declared purpose"; "Risk score: old to new"; and **"What cannot be concluded"** (always shown, from `limitations`).
- Single snapshot: show "Baseline not available." Never show a creep score of zero.
- Never use wording that calls an extension malicious or suspicious on the basis of additions alone.

### 7.7 Optional "Analyze with AI"
Build the button and the result view now, but render the button only when `capabilities.ai_analysis` is true. Call `POST /api/extensions/{id}/analyze`. Show the returned purpose, per-permission status, reason, evidence, and caveat. Label the block "AI-assisted explanation. It does not change the risk score." If the call fails or AI is unavailable, show a plain notice and leave the rest of the page untouched. Do not display model confidence as a percentage.

### 7.8 Sidebar list
- Row: 32 px icon (letter tile fallback), name (single line, ellipsis), browser name in muted below, and on the right a risk word (LOW, MED, HIGH) with a 40 x 4 px bar filled to the score. The bar width is set with `style.setProperty('--score', n)`, and animates over 600 ms on first render.
- Search: `role="search"`, label "Search extensions", filters name and browser client-side, a clear button, and an `aria-live="polite"` count ("4 extensions"). No matches: "No extensions match your search."
- Keyboard: Tab enters the list, Up and Down move between rows, Enter selects. Use a roving tabindex.
- Selecting updates the main panel without a reload and sets `location.hash` to `#/ext/<id>`. On load, read the hash, validate the id against `^[A-Za-z0-9._:-]{1,128}$`, and select it if it exists.

---

## 8. Motion table (nothing else may animate)

| Element | Effect | Duration |
|---|---|---|
| Threads | slow drift | 20 to 30 s loops |
| Main panel, first load only | fade plus 8 to 12 px upward move | 400 to 600 ms |
| Selected row | background color change | 220 ms |
| Gauge needle and number | ease to value | 800 to 1200 ms |
| Sidebar risk bar | width to value | 600 ms |
| Permission detail | expand and collapse | 200 ms |
| Drawer | slide | 250 ms |

No scroll-triggered animation of any kind. No IntersectionObserver reveals. `prefers-reduced-motion: reduce` turns off every row above (threads become a still frame, values jump). Put all of it in `motion.css` and `threads.js`, and test with the setting on.

---

## 9. API client and contract v1

`api.js` is the only file that calls `fetch`. It uses relative URLs, `credentials: 'same-origin'`, an `AbortController` per section, a 10 s timeout, and returns parsed JSON or throws `ApiError {code, message, status, requestId}`. A 401 dispatches a `aegis:unauthorized` event (Part 3 will listen to it) and does nothing else.

If the existing backend already has routes, adapt `api.js` to them and tell me where the shapes differ. Otherwise this is the contract that Part 2 will implement. Keep field names exactly.

```jsonc
// GET /api/extensions
{ "source": "live" | "imported" | "fixture",
  "extensions": [ { "id": "string", "name": "string", "browser": "Google Chrome",
                    "version": "2.4.0", "icon_url": "string|null",
                    "risk_score": 72, "risk_level": "low|medium|high" } ] }

// GET /api/extensions/{id}
{ "id": "...", "name": "...", "browser": "...", "version": "...", "icon_url": null,
  "developer": "string|null",
  "description": { "text": "string|null", "origin": "manifest|store|unavailable" },
  "capabilities": { "ai_analysis": false },
  "assessment": { "risk_score": 72, "risk_level": "high",
                  "thresholds": { "low_max": 34, "mid_max": 69 },
                  "api_score": 60, "host_score": 85, "max_weight": 5,
                  "critical_flags": ["string"],
                  "breakdown": [ { "label": "history", "contribution": 14 } ],
                  "formula_version": "1" } }

// GET /api/extensions/{id}/permissions
{ "api": [Perm], "host": [Perm], "optional": [Perm] }
// Perm: { "name": "history", "kind": "api|host|optional_api|optional_host",
//         "risk_label": "low|medium|high|critical", "weight": 4,
//         "status": "justified|needs_review|potentially_excessive|unknown",
//         "allows": "string", "legitimate_use": "string",
//         "assessment": "string", "evidence": ["string"] }

// GET /api/extensions/{id}/versions
{ "versions": [ { "version": "2.4.0", "captured_at": "2026-09-30T10:00:00Z" } ] }

// GET /api/extensions/{id}/compare?from=2.3.0&to=2.4.0
{ "from": "2.3.0", "to": "2.4.0", "score_from": 41, "score_to": 72,
  "api":      { "added": [Item], "removed": [Item], "retained": [Item] },
  "host":     { "added": [Item], "removed": [Item], "retained": [Item],
                "broadened": [ { "from_pattern": "string", "to_pattern": "string",
                                 "explanation": "string" } ] },
  "optional": { "added": [Item], "removed": [Item], "retained": [Item] } }
// Item: { "name": "string", "risk_label": "low|medium|high|critical" }

// GET /api/extensions/{id}/creep
{ "available": true, "reason": null,           // or false + "baseline_not_available"
  "outcome": "no_significant|needs_review|significant_increase",
  "summary": "string", "added": [Item], "removed": [Item],
  "broadened": [ { "from_pattern": "...", "to_pattern": "...", "explanation": "..." } ],
  "could_allow": ["string"],
  "alignment": { "status": "consistent|unclear|inconsistent", "text": "string" },
  "score_from": 41, "score_to": 72, "limitations": ["string"] }

// POST /api/extensions/{id}/analyze   (only if capabilities.ai_analysis)
{ "available": true, "purpose": "string",
  "items": [ { "name": "string", "status": "...", "reason": "string", "evidence": ["string"] } ],
  "caveat": "string" }

// Any error
{ "error": { "code": "string", "message": "string", "request_id": "string" } }
```

Map `outcome` to the exact three display sentences on the frontend. Map `risk_label` to the chip words.

---

## 10. States and the dev mock API

**Every section** handles four states independently: loading (static text such as "Loading permissions", no looping shimmer), empty, error with a Retry button, and success. One failing section must not break the others. When the user switches extensions quickly, abort in-flight requests so a stale response never overwrites the current one.

**Mock API (dev only).** Because the real backend arrives in Part 2, build `dev/mock-api/serve.py` using only the Python standard library:

- Binds to `127.0.0.1` only. Serves `Frontend/` at `/` and fixtures at `/api/...` following contract v1. Command: `python dev/mock-api/serve.py`.
- Sends the strict CSP from the master prompt on every response, so the frontend is built under it from day one: `default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`. Zero CSP violations in the console is an acceptance criterion.
- Every list response has `"source": "fixture"`. When the UI sees that, it shows a persistent banner: "Sample data from the dev mock API. These are not real extensions."
- Supports `?delay=3000` to simulate slow responses and `?fail=permissions` to force a 500 for one section.
- Fixtures use obviously fictional names ("Sample Notes Sync", "Sample Tab Manager"), never real products. Include: one extension with 3 snapshots and strong creep; one with a single snapshot (baseline not available); one with host broadening from a single site to `<all_urls>`; one with no description; one with empty permissions; one with no icon; one whose name is `<img src=x onerror=alert(1)>`; one with a 200 character name; one with a right-to-left name.
- Nothing under `Frontend/` may contain sample data. `dev/` is never served by the production app and Part 5 will verify its removal from deployment.

---

## 11. Accessibility

- Landmarks: skip link first, `<header>` (mobile bar), `<nav aria-label="Extensions">`, `<main>`. `<h1>` is the extension name. Section labels are `<h2>`. One heading level per nesting, no skips.
- After a selection finishes loading, announce it in a polite live region: "Loaded Sample Notes Sync, permission risk 72 of 100, high."
- Contrast: text 4.5:1 or better, UI components 3:1 or better. Compute and list the ratios for every text and surface pair in the final report.
- Keyboard only: every control reachable and operable, visible focus, drawer focus trap, no keyboard traps elsewhere.
- Works at 200% zoom with no horizontal scroll. Wide content (long patterns) scrolls inside its own `overflow-x: auto` container, never the page.
- Respect `prefers-reduced-motion`. Provide a visible text equivalent for everything the gauge shows.

---

## 12. Frontend security rules

These are required in this part, because AEGIS renders untrusted third-party manifest text.

- **No `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, or `new Function`.** Build DOM with `dom.js` only. `h()` sets text with `textContent` and refuses attributes that start with `on` and any `style` attribute string.
- No inline `<script>`, no inline `style=""` attributes, no inline event handlers. Set dynamic styles through `el.style.setProperty(...)` or classes. Never `setAttribute('style', ...)`.
- No third-party scripts, no CDN, no Google Fonts. Everything is served from `'self'`.
- Validate `icon_url` before use: only `https:` URLs or same-origin paths, or `data:image/png|jpeg|webp`. Anything else falls back to the letter tile. Set `referrerpolicy="no-referrer"`, use `addEventListener('error', ...)` for the fallback, and never render SVG icons from the API.
- Validate the id from the hash with the regex in 7.8 before it reaches `api.js`, and URL-encode ids and versions in request paths.
- Treat all API strings as untrusted text. Truncate display with CSS, not by slicing characters. Use `dir="auto"` on names and patterns so right-to-left text does not reorder surrounding UI.
- No `console.log` left behind. Errors shown to the user are generic; details go only to `requestId`.
- No tokens or secrets in the frontend. No `localStorage` of API data.

---

## 13. Banned patterns

Do not add any of these. Before finishing, search the final HTML, CSS, and JS for each and report the result.

- Purple-to-blue gradient, or any gradient in the UI
- Gradient hero text
- Emojis in headings (none anywhere in the UI)
- Inter everywhere
- Colored border cards
- Glassmorphism cards
- Low-contrast dark mode
- Three icon boxes in a row
- A badge above the headline
- Lucide icons everywhere
- Untouched shadcn UI
- Fade-in on scroll
- A cursor-following beam
- Buttons that fade on hover
- Inconsistent spacing (only `--s-1` to `--s-7`)
- Em dashes everywhere (none in UI copy)
- Generic buzzword copy ("seamless", "powerful", "robust", "cutting-edge", "AI-powered")
- Serif italic accents
- Space Grotesk with Instrument Serif
- Grain over a gradient

Also banned in this part: autonomous AI agents, extra pages, extra statistics cards, decorative widgets, and any scoring code in JavaScript.

---

## 14. Build order (test after each step)

1. Tokens, base CSS, fonts, logo, and the static HTML shell with landmarks. Check the empty state against the threads reference.
2. `threads.js`: static frame first, then motion, then pause and reduced-motion handling.
3. `dom.js`, `state.js`, `api.js`, then the mock API with the CSP header.
4. Sidebar: list, search, selection, hash, keyboard.
5. Identity and gauge, including the animation and accessible text.
6. About and permissions accordion.
7. Version comparison, including single-snapshot and broadening cases.
8. Permission creep and the optional AI block.
9. Responsive drawer and the three breakpoints.
10. States: loading, empty, error, retry, abort on fast switching, slow network (`?delay=3000`), forced failures.
11. Motion pass against the table in section 8, then reduced-motion pass.
12. Accessibility pass and contrast table.
13. Security pass: grep for banned APIs, confirm zero CSP violations, run the XSS fixture and confirm the name renders as plain text.

---

## 15. Acceptance criteria and deliverables

Done when all of these are true:

- The list and every section show data from `api.js` only. Nothing fabricated in `Frontend/`.
- Selecting an extension updates logo, name, browser, version, description, gauge, and permissions without a reload.
- The gauge shows the API score with accessible text and the main contributors.
- API, host, and optional permissions are visibly separate, and rows expand with the three blocks.
- Two snapshots compare correctly; added, removed, retained, and broadened are all identified; one snapshot shows "unavailable" and "Baseline not available".
- Creep wording stays within the three approved outcomes and always shows "What cannot be concluded".
- The page works with the AI button hidden, and with AI failing.
- The threads match the reference mood, run at 20 to 30 second loops, pause when hidden, and stop under reduced motion.
- Layout works at 360, 390, 768, and 1280 px, and at 200% zoom.
- Zero CSP violations, zero banned patterns, zero console errors.

**Report back with:** the changed files, screenshots at 360, 390, 768, and 1280 px (and one with reduced motion on), the contrast table, the banned-pattern search results, the security-pass results, assumptions, known limitations, and the exact command to run the mock API. Do not describe anything as working unless you ran it.

---

## Appendix A: `aegis-mark.svg`

Use exactly this file. It is also attached as `aegis-mark.svg`.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 765" role="img" aria-label="AEGIS" xmlns:c2pa="http://c2pa.org/manifest"><metadata><c2pa:manifest>AAAWgmp1bWIAAAAeanVtZGMycGEAEQAQgAAAqgA4m3EDYzJwYQAAABZcanVtYgAAAEdqdW1kYzJtYQARABCAAACqADibcQN1cm46YzJwYTo0OWViYjc4Zi1lZWJiLTRiODMtODVlYy04MDZlMTIxN2I5MTUAAAADl2p1bWIAAAApanVtZGMyYXMAEQAQgAAAqgA4m3EDYzJwYS5hc3NlcnRpb25zAAAAALxqdW1iAAAARGp1bWRjYm9yABEAEIAAAKoAOJtxE2MycGEuaW5ncmVkaWVudC52MwAAAAAYYzJzaLrpfcjuUJ2fRpjo7k41tbsAAABwY2JvcqNpZGM6Zm9ybWF0bWltYWdlL3N2Zyt4bWxqaW5zdGFuY2VJRHgseG1wOmlpZDpjYjVjMjUzNi1jYzZmLTRjMjItYTUwNC0zZjc0NjZmY2VhZGFscmVsYXRpb25zaGlwaHBhcmVudE9mAAAB4mp1bWIAAABBanVtZGNib3IAEQAQgAAAqgA4m3ETYzJwYS5hY3Rpb25zLnYyAAAAABhjMnNoSxBtlQIAo/xRm0iztNu0nwAAAZljYm9yomdhY3Rpb25zgqJmYWN0aW9ua2MycGEub3BlbmVkanBhcmFtZXRlcnOha2luZ3JlZGllbnRzgaJjdXJseC1zZWxmI2p1bWJmPWMycGEuYXNzZXJ0aW9ucy9jMnBhLmluZ3JlZGllbnQudjNkaGFzaFggzEetSWfPU5Rl5VOpK1VP+Og3ezkUfmlQUw5N18WfsrmkZmFjdGlvbngdY29tLmFudGhyb3BpYy5jbGF1ZGUucHJvdmlkZWRqcGFyYW1ldGVyc6F4H2NvbS5hbnRocm9waWMub3JpZ2luLWNvbmZpZGVuY2VndW5rbm93bmtkZXNjcmlwdGlvbnhmQ2xhdWRlIHByb3ZpZGVkIHRoaXMgZmlsZSBhdCB0aGUgcmVxdWVzdCBvZiBhIHVzZXIgYW5kIG1heSBoYXZlIGNyZWF0ZWQgb3IgbW9kaWZpZWQgdGhlIGZpbGUgY29udGVudHMubXNvZnR3YXJlQWdlbnShZG5hbWVmQ2xhdWRlcmFsbEFjdGlvbnNJbmNsdWRlZPUAAADIanVtYgAAAEBqdW1kY2JvcgARABCAAACqADibcRNjMnBhLmhhc2guZGF0YQAAAAAYYzJzaGjk42WPxSrmCncrTydG5o8AAACAY2JvcqVjYWxnZnNoYTI1NmNwYWRNAAAAAAAAAAAAAAAAAGRoYXNoWCBDugYhWld+gWqxp17aWDTKdiNFUGM3JHq6NfFpMFykw2RuYW1lbmp1bWJmIG1hbmlmZXN0amV4Y2x1c2lvbnOBomVzdGFydBibZmxlbmd0aBkeBAAAAj5qdW1iAAAAJ2p1bWRjMmNsABEAEIAAAKoAOJtxA2MycGEuY2xhaW0udjIAAAACD2Nib3KlY2FsZ2ZzaGEyNTZpc2lnbmF0dXJleE1zZWxmI2p1bWJmPS9jMnBhL3VybjpjMnBhOjQ5ZWJiNzhmLWVlYmItNGI4My04NWVjLTgwNmUxMjE3YjkxNS9jMnBhLnNpZ25hdHVyZWppbnN0YW5jZUlEeCx4bXA6aWlkOmM4NmMxYjM2LTJjY2ItNDcwZi04Nzc3LWY1YWI0NTY2MjEwNnJjcmVhdGVkX2Fzc2VydGlvbnODomN1cmx4LXNlbGYjanVtYmY9YzJwYS5hc3NlcnRpb25zL2MycGEuaW5ncmVkaWVudC52M2RoYXNoWCDMR61JZ89TlGXlU6krVU/46Dd7ORR+aVBTDk3XxZ+yuaJjdXJseCpzZWxmI2p1bWJmPWMycGEuYXNzZXJ0aW9ucy9jMnBhLmFjdGlvbnMudjJkaGFzaFggOMedQGHLFoU5qRHPkIjXwcbOoLba6E9BPLrZi6HxpeSiY3VybHgpc2VsZiNqdW1iZj1jMnBhLmFzc2VydGlvbnMvYzJwYS5oYXNoLmRhdGFkaGFzaFgg1xgucf4vfrEdnGlR+azcvRgbLHD6y+3QAzcmyRgQsnF0Y2xhaW1fZ2VuZXJhdG9yX2luZm+jZG5hbWVvQW50aHJvcGljIEZpbGVzZ3ZlcnNpb25lMS4wLjBrc3BlY1ZlcnNpb25lMi40LjAAABA4anVtYgAAAChqdW1kYzJjcwARABCAAACqADibcQNjMnBhLnNpZ25hdHVyZQAAABAIY2JvctKEWQISogEmGCFZAgowggIGMIIBjaADAgECAhRA5aAK7sI50L64g/oGQgU9Z1UTADAKBggqhkjOPQQDAzBJMRcwFQYDVQQKEw5BbnRocm9waWMsIFBCQzEuMCwGA1UEAxMlQW50aHJvcGljIENvbnRlbnQgQ3JlZGVudGlhbHMgUm9vdCBDQTAeFw0yNjA4MDcxODQzNTZaFw0yODA4MDYxOTQzNTZaMEQxFzAVBgNVBAoTDkFudGhyb3BpYywgUEJDMSkwJwYDVQQDEyBBbnRocm9waWMgQ2xhdWRlIENvbnRlbnQgU2lnbmluZzBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABJh6CmvLUBgFFNU0vUKlOVtE6djd17L5SuwX0LemFisBM3dkd/3cyjxFA3Qo5S46fX0/ihY0VZ7mfb9KF703t5OjWDBWMA4GA1UdDwEB/wQEAwIHgDAVBgNVHSUEDjAMBgorBgEEAYPoXgIBMAwGA1UdEwEB/wQCMAAwHwYDVR0jBBgwFoAUzlHiBIFOZFsj+OPEz5o+nMHXXMIwCgYIKoZIzj0EAwMDZwAwZAIwMXMdFJ4BetLLVY7ORuE9noqbbAZOZn/aArXyTwFAZfKrPzxF2vPoJNf1+UCdg1XGAjBwX1zd9WGqYkqmL5SFqw1QySjr1zJfpJM9+1rdDwSPLMOPOjKuiXjoU/pUUeG9RwmhY3BhZFkNngAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPZYQF9ifjHJePU4Kgh6eEYgO1cVzZars9NoIPJCS7lACK612KjsqLXarmjcRvByF2GipLbWZiwtk4yUf6C3/DyLmn4=</c2pa:manifest></metadata>
  <title>AEGIS</title>
  <defs>
    <clipPath id="aegis-clip-left"><polygon points="-20,103 200,323 200,620 -20,620"/></clipPath>
    <clipPath id="aegis-clip-right"><polygon points="380,503 780,103 780,800 380,800"/></clipPath>
    <clipPath id="aegis-clip-hook"><polygon points="-20,400 380,400 380,900 -20,900"/></clipPath>
  </defs>
  <g fill="none" stroke-width="58" stroke-linejoin="miter" stroke-miterlimit="6">
    <path stroke="#5B5BF0" d="M118 545C75 430 32 300 32 155A126 126 0 0 0 158 29H602A126 126 0 0 0 728 155C745 330 520 640 380 730C310 690 215 640 180 575"/>
    <path stroke="#4747E0" clip-path="url(#aegis-clip-left)" d="M118 545C75 430 32 300 32 155V100"/>
    <path stroke="#6B6BF5" clip-path="url(#aegis-clip-right)" d="M728 100V155C745 330 520 640 380 730C310 690 215 640 180 575"/>
    <path stroke="#8B8BFF" clip-path="url(#aegis-clip-hook)" d="M728 155C745 330 520 640 380 730C310 690 215 640 180 575"/>
    <path stroke="#5B5BF0" d="M120 490Q250 380 380 272Q520 372 635 462"/>
  </g>
  <circle cx="180" cy="575" r="29" fill="#8B8BFF"/>
  <path fill="#D9D9FF" d="M290.3 501A90 90 0 0 1 373 418.3V501Z"/>
  <path fill="#D9D9FF" d="M387 418.3A90 90 0 0 1 469.7 501H387Z"/>
  <path fill="#9A9AFF" d="M469.7 515A90 90 0 0 1 387 597.7V515Z"/>
  <path fill="#9A9AFF" d="M373 597.7A90 90 0 0 1 290.3 515H373Z"/>
</svg>
```
