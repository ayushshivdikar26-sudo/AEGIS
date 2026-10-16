# AEGIS Part 2a: Core analysis modules (prompt for Antigravity)

## 0. Context and rules

AEGIS is a browser-extension Permission Creep Auditor. Source of truth: `AEGIS_Handover_Document.md` (sections 4, 5, 7 matter most here). Stack, security rules, and banned patterns are in `AEGIS_Antigravity_Build_Prompt.md`. Part 1 (frontend) is done and defines API contract v1.

| Step | Scope |
|---|---|
| **2a (this prompt)** | `manifest_parser`, `permission_rules`, `risk_scoring`, `version_comparison` as pure Python |
| 2b | Supabase database |
| 2c | FastAPI connecting frontend and backend |
| 2d | `justification_checker`, `ai_analyzer` |
| 3 | Testing and security checks |

**Do only 2a.** No FastAPI, no Supabase, no network, no Flask, no SQLite in this step. These modules must be plain functions over plain data so that every later step can import them unchanged.

**Rules.** Modify the existing codebase and keep working behaviour. If the repository already has scoring or parsing code, port its logic and prove identical results with tests before deleting anything. Never invent extension data, permissions, or weights you cannot justify. Scores are deterministic and reproducible. Do not claim anything works unless you ran it. Never ask me to paste secrets into chat.

---

## 1. Phase 0: inspect and plan (do this first)

Report the current state: where parsing, scoring, and comparison logic lives, its inputs and outputs, and any tests. Note whether existing scoring uses the handover formulas. Then give a file-by-file plan. **Stop and wait for my approval before editing.**

---

## 2. Layout

Adapt to the repository. Suggested:

```text
Backend/
├── core/
│   ├── __init__.py
│   ├── models.py               # frozen Pydantic v2 models shared by all core modules
│   ├── manifest_parser.py
│   ├── host_patterns.py        # match-pattern parsing, coverage, scope tiers
│   ├── permission_rules.py     # knowledge base loader + weight/label/explanation lookup
│   ├── risk_scoring.py
│   └── version_comparison.py
├── data/
│   ├── permission_knowledge.json   # version-controlled knowledge base
│   └── scoring_config.json         # every constant used by scoring and creep rules
tests/core/                     # pytest, golden fixtures in tests/fixtures/manifests/
docs/SCORING.md
```

Rules for `core/`: no imports from FastAPI, Supabase, httpx, or anything that does I/O except reading the two JSON files at start-up. All functions are pure. Python 3.11+, full type hints, `ruff` and `mypy` clean.

---

## 3. `manifest_parser.py`

`parse_manifest(raw: bytes | str | dict, *, messages: dict | None = None) -> ParsedManifest`

**Output fields**
`manifest_version` (2 or 3), `name`, `version`, `version_key` (list of ints or null), `description`, `name_is_placeholder`, `description_is_placeholder`, `default_locale`, `api_permissions`, `host_permissions`, `optional_api_permissions`, `optional_host_permissions`, `content_script_matches`, `features` (set of structural keys present, see below), `sha256` (of the original bytes), `warnings` (list of `{code, message}`).

**Behaviour**
- Handle Manifest V2 and V3.
  - V3: `permissions` is API only, `host_permissions` is hosts, `optional_permissions` is API, `optional_host_permissions` is hosts.
  - V2: `permissions` mixes API names and host patterns, and so can `optional_permissions`. Split them with `is_match_pattern()` from `host_patterns.py`.
  - A host pattern found in a V3 `permissions` array is treated as a host and gets a warning `host_in_permissions`.
- Treat `content_scripts[].matches` as host access. Keep it in `content_script_matches`; scoring and comparison include it in the host set and label its source.
- `features`: record which of these top-level keys exist, because the justification checker (2d) uses them as structural evidence: `background`, `action`, `browser_action`, `page_action`, `side_panel`, `devtools_page`, `omnibox`, `commands`, `options_page`, `options_ui`, `content_scripts`, `declarative_net_request`, `chrome_url_overrides`, `web_accessible_resources`, `externally_connectable`, `storage`, `sidebar_action`.
- Localized placeholders: if `name` or `description` is `__MSG_<key>__`, resolve it from `messages` (a parsed `messages.json`, key lookup case-insensitive, verify in Chrome docs). If unresolved, keep the raw text, set the placeholder flag, and warn `unresolved_placeholder`.
- Normalization: strip whitespace, drop empty strings, dedupe, sort lexicographically for determinism. NFC-normalize text. Remove bidirectional control characters (U+202A to U+202E, U+2066 to U+2069) and other control characters from display fields and warn `bidi_controls_removed`.
- Version: keep the original string. `version_key` parses Chrome-style versions (1 to 4 dot-separated integers, 0 to 65535) and is null for anything else.

