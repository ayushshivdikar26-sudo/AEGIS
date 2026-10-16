"""
AEGIS Version Comparison & Permission Creep Detector
Compares manifest snapshots, detects host scope broadening, and assesses permission creep (FR-V1 to FR-V7).
"""

from .host_patterns import covers, scope_tier
from .models import (
    BroadenedItem,
    Comparison,
    ComparisonGroup,
    ComparisonItem,
    CreepAssessment,
    CreepTrigger,
    HostComparisonGroup,
    ParsedManifest,
)
from .permission_rules import PermissionKnowledgeBase, get_knowledge_base
from .risk_scoring import assess_manifest

OUTCOME_NO_SIGNIFICANT = "No significant permission creep detected"
OUTCOME_NEEDS_REVIEW = "Permission changes require review"
OUTCOME_SIGNIFICANT_INCREASE = "Significant increase in assessed permission exposure"

STANDARD_LIMITATIONS = [
    "Manifest lists requested capabilities, not proof of use.",
    "AEGIS does not inspect extension code.",
    "Descriptions are claims, not proof of intent.",
    "Optional permissions require explicit runtime user consent.",
    "Risk scores are heuristics under formula version 1.",
]

TIER_ORDER = [
    "single_host",
    "domain_wide",
    "suffix_wide",
    "all_hosts_partial_path",
    "file_access",
    "all_sites",
]


def _build_comparison_item(
    name: str,
    kind: str,
    source: str,
    kb: PermissionKnowledgeBase,
    already_covered_by: str | None = None,
) -> ComparisonItem:
    """Construct a ComparisonItem enriched with knowledge base metadata."""
    if kind in ("api", "optional_api"):
        info = kb.info_for_api(name, kind=kind)
    else:
        info = kb.info_for_host(name, kind=kind)

    return ComparisonItem(
        name=name,
        risk_label=info.risk_label,
        weight=info.weight,
        kind=kind,
        source=source,
        already_covered_by=already_covered_by,
    )


