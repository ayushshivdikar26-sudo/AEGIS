"""
Unit tests for AEGIS Justification Checker & UI Explainability (FR-E1 to FR-E9, PRD s4.5, s11.3, PLAN M5).
Tests rule evaluation order, justification rules R1-R6 and H1-H3, excess score & coverage math,
creep alignment, plain summary generation, and 100-run determinism.
"""

from Backend.core.justification_checker import (
    alignment_for,
    check,
    generate_plain_summary,
)
from Backend.core.models import ParsedManifest
from Backend.core.risk_scoring import assess_manifest


# =============================================================================
# 1. Rule 1 (R1): Common / Low-Risk Weight 1 Capability
# =============================================================================
def test_rule_1_api_common_permissions():
    """R1: Weight 1 API permissions are justified as common capabilities."""
    manifest = ParsedManifest(
        name="Common Utility",
        version="1.0",
        manifest_version=3,
        description="A helpful lightweight utility for day to day browsing convenience.",
        api_permissions=["alarms", "storage"],
        sha256="test1",
    )
    report = check(manifest)
    api_map = {p.name: p for p in report.api}

    # Case 1: alarms
    assert api_map["alarms"].status == "justified"
    assert api_map["alarms"].rule_id == "R1"
    assert any("Common capability" in ev.text for ev in api_map["alarms"].evidence)

    # Case 2: storage
    assert api_map["storage"].status == "justified"
    assert api_map["storage"].rule_id == "R1"


def test_rule_1_host_single_host():
    """R1: Host pattern scoped to a single domain is justified."""
    manifest = ParsedManifest(
        name="Single Host Viewer",
        version="1.0",
        manifest_version=3,
        description="A helpful viewer for browsing various developer resources.",
        host_permissions=["https://example.com/*", "https://api.github.com/*"],
        sha256="test_h_r1",
    )
    report = check(manifest)
    host_map = {p.name: p for p in report.host}

    # Case 1: https://example.com/*
    assert host_map["https://example.com/*"].status == "justified"
    assert host_map["https://example.com/*"].rule_id == "R1"

    # Case 2: https://api.github.com/*
    assert host_map["https://api.github.com/*"].status == "justified"
    assert host_map["https://api.github.com/*"].rule_id == "R1"


# =============================================================================
# 2. Rule 2 (R2): Corroborating Structural Evidence
# =============================================================================
def test_rule_2_structural_manifest_features():
    """R2: Manifest structural features corroborate permission necessity."""
    # Case 1: sidePanel justified by side_panel feature
    manifest1 = ParsedManifest(
        name="Side Panel Helper",
        version="1.0",
        manifest_version=3,
        description="A general productivity utility for daily web browsing workflow.",
        api_permissions=["sidePanel"],
        features=["side_panel"],
        sha256="test_r2_1",
    )
    report1 = check(manifest1)
    p1 = report1.api[0]
    assert p1.name == "sidePanel"
    assert p1.status == "justified"
    assert p1.rule_id == "R2"
    assert any("structural feature 'side_panel'" in ev.text for ev in p1.evidence)

    # Case 2: declarativeNetRequest justified by declarative_net_request feature
    manifest2 = ParsedManifest(
        name="Net Rule Filter",
        version="1.0",
        manifest_version=3,
        description="A general productivity utility for daily web browsing workflow.",
        api_permissions=["declarativeNetRequest"],
        features=["declarative_net_request"],
        sha256="test_r2_2",
    )
    report2 = check(manifest2)
    p2 = report2.api[0]
    assert p2.name == "declarativeNetRequest"
    assert p2.status == "justified"
    assert p2.rule_id == "R2"