**Strictness (this input is untrusted)**
- Strict JSON only. Reject: invalid JSON (`not_json`), non-object top level (`not_object`), input over `max_bytes` (default 1,048,576, `too_large`), nesting deeper than 32 (`too_deep`, also catch `RecursionError`), **duplicate keys at any level** (`duplicate_key`, because duplicates can make two parsers disagree), `NaN` and `Infinity` (`not_json`). Accept a UTF-8 BOM.
- Missing or non-string `version` (`missing_version`), `manifest_version` not 2 or 3 (`invalid_manifest_version`), wrong field types (`invalid_field_type`), more than 500 items in any permission array (`too_many_items`), any string over 2,048 characters (`string_too_long`).
- Errors are a `ManifestError(code, message)`. Messages may name fields but never echo raw input values.

---

## 4. `host_patterns.py`

This is the hardest part and the core of broadening detection. Check MDN "Match patterns" and the Chrome match-pattern docs before coding, and cite them in comments.

- `parse_match_pattern(s) -> MatchPattern | None` handling `<all_urls>`, `scheme://host/path`, schemes `*`, `http`, `https`, `file`, `ftp`, `ws`, `wss`, hosts `*`, `*.domain`, exact host, and path globs with `*`. An optional port is parsed and kept. Invalid patterns return `None`.
- `is_match_pattern(s) -> bool` (used by the manifest parser).
- `covers(a, b) -> bool`: True only when every URL matched by `b` is matched by `a`. Rules: `<all_urls>` covers everything; scheme `*` covers http and https; `*` host covers any host; `*.d` covers `d` and all subdomains; path `/*` covers any path; a path ending in `*` covers any path starting with its prefix; otherwise paths must be equal. **When unsure, return False.** Over-flagging is safer than under-flagging.
- `scope_tier(p) -> Tier` with these tiers, ordered from narrow to wide: `single_host`, `domain_wide` (wildcard subdomain of one registrable domain), `suffix_wide` (for example `*://*.com/*`, `*://*.co.uk/*`), `all_hosts_partial_path` (host `*` but path is not `/*`), `file_access`, `all_sites` (`<all_urls>`, `*://*/*`, `http://*/*`, `https://*/*`). Use a bundled, pinned Public Suffix List package that works offline to tell registrable domains from suffixes, and justify the dependency in the plan.
- `describe(p) -> str`: a short plain-English description of what the pattern allows, used later in explanations.

---

## 5. `permission_rules.py` and the knowledge base

`data/permission_knowledge.json` is the single source of truth for weights and explanations. It is version-controlled JSON, not a database table.

```jsonc
{
  "schema_version": 1,
  "knowledge_version": "2026.10.1",
  "api_permissions": {
    "history": {
      "weight": 4,
      "allows": "Read and change the browser history.",
      "legitimate_use": "History search, productivity dashboards, or cleanup tools.",
      "source": "https://developer.chrome.com/docs/extensions/reference/api/history",
      "reviewed": true
    }
  },
  "host_tiers": {
    "all_sites": { "weight": 5, "allows": "...", "legitimate_use": "..." }
  }
}
```

(2d adds `purposes`, `structural_evidence`, and `narrower_alternative`. Leave room for them and make the loader ignore unknown keys.)

**Starter weights.** These are heuristics for me to review, not official ratings. Verify every permission name and meaning against the current Chrome and MDN documentation, drop obsolete ones, and set `"reviewed": false` for anything you could not verify.

