"""
Unit tests for Version Comparison & Creep Assessment (FR-V1 to FR-V7).
Verifies the Golden Comparison, host broadening detection, and outcome classifications.
"""

from Backend.core.models import ParsedManifest
from Backend.core.version_comparison import (
    OUTCOME_NEEDS_REVIEW,
    OUTCOME_NO_SIGNIFICANT,
    OUTCOME_SIGNIFICANT_INCREASE,
    assess_creep,
    compare,
)


def test_golden_comparison():
    """
    Golden Comparison (PRD s4.6 & Part 2a s7):
    Old: api [storage, alarms], host [https://example.com/*]
    New: api [storage, alarms, history], host [<all_urls>]
    Expect:
    - api added: [history], retained: [alarms, storage]
    - host added: [<all_urls>], removed: [https://example.com/*]
    - host broadened: 1 entry (single_host -> all_sites)
    - score_from = 20, score_to = 70
    - outcome = significant_increase
    """
    old = ParsedManifest(
        manifest_version=3,
        name="Golden Ext",
        version="1.0.0",
        api_permissions=["alarms", "storage"],
        host_permissions=["https://example.com/*"],
        sha256="old_sha",
    )
    new = ParsedManifest(
        manifest_version=3,
        name="Golden Ext",
        version="2.0.0",
        api_permissions=["alarms", "history", "storage"],
        host_permissions=["<all_urls>"],
        sha256="new_sha",
    )

    diff = compare(old, new)
    assert diff.from_version == "1.0.0"
    assert diff.to_version == "2.0.0"
    assert diff.score_from == 20
    assert diff.score_to == 70

    # API diff
    assert [i.name for i in diff.api.added] == ["history"]
    assert [i.name for i in diff.api.removed] == []
    assert sorted([i.name for i in diff.api.retained]) == ["alarms", "storage"]

    # Host diff
    assert [i.name for i in diff.host.added] == ["<all_urls>"]
    assert [i.name for i in diff.host.removed] == ["https://example.com/*"]
    assert len(diff.host.broadened) == 1
    broadened_item = diff.host.broadened[0]
    assert broadened_item.from_pattern == "https://example.com/*"
    assert broadened_item.to_pattern == "<all_urls>"
    assert broadened_item.from_tier == "single_host"
    assert broadened_item.to_tier == "all_sites"

    # Assess creep
    creep = assess_creep(diff)
    assert creep.outcome == OUTCOME_SIGNIFICANT_INCREASE
    assert len(creep.triggers) > 0
    # Must never use malicious or suspicious in output
    assert "malicious" not in creep.summary.lower()
    assert "suspicious" not in creep.summary.lower()
    assert len(creep.limitations) > 0


def test_identical_manifests():
    m = ParsedManifest(
        manifest_version=3,
        name="Static",
        version="1.0",
        api_permissions=["storage"],
        host_permissions=["https://example.com/*"],
        sha256="sha1",
    )
    diff = compare(m, m)
    creep = assess_creep(diff)
    assert diff.score_from == diff.score_to
    assert len(diff.api.added) == 0
    assert len(diff.host.added) == 0
    assert creep.outcome == OUTCOME_NO_SIGNIFICANT


def test_removals_only():
    old = ParsedManifest(
        manifest_version=3,
        name="Privacy Hardening",
        version="1.0",
        api_permissions=["history", "storage"],
        host_permissions=["https://example.com/*", "https://api.example.com/*"],
        sha256="sha_old",
    )
    new = ParsedManifest(
        manifest_version=3,
        name="Privacy Hardening",
        version="1.1",
        api_permissions=["storage"],
        host_permissions=["https://example.com/*"],
        sha256="sha_new",
    )
    diff = compare(old, new)
    creep = assess_creep(diff)
    assert diff.score_to < diff.score_from
    assert len(diff.api.added) == 0
    assert len(diff.host.added) == 0
    assert creep.outcome == OUTCOME_NO_SIGNIFICANT


def test_needs_review_outcome():
    # Adding a weight 3 permission (e.g. bookmarks) with a small delta
    old = ParsedManifest(
        manifest_version=3,
        name="Review Test",
        version="1.0",
        api_permissions=["storage"],
        host_permissions=["https://example.com/*"],
        sha256="sha_old",
    )
    new = ParsedManifest(
        manifest_version=3,
        name="Review Test",
        version="1.1",
        api_permissions=["bookmarks", "storage"],
        host_permissions=["https://example.com/*"],
        sha256="sha_new",
    )
    diff = compare(old, new)
    creep = assess_creep(diff)
    assert creep.outcome == OUTCOME_NEEDS_REVIEW
    assert any("weight >= 3" in t.threshold for t in creep.triggers)


def test_already_covered_addition_flag():
    old = ParsedManifest(
        manifest_version=3,
        name="Already Covered",
        version="1.0",
        host_permissions=["*://*.example.com/*"],
        sha256="sha1",
    )
    new = ParsedManifest(
        manifest_version=3,
        name="Already Covered",
        version="1.1",
        host_permissions=["*://*.example.com/*", "https://sub.example.com/*"],
        sha256="sha2",
    )
    diff = compare(old, new)
    added_sub = next(i for i in diff.host.added if i.name == "https://sub.example.com/*")
    assert added_sub.already_covered_by == "*://*.example.com/*"
