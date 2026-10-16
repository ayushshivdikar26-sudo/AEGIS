"""
Unit tests for AEGIS Risk Scoring Engine (FR-S1 to FR-S8, FR-E2, FR-E8).
Verifies the three mandatory Golden Examples, breakdown arithmetic, and determinism.
"""

from Backend.core.models import ParsedManifest
from Backend.core.risk_scoring import assess_manifest


def test_golden_example_1():
    """
    Golden Example 1 (PRD s4.4 & Part 2a s6):
    api = [storage, alarms, history], host = [https://example.com/*]
    R_api = 100 * 6 / 15 = 40.0
    R_host = 100 * 1 / 5 = 20.0
    S_base = 30.0
    Floor = 40 (weight 4 present)
    Score = 40, medium
    Breakdown: history 13.3, host 10.0, storage 3.3, alarms 3.3, floor +10.0
    """
    manifest = ParsedManifest(
        manifest_version=3,
        name="Golden 1",
        version="1.0",
        api_permissions=["alarms", "history", "storage"],
        host_permissions=["https://example.com/*"],
        sha256="abc1",
    )
    assessment = assess_manifest(manifest)

    assert assessment.api_score == 40.0
    assert assessment.host_score == 20.0
    assert assessment.risk_score == 40
    assert assessment.risk_level == "medium"

    # Verify breakdown items and contributions
    bd_map = {item.label: item.contribution for item in assessment.breakdown}
    assert bd_map["history"] == 13.3
    assert bd_map["https://example.com/*"] == 10.0
    assert bd_map["storage"] == 3.3
    assert bd_map["alarms"] == 3.3
    assert bd_map["High-weight permission floor"] == 10.0

    # Verify calculation steps trace
    assert len(assessment.calculation) > 0
    assert assessment.calculation[-1].result == str(assessment.risk_score)


def test_golden_example_2():
    """
    Golden Example 2 (PRD s4.4 & Part 2a s6):
    api = [storage], host = [<all_urls>]
    R_api = 20.0
    R_host = 100.0
    S_base = 60.0
    Floor = 70 (weight 5 present)
    Score = 70, high
    Breakdown: <all_urls> 50.0, storage 10.0, floor +10.0
    """
    manifest = ParsedManifest(
        manifest_version=3,
        name="Golden 2",
        version="1.0",
        api_permissions=["storage"],
        host_permissions=["<all_urls>"],
        sha256="abc2",
    )
    assessment = assess_manifest(manifest)

    assert assessment.api_score == 20.0
    assert assessment.host_score == 100.0
    assert assessment.risk_score == 70
    assert assessment.risk_level == "high"

    bd_map = {item.label: item.contribution for item in assessment.breakdown}
    assert bd_map["<all_urls>"] == 50.0
    assert bd_map["storage"] == 10.0
    assert bd_map["High-weight permission floor"] == 10.0

    assert assessment.calculation[-1].result == str(assessment.risk_score)


def test_golden_example_3():
    """
    Golden Example 3 (PRD s4.4 & Part 2a s6):
    No permissions declared: score 0, low, note "This extension declares no permissions."
    """
    manifest = ParsedManifest(
        manifest_version=3,
        name="Golden 3 (Zero Permissions)",
        version="1.0",
        api_permissions=[],
        host_permissions=[],
        sha256="abc3",
    )
    assessment = assess_manifest(manifest)

    assert assessment.api_score == 0.0
    assert assessment.host_score == 0.0
    assert assessment.risk_score == 0
    assert assessment.risk_level == "low"
    assert "This extension declares no permissions." in assessment.notes
    assert assessment.calculation[-1].result == "0"


def test_breakdown_adds_up_to_pre_round_score():
    """FR-S7: Breakdown must add up to the pre-rounding score."""
    manifest = ParsedManifest(
        manifest_version=3,
        name="Breakdown Test",
        version="1.0",
        api_permissions=["tabs", "cookies", "bookmarks"],
        host_permissions=["https://*.example.com/*", "http://*.org/*"],
        sha256="abc4",
    )
    assessment = assess_manifest(manifest)

    # Sum of rounded contributions should be within rounding tolerance (±0.2) of pre-round score
    contrib_sum = sum(item.contribution for item in assessment.breakdown)
    # The pre-round score is either S_base or floor
    s_base = 0.5 * assessment.api_score + 0.5 * assessment.host_score
    pre_round = max(s_base, 40.0)  # tabs and cookies are weight 4, floor is 40
    assert abs(contrib_sum - pre_round) <= 0.2


def test_unrecognized_permissions_handling():
    manifest = ParsedManifest(
        manifest_version=3,
        name="Unknown Perms",
        version="1.0",
        api_permissions=["customInternalApi123"],
        host_permissions=["invalid://not-a-pattern"],
        sha256="abc5",
    )
    assessment = assess_manifest(manifest)
    assert "customInternalApi123" in assessment.unrecognized
    assert "invalid://not-a-pattern" in assessment.unrecognized
    # Default unknown weight is 3
    assert assessment.max_weight == 3


def test_potential_score_with_optional_permissions():
    manifest = ParsedManifest(
        manifest_version=3,
        name="Optional Permissions",
        version="1.0",
        api_permissions=["storage"],  # weight 1
        host_permissions=[],
        optional_api_permissions=["debugger"],  # weight 5
        optional_host_permissions=["<all_urls>"],  # weight 5
        sha256="abc6",
    )
    assessment = assess_manifest(manifest)
    # Requested risk_score should be low (storage only)
    assert assessment.risk_score == 20  # 100 * 1 / 5 = 20
    assert assessment.risk_level == "low"
    # Potential score should account for debugger & <all_urls> -> floor 70
    assert assessment.potential_score >= 70


def test_scoring_determinism_100_runs():
    """FR-E8: 100 runs on identical manifest produce byte-identical assessment serialization."""
    manifest = ParsedManifest(
        manifest_version=3,
        name="Determinism Test",
        version="1.0",
        api_permissions=["storage", "tabs", "history"],
        host_permissions=["https://example.com/*", "<all_urls>"],
        sha256="abc_det",
    )
    first_result = assess_manifest(manifest).model_dump_json()
    for _ in range(100):
        run_result = assess_manifest(manifest).model_dump_json()
        assert run_result == first_result