| Weight | Label | Permissions |
|---|---|---|
| 5 | critical | `debugger`, `nativeMessaging`, `proxy`, `management`, `webRequestBlocking` |
| 4 | high | `history`, `cookies`, `tabs`, `webRequest`, `clipboardRead`, `pageCapture`, `tabCapture`, `desktopCapture`, `privacy`, `declarativeNetRequestWithHostAccess`, `identity.email`, `webAuthenticationProxy` |
| 3 | medium | `bookmarks`, `downloads`, `downloads.open`, `geolocation`, `contentSettings`, `topSites`, `sessions`, `scripting`, `webNavigation`, `identity`, `browsingData`, `declarativeNetRequestFeedback`, `printing`, `printerProvider` |
| 2 | low | `notifications`, `offscreen`, `declarativeNetRequest`, `declarativeContent`, `search`, `gcm`, `favicon`, `system.cpu`, `system.memory`, `system.storage`, `system.display`, `ttsEngine`, `background`, `loginState`, `readingList`, `tabGroups`, `clipboardWrite` |
| 1 | low | `storage`, `unlimitedStorage`, `alarms`, `activeTab`, `contextMenus`, `idle`, `sidePanel`, `fontSettings`, `power`, `tts` |

Host tier weights: `all_sites` 5, `file_access` 4, `suffix_wide` 4, `all_hosts_partial_path` 4, `domain_wide` 2, `single_host` 1.

**API**
- `info_for_api(name) -> PermissionInfo`, `info_for_host(pattern) -> PermissionInfo`. `PermissionInfo` has `name`, `kind`, `weight`, `risk_label`, `allows`, `legitimate_use`, `source_url`, `known`, `tier` (hosts only).
- Unknown API permission: `known=False`, default weight from `scoring_config.json` (start at 3), and it is surfaced in `unrecognized`. Invalid host pattern: same treatment.
- Weight to label mapping from config: 1 and 2 are `low`, 3 `medium`, 4 `high`, 5 `critical`.
- The loader validates the JSON with Pydantic and fails fast with a clear message on any schema error. `knowledge_version` is exposed.

---

## 6. `risk_scoring.py`

Everything numeric lives in `data/scoring_config.json`, and `formula_version` is `"1"`. Scores are heuristics, not official browser ratings.

**Definitions** (per set: API set `A`, host set `H`; host set = `host_permissions` plus V2 hosts plus `content_script_matches`)
- Set score, from the handover: `R = 100 * sum(w_i) / (5 * n)`, and `R = 0` when `n = 0`.
- Blend: if both sets are non-empty, `S_base = 0.5 * R_api + 0.5 * R_host`. If only one is non-empty, `S_base` is that set's score. If both are empty, `S_base = 0`.
- Averages hide single dangerous items, so apply floors: if any item has weight 5, `S >= 70`; else if any has weight 4, `S >= 40`. Final `S = round_half_up(max(S_base, floor))`, clamped to 0 to 100. Use `floor(x + 0.5)`, never banker's rounding.
- Level thresholds from config: low 0 to 34, medium 35 to 69, high 70 to 100.
- **Requested vs optional.** `risk_score` uses requested permissions only. `potential_score` is the same function with optional permissions included at full weight. Report both.

**Output (`Assessment`), matching contract v1 plus additive fields**
`formula_version`, `knowledge_version`, `risk_score`, `risk_level`, `thresholds {low_max, mid_max}`, `api_score`, `host_score` (each rounded to 1 decimal), `max_weight`, `critical_flags` (readable strings, one per weight-5 item), `breakdown`, `potential_score`, `notes`, `unrecognized`.

**Breakdown must add up.** Each permission's contribution is its exact share of `S_base`: `0.5 * 100 * w_i / (5 * n)` when both sets exist (use 1.0 instead of 0.5 when only one set exists). If a floor applied, add one entry `{label: "High-weight permission floor", contribution: floor - S_base, kind: "floor"}`. The contributions then sum to the score before rounding. Sort by contribution descending. Each entry: `label`, `contribution` (1 decimal), `kind` (`api`, `host`, `floor`).

**Golden examples (these must pass as tests)**

1. `api = [storage, alarms, history]`, `host = [https://example.com/*]`.
   `R_api = 100*6/15 = 40.0`, `R_host = 100*1/5 = 20.0`, `S_base = 30.0`, floor 40 (weight 4 present), so `risk_score = 40`, medium. Breakdown: history 13.3, host 10.0, storage 3.3, alarms 3.3, floor +10.0.
