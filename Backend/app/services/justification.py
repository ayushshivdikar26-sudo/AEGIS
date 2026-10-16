"""
AEGIS Justification Checker Service (Backend/app/services/justification.py)
Stub service until Milestone M5 (Part 2d); returns 'unknown' status without fabricating evidence (PRD Part 2c s6).
"""

from typing import Any

from Backend.core.permission_rules import get_knowledge_base


def get_permission_justification(perm_name: str, kind: str) -> dict[str, Any]:
    """Returns baseline permission info with 'unknown' justification status."""
    kb = get_knowledge_base()
    if kind == "api":
        info = kb.info_for_api(perm_name)
    else:
        info = kb.info_for_host(perm_name)

    return {
        "name": perm_name,
        "kind": kind,
        "weight": info.weight,
        "risk_label": info.risk_label.value if hasattr(info.risk_label, "value") else str(info.risk_label),
        "status": "unknown",
        "allows": info.allows,
        "legitimate_use": info.legitimate_use,
        "source_url": info.source_url,
        "reviewed": info.reviewed,
        "evidence": ["Justification checker not installed yet."],
    }


def enrich_permissions_list(api_perms: list[str], host_perms: list[str], optional_perms: list[str]) -> dict[str, Any]:
    """Enriches manifest permissions with rules catalog and stub justification status."""
    api_items = [get_permission_justification(p, "api") for p in sorted(api_perms)]
    host_items = [get_permission_justification(p, "host") for p in sorted(host_perms)]
    opt_items = [get_permission_justification(p, "optional") for p in sorted(optional_perms)]

    return {
        "api": api_items,
        "host": host_items,
        "optional": opt_items,
    }
