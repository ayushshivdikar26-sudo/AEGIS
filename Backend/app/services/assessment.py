"""
AEGIS Assessment Service (Backend/app/services/assessment.py)
Transforms stored database snapshot rows into core models and computes deterministic risk scores (PRD Part 2c s6).
"""

from typing import Any

from Backend.core.models import ParsedManifest
from Backend.core.risk_scoring import assess_manifest
from Backend.core.version_comparison import compare


def snapshot_row_to_parsed_manifest(snap: dict[str, Any]) -> ParsedManifest:
    """Converts a database snapshot row into a core ParsedManifest instance."""
    vkey = snap.get("version_key")
    return ParsedManifest(
        name=snap.get("name", "Unknown Extension"),
        version=snap.get("version", "1.0"),
        manifest_version=int(snap.get("manifest_version", 3)),
        description=snap.get("description"),
        api_permissions=list(snap.get("api_permissions", [])),
        host_permissions=list(snap.get("host_permissions", [])),
        optional_api_permissions=list(snap.get("optional_api_permissions", [])),
        optional_host_permissions=list(snap.get("optional_host_permissions", [])),
        content_script_matches=list(snap.get("content_script_matches", [])),
        features=list(snap.get("features", [])),
        sha256=snap.get("manifest_sha256", ""),
        version_key=list(vkey) if vkey else None,
    )


def compute_snapshot_assessment(snap: dict[str, Any]) -> dict[str, Any]:
    """Computes pure, deterministic risk assessment for a snapshot row."""
    manifest = snapshot_row_to_parsed_manifest(snap)
    assessment = assess_manifest(manifest)
    return assessment.model_dump()


def compare_snapshot_rows(snap_old: dict[str, Any], snap_new: dict[str, Any]) -> dict[str, Any]:
    """Computes version diff, host broadening, and creep classification between two snapshot rows."""
    manifest_old = snapshot_row_to_parsed_manifest(snap_old)
    manifest_new = snapshot_row_to_parsed_manifest(snap_new)
    comparison = compare(manifest_old, manifest_new)
    return comparison.model_dump()
