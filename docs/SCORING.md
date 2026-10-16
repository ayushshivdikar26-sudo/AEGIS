# AEGIS Scoring Specification & Methodology

**Formula Version:** `1`  
**Knowledge Base Version:** `2026.10.1`  
**Auditor Principle:** Minimal, explainable, transparent, deterministic.

---

## 1. Mathematical Scoring Formulation

AEGIS evaluates permission exposure across two primary dimensions:
1. **API Permissions ($A$):** Browser APIs declared in `permissions` (or V2 API names).
2. **Host Permissions ($H$):** Match patterns declared in `host_permissions`, V2 match patterns, and `content_scripts[].matches`.

### 1.1 Set Normalization
For a set of $n$ permissions where each capability $i$ has an integer weight $w_i \in [1, 5]$:

$$R = 100 \times \frac{\sum_{i=1}^n w_i}{5 \times n}$$

If $n = 0$, $R = 0.0$.

### 1.2 Base Blend Score ($S_{base}$)
- **Both sets non-empty:** $S_{base} = 0.5 \times R_{api} + 0.5 \times R_{host}$
- **Only API set present:** $S_{base} = R_{api}$
- **Only Host set present:** $S_{base} = R_{host}$
- **Both sets empty:** $S_{base} = 0.0$

### 1.3 High-Exposure Danger Floors
Averages can mask severe individual risks. AEGIS applies strict deterministic danger floors:
- If **any** requested capability has weight $5$: $\text{Floor} = 70$.
- Else if **any** requested capability has weight $4$: $\text{Floor} = 40$.
- Otherwise: $\text{Floor} = 0$.

### 1.4 Pre-Rounding and Final Score ($S$)
$$\text{Pre-round} = \max(S_{base}, \text{Floor})$$
$$S = \min(100, \max(0, \lfloor \text{Pre-round} + 0.5 \rfloor))$$

AEGIS uses standard arithmetic half-up rounding (`floor(x + 0.5)`), never banker's rounding.

---

## 2. Risk Levels & Thresholds

| Risk Level | Score Range | Meaning |
|---|---|---|
| **Low** | 0 – 34 | Standard low-exposure capabilities with minimal privacy impact |
| **Medium** | 35 – 69 | Moderate capabilities; accessing user data with defined bounds |
| **High** | 70 – 100 | Broad host access (`<all_urls>`), critical debugging, or proxy control |

Thresholds are defined in `Backend/data/scoring_config.json`.

---

## 3. Contribution Breakdown (FR-S7)

Every reported score is accompanied by an itemized breakdown whose contributions sum exactly to the pre-rounding score:
- **Both sets present:** Each item contributes $0.5 \times 100 \times w_i / (5 \times n) = 10 \times w_i / n$.
- **Single set present:** Each item contributes $1.0 \times 100 \times w_i / (5 \times n) = 20 \times w_i / n$.
- **Floor adjustment:** If $\text{Floor} > S_{base}$, a floor line item contributes $\text{Floor} - S_{base}$.

---

## 4. Host Scope Tiers

| Tier | Weight | Description |
|---|---|---|
| `single_host` | 1 | Single explicit domain (e.g. `https://example.com/*`) |
| `domain_wide` | 2 | Domain and subdomains of one registrable domain (e.g. `*://*.example.com/*`) |
| `suffix_wide` | 4 | Broad wildcard across a public suffix / TLD (e.g. `*://*.com/*`) |
| `all_hosts_partial_path` | 4 | Wildcard host on specific path (e.g. `*://*/analytics.js`) |
| `file_access` | 4 | Local filesystem file URL access (`file:///*`) |
| `all_sites` | 5 | Unrestricted web access (`<all_urls>`, `*://*/*`) |

---

## 5. Permission Creep Assessment

Comparing snapshots yields score delta $\Delta = S_{new} - S_{old}$ and structural differences.

### 5.1 Outcome Classifications (Exact Phrases)
1. **"Significant increase in assessed permission exposure"**
   - $\Delta \ge 15$, OR
   - Added weight-5 permission, OR
   - Broadened to `all_sites` (weight 5), OR
   - Risk score entered High level (> 69).
2. **"Permission changes require review"**
   - $\Delta \ge 5$, OR
   - Added permission with weight $\ge 3$, OR
   - Host scope broadened to a wider tier, OR
   - Unrecognized capability added.
3. **"No significant permission creep detected"**
   - All other modifications (removals, or low-weight additions with $\Delta < 5$).