# =============================================================================
# 3. Rule 3 (R3): Stated Purpose Match
# =============================================================================
def test_rule_3_stated_purpose_match():
    """R3: Extension description matches recognized purpose tag that typically requires capability."""
    # Case 1: Tab manager with tabs
    manifest1 = ParsedManifest(
        name="Tab Organizer",
        version="1.0",
        manifest_version=3,
        description="Organize and group your open browser tabs effortlessly.",
        api_permissions=["tabs"],
        sha256="test_r3_1",
    )
    report1 = check(manifest1)
    p1 = report1.api[0]
    assert p1.name == "tabs"
    assert p1.status == "justified"
    assert p1.rule_id == "R3"
    assert any("Tab" in ev.text for ev in p1.evidence)

    # Case 2: Password manager with nativeMessaging
    manifest2 = ParsedManifest(
        name="Vault Keeper",
        version="1.0",
        manifest_version=3,
        description="Secure password manager to store and autofill credentials securely.",
        api_permissions=["nativeMessaging"],
        sha256="test_r3_2",
    )
    report2 = check(manifest2)
    p2 = report2.api[0]
    assert p2.name == "nativeMessaging"
    assert p2.status == "justified"
    assert p2.rule_id == "R3"


# =============================================================================
# 4. Rule 4 (R4): Missing or Insufficient Description (< 20 chars) -> Unknown
# =============================================================================
def test_rule_4_short_or_missing_description():
    """R4: Under-specified descriptions strictly return unknown and never potentially_excessive."""
    # Case 1: None / empty description with weight 4 permission
    manifest1 = ParsedManifest(
        name="No Desc Ext",
        version="1.0",
        manifest_version=3,
        description=None,
        api_permissions=["history"],
        host_permissions=["*://*.example.com/*"],
        sha256="test_r4_1",
    )
    report1 = check(manifest1)
    assert report1.api[0].status == "unknown"
    assert report1.api[0].rule_id == "R4"
    assert report1.api[0].status != "potentially_excessive"
    assert "missing" in report1.api[0].reason.lower()

    assert report1.host[0].status == "unknown"
    assert report1.host[0].rule_id == "R4"

    # Case 2: Short description (< 20 chars)
    manifest2 = ParsedManifest(
        name="Short Desc Ext",
        version="1.0",
        manifest_version=3,
        description="Todo notes",  # 10 chars
        api_permissions=["cookies", "tabs"],
        host_permissions=["<all_urls>"],
        sha256="test_r4_2",
    )
    report2 = check(manifest2)
    for p in report2.api:
        assert p.status == "unknown"
        assert p.rule_id == "R4"
        assert p.status != "potentially_excessive"

    assert report2.host[0].status == "unknown"
    assert report2.host[0].rule_id == "R4"
    assert report2.host[0].status != "potentially_excessive"


# =============================================================================
# 5. Rule 5 (R5): Potentially Excessive API Permission (Narrower Alt Exists)
# =============================================================================
def test_rule_5_potentially_excessive_api():
    """R5: High-weight permission with narrower alternative when stated purpose doesn't justify it."""
    # Case 1: Note taking with history (weight 4, narrower alt: sessions or activeTab)
    manifest1 = ParsedManifest(
        name="Quick Memo",
        version="1.0",
        manifest_version=3,
        description="Capture quick notes and save memo ideas while browsing the web.",
        api_permissions=["history"],
        sha256="test_r5_1",
    )
    report1 = check(manifest1)
    p1 = report1.api[0]
    assert p1.name == "history"
    assert p1.status == "potentially_excessive"
    assert p1.rule_id == "R5"
    assert p1.narrower_alternative is not None
    assert "sessions or activeTab" in p1.narrower_alternative

    # Case 2: Note taking with cookies (weight 4, narrower alt: activeTab or storage)
    manifest2 = ParsedManifest(
        name="Simple Scratchpad",
        version="1.0",
        manifest_version=3,
        description="Take quick notes and save ideas while browsing articles online.",
        api_permissions=["cookies"],
        sha256="test_r5_2",
    )
    report2 = check(manifest2)
    p2 = report2.api[0]
    assert p2.name == "cookies"
    assert p2.status == "potentially_excessive"
    assert p2.rule_id == "R5"
    assert p2.narrower_alternative is not None