def compare(
    old: ParsedManifest,
    new: ParsedManifest,
    *,
    kb: PermissionKnowledgeBase | None = None,
) -> Comparison:
    """
    Compare two parsed manifests and return a structured diff covering API,
    host, and optional permissions with host broadening detection.
    """
    if kb is None:
        kb = get_knowledge_base()

    # Calculate risk scores on both sides using identical rules
    assessment_from = assess_manifest(old, kb=kb)
    assessment_to = assess_manifest(new, kb=kb)

    # 1. API permissions diff
    old_api = set(old.api_permissions)
    new_api = set(new.api_permissions)
    api_added = sorted(new_api - old_api)
    api_removed = sorted(old_api - new_api)
    api_retained = sorted(new_api & old_api)

    api_group = ComparisonGroup(
        added=[_build_comparison_item(p, "api", "permissions", kb) for p in api_added],
        removed=[_build_comparison_item(p, "api", "permissions", kb) for p in api_removed],
        retained=[_build_comparison_item(p, "api", "permissions", kb) for p in api_retained],
    )

    # 2. Host permissions diff & broadening
    old_host = set(old.host_permissions)
    new_host = set(new.host_permissions)
    host_added = sorted(new_host - old_host)
    host_removed = sorted(old_host - new_host)
    host_retained = sorted(new_host & old_host)

    # Detect broadening: added pattern 'a' covers removed pattern 'o'
    broadened: list[BroadenedItem] = []
    for a in host_added:
        for o in host_removed:
            if a != o and covers(a, o):
                t_old = scope_tier(o).value
                t_new = scope_tier(a).value
                explanation = f"Host access broadened from '{o}' ({t_old}) to '{a}' ({t_new})"
                broadened.append(
                    BroadenedItem(
                        from_pattern=o,
                        to_pattern=a,
                        from_tier=t_old,
                        to_tier=t_new,
                        explanation=explanation,
                    )
                )

    # Check if added patterns were already covered by retained patterns
    host_added_items: list[ComparisonItem] = []
    for a in host_added:
        covered_by: str | None = None
        for r in host_retained:
            if covers(r, a):
                covered_by = r
                break
        host_added_items.append(
            _build_comparison_item(
                a,
                "host",
                "host_permissions",
                kb,
                already_covered_by=covered_by,
            )
        )

    host_group = HostComparisonGroup(
        added=host_added_items,
        removed=[_build_comparison_item(p, "host", "host_permissions", kb) for p in host_removed],
        retained=[_build_comparison_item(p, "host", "host_permissions", kb) for p in host_retained],
        broadened=broadened,
    )

    # 3. Optional permissions diff (combining optional api and optional host)
    old_opt_api = set(old.optional_api_permissions)
    new_opt_api = set(new.optional_api_permissions)
    old_opt_host = set(old.optional_host_permissions)
    new_opt_host = set(new.optional_host_permissions)

    opt_added_api = sorted(new_opt_api - old_opt_api)
    opt_removed_api = sorted(old_opt_api - new_opt_api)
    opt_retained_api = sorted(new_opt_api & old_opt_api)

    opt_added_host = sorted(new_opt_host - old_opt_host)
    opt_removed_host = sorted(old_opt_host - new_opt_host)
    opt_retained_host = sorted(new_opt_host & old_opt_host)

    opt_added = [_build_comparison_item(p, "optional_api", "optional_permissions", kb) for p in opt_added_api] + [
        _build_comparison_item(p, "optional_host", "optional_permissions", kb) for p in opt_added_host
    ]
    opt_removed = [_build_comparison_item(p, "optional_api", "optional_permissions", kb) for p in opt_removed_api] + [
        _build_comparison_item(p, "optional_host", "optional_permissions", kb) for p in opt_removed_host
    ]
    opt_retained = [_build_comparison_item(p, "optional_api", "optional_permissions", kb) for p in opt_retained_api] + [
        _build_comparison_item(p, "optional_host", "optional_permissions", kb) for p in opt_retained_host
    ]

    opt_group = ComparisonGroup(
        added=opt_added,
        removed=opt_removed,
        retained=opt_retained,
    )

    return Comparison(
        from_version=old.version,
        to_version=new.version,
        score_from=assessment_from.risk_score,
        score_to=assessment_to.risk_score,
        api=api_group,
        host=host_group,
        optional=opt_group,
    )