2. `api = [storage]`, `host = [<all_urls>]`.
   `R_api = 20.0`, `R_host = 100.0`, `S_base = 60.0`, floor 70, so `risk_score = 70`, high. Breakdown: `<all_urls>` 50.0, storage 10.0, floor +10.0.
3. No permissions at all: `risk_score = 0`, low, note "This extension declares no permissions."

---

## 7. `version_comparison.py`

`compare(old: ParsedManifest, new: ParsedManifest) -> Comparison` and `assess_creep(comparison, *, alignment=None) -> CreepAssessment`.

**Comparison**
- Three groups: `api`, `host`, `optional` (optional API and optional host together, each item keeps its `kind`). Content-script matches are part of `host`, each item labeled with `source`.
- In each group: `added = new - old`, `removed = old - new`, `retained = new ∩ old`, by exact string.
- Host broadening: for every added host pattern `a` and every removed host pattern `o`, if `covers(a, o)` and `a != o`, emit `{from_pattern: o, to_pattern: a, from_tier, to_tier, explanation}`. The two patterns also remain in `added` and `removed`. Also flag an added pattern that is already covered by a retained pattern as `already_covered_by` (no new access in practice), so it is not over-reported.
- Items carry `name`, `risk_label`, `weight`, `kind`, and `source`.
- `score_from` and `score_to` come from `risk_scoring` using the same rules on both sides.

**Creep rules** (constants in `scoring_config.json`: `delta_review = 5`, `delta_significant = 15`)
- `significant_increase` if `delta >= 15`, or any added or broadened-to item has weight 5, or the level moved up into `high`.
- Else `needs_review` if `delta >= 5`, or any added item has weight 3 or more, or any broadening to a wider tier, or any added unrecognized permission.
- Else `no_significant`. Removals only, or low-weight additions with a small delta, land here.
- Output fields follow contract v1: `outcome`, `summary`, `added`, `removed`, `broadened`, `could_allow`, `alignment`, `score_from`, `score_to`, `limitations`. `could_allow` text comes from the knowledge base `allows` fields and `describe()`. Until 2d provides alignment, `alignment = {status: "unclear", text: "Purpose alignment has not been evaluated."}`.
- `limitations` always includes: the manifest lists requested capabilities, not proof that they were used; AEGIS does not inspect extension code; descriptions are claims, not proof of intent; optional permissions need runtime consent; scores are heuristics under formula version N.
- Wording rule: never describe an extension as malicious or suspicious. Use the three approved outcome phrases in the handover.

**Golden comparison.** Old: `api [storage, alarms]`, `host [https://example.com/*]`. New: `api [storage, alarms, history]`, `host [<all_urls>]`. Expect: api added `history`, retained `storage` and `alarms`; host added `<all_urls>`, removed `https://example.com/*`, one broadened entry from `single_host` to `all_sites`; `score_from = 20`, `score_to = 70`; outcome `significant_increase`.

---

## 8. Tests (required)

- `pytest`, no network. Coverage at least 90% on `core/`.
- Parser: valid V2 and V3 manifests, mixed V2 permissions, host in V3 `permissions`, placeholders resolved and unresolved, duplicate keys, deep nesting, huge input, NaN, BOM, wrong types, 501 items, bidi characters in names, empty permissions.
- Host patterns: a table of at least 60 pairs for `covers` and `scope_tier`, including `<all_urls>`, scheme `*`, subdomain wildcards, `*://*.co.uk/*`, `file:///*`, invalid patterns, and paths. Property tests with `hypothesis` (dev dependency only): `covers(a, a)` is always true, `<all_urls>` covers every valid pattern, and `covers` is transitive.
- Scoring: the three golden examples exactly, plus rounding edge cases, unknown permissions, optional vs requested, and determinism (same input gives byte-identical output, 100 runs).
- Comparison: the golden comparison, identical manifests, removals only, scheme broadening (`https` to `*`), path broadening, already-covered additions, reversed order, and each creep outcome branch.
- Fixtures are fictional extensions with clearly fictional names, kept in `tests/fixtures/`.

---

## 9. Deliverables and report

1. The modules, data files, and tests.
2. `docs/SCORING.md`: every formula, every constant and where it lives, the weight table, the creep rules, limitations, and how to change a weight safely.
3. A short summary: files changed, assumptions, permissions you could not verify (`reviewed: false`), known limitations, and the exact test command.

Do not describe anything as working unless you ran it.