# =============================================================================
# 6. Rule 6 (R6): Needs Review / Unknown
# =============================================================================
def test_rule_6_needs_review_and_unknown():
    """R6: Weight >= 3 capability without matched purpose or structure flagged as needs_review."""
    # Case 1: webRequest (weight 4, no narrower alt) on note taking
    manifest1 = ParsedManifest(
        name="Note taker",
        version="1.0",
        manifest_version=3,
        description="Take quick notes and save memo ideas while browsing articles online.",
        api_permissions=["webRequest"],
        sha256="test_r6_1",
    )
    report1 = check(manifest1)
    p1 = report1.api[0]
    assert p1.name == "webRequest"
    assert p1.status == "needs_review"
    assert p1.rule_id == "R6"

    # Case 2: privacy (weight 3, no narrower alt) on note taking
    manifest2 = ParsedManifest(
        name="Memo keeper",
        version="1.0",
        manifest_version=3,
        description="Take quick notes and save memo ideas while browsing articles online.",
        api_permissions=["privacy"],
        sha256="test_r6_2",
    )
    report2 = check(manifest2)
    p2 = report2.api[0]
    assert p2.name == "privacy"
    assert p2.status == "needs_review"
    assert p2.rule_id == "R6"


# =============================================================================
# 7. Rule H1: Host Domain Named in Description -> Justified
# =============================================================================
def test_rule_h1_host_domain_in_description():
    """H1: Host domain explicitly cited in description is justified."""
    # Case 1: github.com named in description
    manifest1 = ParsedManifest(
        name="GitHub Notifier",
        version="1.0",
        manifest_version=3,
        description="Official helper for github.com to track notifications and open issues.",
        host_permissions=["*://github.com/*"],
        sha256="test_h1_1",
    )
    report1 = check(manifest1)
    h1 = report1.host[0]
    assert h1.status == "justified"
    assert h1.rule_id == "H1"
    assert any("github.com" in ev.text for ev in h1.evidence)

    # Case 2: youtube.com named in description
    manifest2 = ParsedManifest(
        name="YouTube Player Enhancer",
        version="1.0",
        manifest_version=3,
        description="Enhance your youtube.com watching experience with player controls.",
        host_permissions=["*://*.youtube.com/*"],
        sha256="test_h1_2",
    )
    report2 = check(manifest2)
    h2 = report2.host[0]
    assert h2.status == "justified"
    assert h2.rule_id == "H1"
    assert any("youtube.com" in ev.text for ev in h2.evidence)


# =============================================================================
# 8. Rule H2: Single-Site Mismatch -> Potentially Excessive
# =============================================================================
def test_rule_h2_single_site_mismatch():
    """H2: Single-site purpose with broad all_sites host access is potentially_excessive."""
    # Case 1: GitHub single site purpose with <all_urls>
    manifest1 = ParsedManifest(
        name="GitHub Toolkit",
        version="1.0",
        manifest_version=3,
        description="A dedicated assistant for github repositories, pull requests, and code reviews.",
        host_permissions=["<all_urls>"],
        sha256="test_h2_1",
    )
    report1 = check(manifest1)
    h1 = report1.host[0]
    assert h1.status == "potentially_excessive"
    assert h1.rule_id == "H2"
    assert any("single-site" in ev.text.lower() for ev in h1.evidence)

    # Case 2: YouTube single site purpose with *://*/*
    manifest2 = ParsedManifest(
        name="YouTube Dark",
        version="1.0",
        manifest_version=3,
        description="A specialized youtube enhancer for video playback controls and custom styles.",
        host_permissions=["*://*/*"],
        sha256="test_h2_2",
    )
    report2 = check(manifest2)
    h2 = report2.host[0]
    assert h2.status == "potentially_excessive"
    assert h2.rule_id == "H2"


