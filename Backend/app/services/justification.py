"""
AEGIS Justification Checker Service (Backend/app/services/justification.py)
Invokes core justification checker and enriches permissions responses with rule IDs and evidence (PRD Part 2c s6, PLAN M5).
"""

from typing import Any

from Backend.core.justification_checker import check
from Backend.core.models import JustifiedPermission, ParsedManifest


def _justified_item_to_dict(item: JustifiedPermission, kind: str) -> dict[str, Any]:
    """Converts a JustifiedPermission model into a Contract v1 PermissionItem payload."""
    return {
        "name": item.name,
        "kind": kind,
        "weight": item.weight,
        "risk_label": item.risk_label,
        "status": item.status,
        "allows": item.allows,
        "legitimate_use": item.legitimate_use,
        "source_url": item.source_url,
        "reviewed": item.reviewed,
        "rule_id": item.rule_id,
        "reason": item.reason,
        "assessment": item.reason,
        "evidence": [ev.text for ev in item.evidence],
    }


def enrich_permissions_from_manifest(parsed: ParsedManifest) -> dict[str, list[dict[str, Any]]]:
    """Evaluates justification rules on parsed manifest and formats permissions groups with evidence."""
    report = check(parsed)

    return {
        "api": [_justified_item_to_dict(p, "api") for p in report.api],
        "host": [_justified_item_to_dict(p, "host") for p in report.host],
        "optional": [_justified_item_to_dict(p, "optional") for p in report.optional],
    }


def enrich_permissions_list(
    api_perms: list[str],
    host_perms: list[str],
    optional_perms: list[str],
    description: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Backward-compatible adapter evaluating justification for list inputs."""
    opt_api = [p for p in optional_perms if not p.startswith(("*", "http", "file", "ws", "ftp", "<"))]
    opt_host = [p for p in optional_perms if p not in opt_api]

    parsed = ParsedManifest(
        name="Extension",
        version="1.0",
        manifest_version=3,
        description=description,
        api_permissions=sorted(list(api_perms)),
        host_permissions=sorted(list(host_perms)),
        optional_api_permissions=sorted(opt_api),
        optional_host_permissions=sorted(opt_host),
        sha256="",
    )
    return enrich_permissions_from_manifest(parsed)