### 5.2 Mandatory Limitations
AEGIS assessments always display:
- Manifest lists requested capabilities, not proof of use.
- AEGIS does not inspect extension code.
- Descriptions are claims, not proof of intent.
- Optional permissions require explicit runtime user consent.
- Risk scores are heuristics under formula version 1.

---

## 6. Excess Score ($J$) & Evidence Coverage Formulation

The excess score measures the proportion of requested capabilities that appear over-privileged or insufficiently explained by the extension's stated purpose and manifest structure (PRD Section 4.5 line 233, Milestone M5).

### 6.1 Status Multipliers ($m_i$)
Each evaluated permission item receives a status multiplier:
- **`justified`:** $m_i = 0.0$ (capability aligns with stated purpose or structural manifest features)
- **`needs_review`:** $m_i = 0.5$ (weight $\ge 3$ capability not explained by recognized purpose or features)
- **`potentially_excessive`:** $m_i = 1.0$ (capability exceeds what is needed when narrower alternatives exist)
- **`unknown`:** Excluded from calculation (insufficient information)

### 6.2 Evidence Coverage
Evidence coverage is the ratio of weight of evaluated items (excluding `unknown`) to total requested weight:

$$\text{Coverage} = \frac{\sum_{i \in \text{assessed}} w_i}{\sum_{i \in \text{requested}} w_i}$$

- If total requested weight is 0, $\text{Coverage} = 1.0$.
- If $\text{Coverage} < 0.5$, the excess score cannot be reliably calculated and is reported as `null` (`None`), rendered in the UI as *"Not enough evidence to estimate."*

### 6.3 Excess Score Calculation
When $\text{Coverage} \ge 0.5$:

$$J = \min\left(100, \max\left(0, \left\lfloor 100 \times \frac{\sum_{i \in \text{assessed}} (w_i \times m_i)}{\sum_{i \in \text{assessed}} w_i} + 0.5 \right\rfloor\right)\right)$$

Standard arithmetic half-up rounding (`floor(x + 0.5)`) is used.

---

## 7. Deterministic Justification Checker Rules

### 7.1 API Permission Rules (Evaluated in strict priority order)
- **Rule 1 (`R1`):** Capability has weight 1 (minimal risk) $\to$ `justified` (`common`).
- **Rule 2 (`R2`):** Manifest structural evidence present for this capability $\to$ `justified` (`structural`).
- **Rule 3 (`R3`):** Stated description matches a recognized purpose tag that typically requires this capability $\to$ `justified` (`stated_purpose`).
- **Rule 4 (`R4`):** Description is missing, under 20 characters, or contains no recognized purpose $\to$ `unknown` (strictly prevents excessive classification without sufficient context).
- **Rule 5 (`R5`):** Recognized purpose matches, but capability has high weight (4 or 5) and a documented narrower alternative exists $\to$ `potentially_excessive` (`narrower_alternative_exists`).
- **Rule 6 (`R6`):** Otherwise, weight $\ge 3 \to$ `needs_review`; lower weights $\to$ `unknown`.

### 7.2 Host Permission Rules (Evaluated in strict priority order)
- **Rule H1 (`H1`):** Host domain is explicitly named in the description $\to$ `justified` (`domain_in_description`).
- **Rule 1 (`R1`):** Pattern is scoped to a single host (`single_host` tier) $\to$ `justified` (`single_host`).
- **Rule 4 (`R4`):** Description is missing or under 20 characters $\to$ `unknown`.
- **Rule H2 (`H2`):** Declared single-site purpose (e.g. GitHub/YouTube enhancer) but requested broad `all_sites` $\to$ `potentially_excessive` (`single_site_mismatch`).
- **Rule H3 (`H3`):** Broad host pattern requested when narrower alternatives exist $\to$ `potentially_excessive` (`broad_host_access`).
- **Rule 6 (`R6`):** Otherwise, weight $\ge 3 \to$ `needs_review`; lower weights $\to$ `unknown`.

---

## 8. How to Safely Change a Permission Weight or Purpose Tag

1. Edit `Backend/data/permission_knowledge.json`.
2. Add or adjust the `weight`, provide `allows`, `legitimate_use`, documentation `source`, `narrower_alternative`, and set `reviewed: true` if verified against official Chrome/MDN docs.
3. Run `python scripts/gen_rules_doc.py` to regenerate `docs/RULES.md`.
4. Run `pytest tests/core/` to ensure all scoring goldens, determinism, and stale documentation checks pass.