# =============================================================================
# 9. Rule H3: Broad Host Access -> Potentially Excessive
# =============================================================================
def test_rule_h3_broad_host_access():
    """H3: Broad host pattern when narrower scoping is available."""
    # Case 1: Multi-site purpose (shopping) requesting <all_urls>
    manifest1 = ParsedManifest(
        name="Coupon Hunter",
        version="1.0",
        manifest_version=3,
        description="Automatically find coupons and cashback discounts when shopping online.",
        host_permissions=["<all_urls>"],
        sha256="test_h3_1",
    )
    report1 = check(manifest1)
    h1 = report1.host[0]
    assert h1.status == "potentially_excessive"
    assert h1.rule_id == "H3"
    assert h1.narrower_alternative is not None

    # Case 2: Broad file:///* access
    manifest2 = ParsedManifest(
        name="Offline Reader",
        version="1.0",
        manifest_version=3,
        description="Read saved html pages offline with custom dark mode formatting.",
        host_permissions=["file:///*"],
        sha256="test_h3_2",
    )
    report2 = check(manifest2)
    h2 = report2.host[0]
    assert h2.status == "potentially_excessive"
    assert h2.rule_id == "H3"


# =============================================================================
# 10. PRD Section 11.3 Acceptance Scenarios
# =============================================================================
def test_prd_11_3_scenarios():
    """Executes the specific scenarios documented in PRD section 11.3."""
    # 1. Tab manager with tabs and storage
    m_tab = ParsedManifest(
        name="Tab Flow",
        version="1.0",
        manifest_version=3,
        description="Organize and group your open browser tabs effortlessly.",
        api_permissions=["storage", "tabs"],
        sha256="m_tab",
    )
    r_tab = check(m_tab)
    tab_map = {p.name: p for p in r_tab.api}
    assert tab_map["tabs"].status == "justified"
    assert tab_map["tabs"].rule_id == "R3"
    assert tab_map["storage"].status == "justified"
    assert tab_map["storage"].rule_id == "R1"

    # 2. Note taking with history
    m_note = ParsedManifest(
        name="Quick Note",
        version="1.0",
        manifest_version=3,
        description="Take quick notes and save memo ideas while browsing articles online.",
        api_permissions=["history"],
        sha256="m_note",
    )
    r_note = check(m_note)
    hist = r_note.api[0]
    assert hist.status == "potentially_excessive"
    assert hist.rule_id == "R5"
    assert hist.narrower_alternative is not None

    # 3. Description under 20 characters
    m_short = ParsedManifest(
        name="Shorty",
        version="1.0",
        manifest_version=3,
        description="Todo notes",
        api_permissions=["history", "tabs"],
        sha256="m_short",
    )
    r_short = check(m_short)
    for p in r_short.api:
        assert p.status == "unknown"
        assert p.rule_id == "R4"
        assert p.status != "potentially_excessive"

    # 4. Single-site enhancer with <all_urls>
    m_single = ParsedManifest(
        name="GH Pro",
        version="1.0",
        manifest_version=3,
        description="A dedicated assistant for github repositories and pull requests.",
        host_permissions=["<all_urls>"],
        sha256="m_single",
    )
    r_single = check(m_single)
    assert r_single.host[0].status == "potentially_excessive"
    assert r_single.host[0].rule_id == "H2"

    # 5. Permission justified purely by structural manifest evidence
    m_side = ParsedManifest(
        name="Side Panel Dock",
        version="1.0",
        manifest_version=3,
        description="A general productivity utility for daily web browsing workflow.",
        api_permissions=["sidePanel"],
        features=["side_panel"],
        sha256="m_side",
    )
    r_side = check(m_side)
    assert r_side.api[0].status == "justified"
    assert r_side.api[0].rule_id == "R2"


# =============================================================================
# 11. Excess Score & Coverage Arithmetic Edge Cases
# =============================================================================
def test_excess_score_coverage_below_50_percent_returns_none():
    """PRD s4.5: When evidence_coverage < 0.5, excess_score must be None."""
    # Description missing -> history (w=4) becomes unknown
    # alarms (w=1) becomes justified (R1)
    # Assessed weight = 1, Total weight = 5 -> coverage = 0.20 < 0.5
    manifest = ParsedManifest(
        name="Low Coverage",
        version="1.0",
        manifest_version=3,
        description=None,
        api_permissions=["alarms", "history"],
        sha256="test_cov_low",
    )
    report = check(manifest)
    assert report.evidence_coverage == 0.2
    assert report.excess_score is None


