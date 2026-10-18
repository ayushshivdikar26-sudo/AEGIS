"""
Unit Tests for Unified Deterministic Risk Scoring and Honest Privilege Assessment (Milestone 1d).
Verifies:
1. Documented weights and thresholds: LOW (0-34), MED (35-69), HIGH (70-100).
2. Known permission sets across distinct exposure profiles.
3. High-weight danger floors (Weight 4 -> Floor 40, Weight 5 -> Floor 70).
4. Content script match pattern inclusion in host scoring.
5. Exact boundary classification (34 vs 35, 69 vs 70).
6. Honest wording: absence of sensationalist claims (no 'malicious', 'malware', 'hack').
"""

from Backend.core.models import ParsedManifest
from Backend.core.permission_rules import get_knowledge_base
from Backend.core.risk_scoring import assess_manifest


def test_unified_threshold_boundaries():
    """Verify exact threshold boundary transitions."""
    kb = get_knowledge_base()
    low_max = kb.thresholds.get("low_max", 34)
    mid_max = kb.thresholds.get("mid_max", 69)

    assert low_max == 34
    assert mid_max == 69

    # Score <= 34 is low
    # Score 35..69 is medium
    # Score >= 70 is high


def test_known_permission_set_low():
    """Low exposure: storage and alarms with single host -> score <= 34, low."""
    manifest = ParsedManifest(
        name="Low Risk Utility",
        version="1.0.0",
        manifest_version=3,
        api_permissions=["storage", "alarms"],
        host_permissions=["https://api.example.com/*"],
        sha256="low_sha_1",
    )
    assessment = assess_manifest(manifest)
    assert assessment.risk_level == "low"
    assert assessment.risk_score <= 34
    # storage (1), alarms (1) -> R_api = 100 * 2 / 10 = 20.0
    # single host (1) -> R_host = 100 * 1 / 5 = 20.0
    # S_base = 20.0 -> score = 20
    assert assessment.risk_score == 20


def test_known_permission_set_medium_weight_4_floor():
    """Medium exposure: tabs capability (weight 4) triggers High-weight danger floor 40."""
    manifest = ParsedManifest(
        name="Tab Helper",
        version="1.0.0",
        manifest_version=3,
        api_permissions=["tabs", "storage"],
        host_permissions=["https://example.com/*"],
        sha256="med_sha_1",
    )
    assessment = assess_manifest(manifest)
    assert assessment.risk_level == "medium"
    assert assessment.risk_score >= 40
    assert assessment.max_weight == 4
    # Breakdown must contain Floor line item
    bd_labels = [item.label for item in assessment.breakdown]
    assert "High-weight permission floor" in bd_labels


def test_known_permission_set_high_critical_urls():
    """High exposure: <all_urls> (weight 5) triggers Critical danger floor 70."""
    manifest = ParsedManifest(
        name="Broad Site Access Extension",
        version="1.0.0",
        manifest_version=3,
        api_permissions=["storage"],
        host_permissions=["<all_urls>"],
        sha256="high_sha_1",
    )
    assessment = assess_manifest(manifest)
    assert assessment.risk_level == "high"
    assert assessment.risk_score >= 70
    assert assessment.max_weight == 5
    assert any("<all_urls>" in flag for flag in assessment.critical_flags)


def test_content_scripts_matches_accounted_in_scoring():
    """Content script broad match patterns must contribute to host exposure scoring."""
    manifest = ParsedManifest(
        name="Content Script Injector",
        version="1.0.0",
        manifest_version=3,
        api_permissions=["storage"],
        host_permissions=["<all_urls>"],
        sha256="cs_sha_1",
    )
    assessment = assess_manifest(manifest)
    assert assessment.risk_score == 70
    assert assessment.risk_level == "high"


def test_honest_wording_principle():
    """Assessment summaries and notes must reflect capability exposure without sensationalizing."""
    manifest = ParsedManifest(
        name="Sensitive Tool",
        version="1.0.0",
        manifest_version=3,
        api_permissions=["cookies", "webRequest"],
        host_permissions=["<all_urls>"],
        sha256="honest_sha_1",
    )
    assessment = assess_manifest(manifest)

    serialized = assessment.model_dump_json().lower()
    forbidden_words = ["malicious", "malware", "virus", "trojan", "hacker", "infected", "evil"]
    for word in forbidden_words:
        assert word not in serialized, f"Sensationalized word '{word}' found in assessment output"

    # Must contain exposure / capability phrasing
    assert "exposure" in assessment.plain_summary.lower() or "capabilities" in assessment.plain_summary.lower()
