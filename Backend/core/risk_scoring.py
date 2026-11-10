"""
AEGIS Risk Scoring Engine
Deterministic, explainable risk assessment following the approved formulas (FR-S1 to FR-S8, FR-E2).
"""

import math
from collections.abc import Sequence

from .models import (
    Assessment,
    BreakdownItem,
    CalculationStep,
    ParsedManifest,
    PermissionInfo,
)
from .permission_rules import PermissionKnowledgeBase, get_knowledge_base


def _round_half_up(val: float) -> int:
    """Implement exact arithmetic half-up rounding (floor(val + 0.5))."""
    return math.floor(val + 0.5)


def calculate_set_score(items: Sequence[PermissionInfo]) -> tuple[float, int, int]:
    """
    Calculate the normalized risk score for a permission set (API or Host).
    R = 100 * sum(w_i) / (5 * n), with R = 0.0 when n = 0.
    Returns (score, total_weight, count).
    """
    n = len(items)
    if n == 0:
        return 0.0, 0, 0
    total_weight = sum(item.weight for item in items)
    score = 100.0 * total_weight / (5.0 * n)
    return score, total_weight, n


def assess_manifest(
    parsed: ParsedManifest,
    *,
    kb: PermissionKnowledgeBase | None = None,
) -> Assessment:
    """
    Perform a complete, deterministic, and explainable risk assessment
    of an extension manifest.
    """
    if kb is None:
        kb = get_knowledge_base()

    # 1. Resolve requested API and Host permissions
    api_items: list[PermissionInfo] = [kb.info_for_api(name, kind="api") for name in parsed.api_permissions]
    host_items: list[PermissionInfo] = [kb.info_for_host(pat, kind="host") for pat in parsed.host_permissions]

    # Resolve optional permissions for potential score evaluation
    opt_api_items: list[PermissionInfo] = [
        kb.info_for_api(name, kind="optional_api") for name in parsed.optional_api_permissions
    ]
    opt_host_items: list[PermissionInfo] = [
        kb.info_for_host(pat, kind="optional_host") for pat in parsed.optional_host_permissions
    ]

    all_requested = api_items + host_items
    all_with_optional = all_requested + opt_api_items + opt_host_items

    # Track unrecognized permissions
    unrecognized: list[str] = [item.name for item in all_requested if not item.known]

    # 2. Evaluate Set Scores (R_api, R_host)
    r_api, sum_w_api, n_api = calculate_set_score(api_items)
    r_host, sum_w_host, n_host = calculate_set_score(host_items)

    calc_steps: list[CalculationStep] = []

    if n_api > 0:
        calc_steps.append(
            CalculationStep(
                step="R_api",
                formula="100 * sum(w_i) / (5 * n_api)",
                values=f"100 * {sum_w_api} / (5 * {n_api})",
                result=f"{r_api:.1f}",
            )
        )
    else:
        calc_steps.append(
            CalculationStep(
                step="R_api",
                formula="0 (no API permissions declared)",
                values="n_api = 0",
                result="0.0",
            )
        )

    if n_host > 0:
        calc_steps.append(
            CalculationStep(
                step="R_host",
                formula="100 * sum(w_i) / (5 * n_host)",
                values=f"100 * {sum_w_host} / (5 * {n_host})",
                result=f"{r_host:.1f}",
            )
        )
    else:
        calc_steps.append(
            CalculationStep(
                step="R_host",
                formula="0 (no host permissions declared)",
                values="n_host = 0",
                result="0.0",
            )
        )

    # 3. Blend Scores (S_base)
    if n_api > 0 and n_host > 0:
        s_base = 0.5 * r_api + 0.5 * r_host
        blend_weight = 0.5
        calc_steps.append(
            CalculationStep(
                step="S_base",
                formula="0.5 * R_api + 0.5 * R_host",
                values=f"0.5 * {r_api:.1f} + 0.5 * {r_host:.1f}",
                result=f"{s_base:.1f}",
            )
        )
    elif n_api > 0:
        s_base = r_api
        blend_weight = 1.0
        calc_steps.append(
            CalculationStep(
                step="S_base",
                formula="R_api (only API set present)",
                values=f"{r_api:.1f}",
                result=f"{s_base:.1f}",
            )
        )
    elif n_host > 0:
        s_base = r_host
        blend_weight = 1.0
        calc_steps.append(
            CalculationStep(
                step="S_base",
                formula="R_host (only host set present)",
                values=f"{r_host:.1f}",
                result=f"{s_base:.1f}",
            )
        )
    else:
        s_base = 0.0
        blend_weight = 0.0
        calc_steps.append(
            CalculationStep(
                step="S_base",
                formula="0.0 (no permissions requested)",
                values="empty sets",
                result="0.0",
            )
        )

    # 4. Floors Evaluation
    max_weight = max((item.weight for item in all_requested), default=0)
    critical_floor = kb.floors.get("critical_floor", 70)
    high_floor = kb.floors.get("high_floor", 40)

    critical_flags: list[str] = [
        f"Critical permission requested: {item.name}" for item in all_requested if item.weight == 5
    ]

    floor_applied = 0
    if max_weight >= 5:
        floor_applied = critical_floor
        calc_steps.append(
            CalculationStep(
                step="Floor",
                formula=f"Weight-5 permission present -> S >= {critical_floor}",
                values=f"max_weight = {max_weight}",
                result=f"{critical_floor}",
            )
        )
    elif max_weight == 4:
        floor_applied = high_floor
        calc_steps.append(
            CalculationStep(
                step="Floor",
                formula=f"Weight-4 permission present -> S >= {high_floor}",
                values=f"max_weight = {max_weight}",
                result=f"{high_floor}",
            )
        )
    else:
        calc_steps.append(
            CalculationStep(
                step="Floor",
                formula="No danger floor triggered",
                values=f"max_weight = {max_weight}",
                result="0",
            )
        )

    # 5. Pre-rounding and Final Rounding
    pre_round_score = max(s_base, float(floor_applied))
    final_score = min(100, max(0, _round_half_up(pre_round_score)))

    calc_steps.append(
        CalculationStep(
            step="Score",
            formula="round_half_up(max(S_base, Floor))",
            values=f"round_half_up(max({s_base:.1f}, {floor_applied}))",
            result=str(final_score),
        )
    )

    # 6. Breakdown (must sum to pre_round_score, FR-S7)
    breakdown: list[BreakdownItem] = []

    # API contributions
    if n_api > 0:
        for item in api_items:
            contrib = blend_weight * 100.0 * item.weight / (5.0 * n_api)
            breakdown.append(
                BreakdownItem(
                    label=item.name,
                    contribution=round(contrib, 1),
                    kind="api",
                )
            )

    # Host contributions
    if n_host > 0:
        for item in host_items:
            contrib = blend_weight * 100.0 * item.weight / (5.0 * n_host)
            breakdown.append(
                BreakdownItem(
                    label=item.name,
                    contribution=round(contrib, 1),
                    kind="host",
                )
            )

    # Floor adjustment contribution
    if floor_applied > s_base:
        floor_diff = float(floor_applied) - s_base
        breakdown.append(
            BreakdownItem(
                label="High-weight permission floor",
                contribution=round(floor_diff, 1),
                kind="floor",
            )
        )

    # Sort descending by contribution
    breakdown.sort(key=lambda b: b.contribution, reverse=True)

    # 7. Potential Score (including optional permissions at full weight)
    comb_api_items = api_items + opt_api_items
    comb_host_items = host_items + opt_host_items
    r_comb_api, _, n_c_api = calculate_set_score(comb_api_items)
    r_comb_host, _, n_c_host = calculate_set_score(comb_host_items)

    if n_c_api > 0 and n_c_host > 0:
        s_comb_base = 0.5 * r_comb_api + 0.5 * r_comb_host
    elif n_c_api > 0:
        s_comb_base = r_comb_api
    elif n_c_host > 0:
        s_comb_base = r_comb_host
    else:
        s_comb_base = 0.0

    comb_max_w = max((item.weight for item in all_with_optional), default=0)
    comb_floor = 0
    if comb_max_w >= 5:
        comb_floor = critical_floor
    elif comb_max_w == 4:
        comb_floor = high_floor

    potential_score = min(100, max(0, _round_half_up(max(s_comb_base, float(comb_floor)))))

    # 8. Determine Risk Level
    low_max = kb.thresholds.get("low_max", 34)
    mid_max = kb.thresholds.get("mid_max", 69)

    if final_score <= low_max:
        risk_level = "low"
    elif final_score <= mid_max:
        risk_level = "medium"
    else:
        risk_level = "high"

    # 9. Notes & Plain Summary (FR-E9)
    notes: list[str] = []
    if len(all_requested) == 0:
        notes.append("This extension declares no permissions.")
        plain_summary = "This extension declares no permissions (low exposure)."
    else:
        # Build plain language summary without AI
        summary_parts = []
        # Check high impact host access
        has_all_sites = any(item.tier and item.tier.value == "all_sites" for item in host_items)
        if has_all_sites:
            summary_parts.append("Can read and change data on all websites you visit (high exposure).")
        elif len(host_items) > 0:
            summary_parts.append(f"Can access data on {len(host_items)} specific website match pattern(s).")

        # Check critical APIs
        high_weight_apis = [item.name for item in api_items if item.weight >= 4]
        if high_weight_apis:
            names_str = ", ".join(high_weight_apis[:3])
            summary_parts.append(f"Requests high-exposure browser capabilities ({names_str}).")

        if not summary_parts:
            summary_parts.append(f"Requests {len(all_requested)} permission(s) with minimal broad exposure risk.")

        plain_summary = " ".join(summary_parts)

    return Assessment(
        formula_version=kb.formula_version,
        knowledge_version=kb.knowledge_version,
        risk_score=final_score,
        risk_level=risk_level,
        thresholds={"low_max": low_max, "mid_max": mid_max},
        api_score=round(r_api, 1),
        host_score=round(r_host, 1),
        max_weight=max_weight,
        critical_flags=critical_flags,
        breakdown=breakdown,
        potential_score=potential_score,
        calculation=calc_steps,
        plain_summary=plain_summary,
        notes=notes,
        unrecognized=unrecognized,
        excess_score=None,
        evidence_coverage=None,
    )

