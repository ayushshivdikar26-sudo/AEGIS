# AEGIS Demonstration Fixtures (Synthetic)

> [!NOTE]
> These manifests are **synthetic, illustrative test samples** designed specifically for the AEGIS live demonstration. They are **not** real-world malicious extensions. They demonstrate the explainable exposure-risk assessment and historical version diffing capabilities of the deterministic AEGIS analysis engine.

## Sample: QuickNote Clipper

### Version 1.0.0 (`v1_narrow_manifest.json`)
- **Stated Purpose:** Capture text snippets and save notes locally in your browser.
- **Declared API Permissions:** `storage`, `alarms` (low weight, routine).
- **Declared Host Access:** `https://api.quicknote.example/*` (single host domain).
- **Expected Engine Risk Score:** Low (~20/100).
- **Justification Fit:** Declared permissions align with local note storage.

### Version 1.1.0 (`v2_expanded_manifest.json`)
- **Stated Purpose:** Unchanged.
- **Added API Permissions:** `history` (weight 4 - reads visited URLs), `cookies` (weight 4 - session access).
- **Expanded Host Access:** `*://*/*` (broadened from single host to all websites).
- **Expected Engine Risk Score:** High (~75/100).
- **Expected Creep Outcome:** *"Significant increase in assessed permission exposure"*.
- **Review Reason:** The added sensitive APIs (`history`, `cookies`) and universal web access exceed the stated text snippet clipping capability.

---

## Live Demonstration Procedure

1. Launch AEGIS:
   ```bash
   uvicorn Backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```
2. Navigate to `http://127.0.0.1:8000/`.
3. Click **"Import Manifest"** in the sidebar.
4. Select `fixtures/demo/v1_narrow_manifest.json` (or paste its content).
   - Enter Extension ID: `quicknote-clipper` (or leave default, matching on extension name).
   - Click **"Analyze Manifest"**.
   - Observe **Low Risk (20)**, narrow permissions.
5. Click **"Import Manifest"** again.
6. Select `fixtures/demo/v2_expanded_manifest.json` (or paste its content).
   - Enter the same Extension ID: `quicknote-clipper`.
   - Click **"Analyze Manifest"**.
7. Observe immediate automatic snapshot linking:
   - **Risk Gauge:** elevated from 20 to 75 (High Exposure).
   - **Version Comparison:** lists `1.0.0 -> 1.1.0`.
   - **Diff:** highlights added `cookies` and `history`, plus host broadening from `https://api.quicknote.example/*` to `*://*/*`.
   - **Permission Creep:** displays *"Significant increase in assessed permission exposure"* and explains why without claiming malware.