def assess_creep(
    comparison: Comparison,
    *,
    alignment: dict[str, str] | None = None,
    kb: PermissionKnowledgeBase | None = None,
) -> CreepAssessment:
    """
    Evaluate permission creep rules against version comparison results.
    Produces an audited, explainable outcome with rule triggers.
    """
    if kb is None:
        kb = get_knowledge_base()

    delta = comparison.score_to - comparison.score_from
    delta_review = kb.creep_config.get("delta_review", 5)
    delta_significant = kb.creep_config.get("delta_significant", 15)

    all_added = comparison.api.added + comparison.host.added + comparison.optional.added
    all_removed = comparison.api.removed + comparison.host.removed + comparison.optional.removed

    triggers: list[CreepTrigger] = []

    # Check Significant Increase Conditions
    is_significant = False

    if delta >= delta_significant:
        is_significant = True
        triggers.append(
            CreepTrigger(
                rule="Delta threshold exceeded",
                observed=f"Risk score increase of {delta} points (from {comparison.score_from} to {comparison.score_to})",
                threshold=f"delta >= {delta_significant}",
            )
        )

    # Added weight-5 permission
    weight_5_added = [item.name for item in all_added if item.weight == 5]
    if weight_5_added:
        is_significant = True
        triggers.append(
            CreepTrigger(
                rule="Critical permission added",
                observed=f"Critical weight-5 permission(s) added: {', '.join(weight_5_added)}",
                threshold="added weight == 5",
            )
        )

    # Broadened to weight-5 tier
    for b in comparison.host.broadened:
        tier_weight = kb.host_tier_weights.get(b.to_tier, 0)
        if tier_weight == 5:
            is_significant = True
            triggers.append(
                CreepTrigger(
                    rule="Broadened to critical tier",
                    observed=f"Host access broadened to critical tier '{b.to_tier}' ({b.to_pattern})",
                    threshold="broadened tier weight == 5",
                )
            )

    # Moved up into high risk level
    mid_max = kb.thresholds.get("mid_max", 69)
    if comparison.score_from <= mid_max and comparison.score_to > mid_max:
        is_significant = True
        triggers.append(
            CreepTrigger(
                rule="Risk tier escalation",
                observed=f"Score crossed threshold into High risk level ({comparison.score_from} -> {comparison.score_to})",
                threshold=f"score_to > {mid_max}",
            )
        )

    # Check Needs Review Conditions if not already significant
    is_review = False
    if not is_significant:
        if delta >= delta_review:
            is_review = True
            triggers.append(
                CreepTrigger(
                    rule="Moderate delta increase",
                    observed=f"Risk score increase of {delta} points",
                    threshold=f"delta >= {delta_review}",
                )
            )

        weight_3_plus_added = [item.name for item in all_added if item.weight >= 3]
        if weight_3_plus_added:
            is_review = True
            triggers.append(
                CreepTrigger(
                    rule="Medium/High permission added",
                    observed=f"Added permission(s) with weight >= 3: {', '.join(weight_3_plus_added)}",
                    threshold="added weight >= 3",
                )
            )

        # Broadening to a wider tier
        for b in comparison.host.broadened:
            idx_from = TIER_ORDER.index(b.from_tier) if b.from_tier in TIER_ORDER else 0
            idx_to = TIER_ORDER.index(b.to_tier) if b.to_tier in TIER_ORDER else 0
            if idx_to > idx_from:
                is_review = True
                triggers.append(
                    CreepTrigger(
                        rule="Host scope broadening",
                        observed=f"Host access widened from {b.from_tier} to {b.to_tier}",
                        threshold="tier_to > tier_from",
                    )
                )

        unrecognized_added = [
            item.name
            for item in all_added
            if not (
                kb.info_for_api(item.name, kind=item.kind).known
                if item.kind in ("api", "optional_api")
                else kb.info_for_host(item.name, kind=item.kind).known
            )
        ]
        if unrecognized_added:
            is_review = True
            triggers.append(
                CreepTrigger(
                    rule="Unrecognized permission added",
                    observed=f"Added unrecognized permission(s): {', '.join(unrecognized_added)}",
                    threshold="added permission is unrecognized",
                )
            )

    if is_significant:
        outcome = OUTCOME_SIGNIFICANT_INCREASE
    elif is_review:
        outcome = OUTCOME_NEEDS_REVIEW
    else:
        outcome = OUTCOME_NO_SIGNIFICANT
        if not triggers:
            triggers.append(
                CreepTrigger(
                    rule="Baseline comparison",
                    observed=f"Delta is {delta} points; no dangerous additions or broadening observed",
                    threshold=f"delta < {delta_review}",
                )
            )

    # Explanations of what added access could allow
    could_allow: list[str] = []
    for item in all_added:
        if item.kind in ("api", "optional_api"):
            info = kb.info_for_api(item.name, kind=item.kind)
        else:
            info = kb.info_for_host(item.name, kind=item.kind)
        could_allow.append(f"{item.name}: {info.allows}")

    # Summary sentence
    summary_parts = []
    summary_parts.append(f"{len(all_added)} added, {len(all_removed)} removed")
    if comparison.host.broadened:
        summary_parts.append(f"{len(comparison.host.broadened)} host scope(s) broadened")
    summary_parts.append(f"Risk score moved from {comparison.score_from} to {comparison.score_to}.")
    summary = ". ".join(summary_parts)

    final_alignment = (
        alignment
        if alignment is not None
        else {
            "status": "unclear",
            "text": "Purpose alignment has not been evaluated.",
        }
    )

    return CreepAssessment(
        available=True,
        reason=None,
        outcome=outcome,
        summary=summary,
        added=all_added,
        removed=all_removed,
        broadened=comparison.host.broadened,
        could_allow=could_allow,
        alignment=final_alignment,
        triggers=triggers,
        score_from=comparison.score_from,
        score_to=comparison.score_to,
        limitations=STANDARD_LIMITATIONS,
    )
