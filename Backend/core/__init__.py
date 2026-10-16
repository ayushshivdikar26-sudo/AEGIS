"""
AEGIS Core Package
Pure Python analysis engine for browser extension permissions and version comparison.
"""

from .host_patterns import (
    covers,
    describe,
    is_match_pattern,
    parse_match_pattern,
    scope_tier,
)
from .justification_checker import alignment_for, check, generate_plain_summary
from .manifest_parser import parse_manifest
from .models import (
    Assessment,
    BreakdownItem,
    CalculationStep,
    Comparison,
    CreepAssessment,
    CreepTrigger,
    EvidenceItem,
    JustificationReport,
    JustifiedPermission,
    ManifestError,
    MatchPattern,
    ParsedManifest,
    PermissionInfo,
    PurposeMatch,
    ScopeTier,
)
from .permission_rules import PermissionKnowledgeBase, get_knowledge_base
from .risk_scoring import assess_manifest, calculate_set_score
from .version_comparison import assess_creep, compare

__all__ = [
    "Assessment",
    "BreakdownItem",
    "CalculationStep",
    "Comparison",
    "CreepAssessment",
    "CreepTrigger",
    "EvidenceItem",
    "JustificationReport",
    "JustifiedPermission",
    "ManifestError",
    "MatchPattern",
    "ParsedManifest",
    "PermissionInfo",
    "PermissionKnowledgeBase",
    "PurposeMatch",
    "ScopeTier",
    "alignment_for",
    "assess_creep",
    "assess_manifest",
    "calculate_set_score",
    "check",
    "compare",
    "covers",
    "describe",
    "generate_plain_summary",
    "get_knowledge_base",
    "is_match_pattern",
    "parse_manifest",
    "parse_match_pattern",
    "scope_tier",
]