def test_excess_score_calculation_arithmetic():
    """Verifies J = 100 * sum(w_i * m_i) / sum(w_i) over assessed items with half-up rounding."""
    # note taking:
    # storage (w=1) -> justified (m=0)
    # history (w=4) -> potentially_excessive (m=1.0)
    # Total weight = 5, assessed = 5 -> coverage = 1.0
    # J = 100 * (1*0 + 4*1.0) / 5 = 100 * 4 / 5 = 80.0
    manifest = ParsedManifest(
        name="Math Test",
        version="1.0",
        manifest_version=3,
        description="Take quick notes and save memo ideas while browsing articles online.",
        api_permissions=["history", "storage"],
        sha256="test_j_math",
    )
    report = check(manifest)
    assert report.evidence_coverage == 1.0
    assert report.excess_score == 80.0


def test_excess_score_empty_manifest():
    """Empty manifest yields coverage 1.0 and excess score 0.0."""
    manifest = ParsedManifest(
        name="Empty",
        version="1.0",
        manifest_version=3,
        api_permissions=[],
        host_permissions=[],
        sha256="test_empty",
    )
    report = check(manifest)
    assert report.evidence_coverage == 1.0
    assert report.excess_score == 0.0


# =============================================================================
# 12. Creep Alignment & Plain-Language Summary
# =============================================================================
def test_creep_alignment_evaluation():
    """alignment_for returns consistent, inconsistent, or unclear depending on statuses."""
    manifest = ParsedManifest(
        name="Tab Session Helper",
        version="1.0",
        manifest_version=3,
        description="Organize and group your open browser tabs effortlessly.",
        api_permissions=["history", "storage", "tabs"],
        sha256="test_align",
    )
    report = check(manifest)

    # Consistent: all justified
    res_cons = alignment_for(["storage", "tabs"], report)
    assert res_cons["status"] == "consistent"

    # Inconsistent: any potentially_excessive
    res_incons = alignment_for(["history"], report)
    assert res_incons["status"] == "inconsistent"

    # Empty added list
    res_empty = alignment_for([], report)
    assert res_empty["status"] == "consistent"


def test_plain_summary_deterministic_and_safe():
    """generate_plain_summary produces explainable text without subjective malicious/suspicious words."""
    manifest = ParsedManifest(
        name="Broad Extension",
        version="1.0",
        manifest_version=3,
        description="A general productivity utility for daily web browsing workflow.",
        host_permissions=["<all_urls>"],
        api_permissions=["history"],
        sha256="test_plain",
    )
    assessment = assess_manifest(manifest)
    report = check(manifest, assessment)
    summary = generate_plain_summary(manifest, report, assessment)

    # Must mention broad access
    assert "every website you visit" in summary.lower()
    # Must NOT contain forbidden subjective language
    assert "malicious" not in summary.lower()
    assert "suspicious" not in summary.lower()


# =============================================================================
# 13. 100-Run Determinism Test
# =============================================================================
def test_100_run_determinism():
    """100 identical runs must produce byte-for-byte identical justification reports."""
    manifest = ParsedManifest(
        name="Determinism Subject",
        version="1.0",
        manifest_version=3,
        description="Take quick notes and save memo ideas while browsing articles online.",
        api_permissions=["alarms", "history", "storage", "tabs"],
        host_permissions=["*://*.example.com/*", "<all_urls>"],
        features=["side_panel"],
        sha256="test_det",
    )
    baseline_report = check(manifest)
    baseline_dump = baseline_report.model_dump()

    for _ in range(100):
        run_report = check(manifest)
        assert run_report.model_dump() == baseline_dump
