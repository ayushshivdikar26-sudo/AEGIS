"""
AEGIS Justification Checker (Backend/core/justification_checker.py)
Deterministic, rule-based justification assessment following approved decision rules (Rules 1-6, H1-H3, FR-E1 to FR-E9).
Evaluates declared capabilities against stated extension description, recognized purpose tags, and manifest structure.
"""

import math
from typing import Any

from Backend.core.host_patterns import parse_match_pattern, scope_tier
from Backend.core.models import (
    Assessment,
    EvidenceItem,
    JustificationReport,
    JustifiedPermission,
    ParsedManifest,
    PermissionInfo,
    PurposeMatch,
    ScopeTier,
)
from Backend.core.permission_rules import PermissionKnowledgeBase, get_knowledge_base


def _round_half_up(val: float) -> int:
    """Implement exact arithmetic half-up rounding (floor(val + 0.5))."""
    return math.floor(val + 0.5)


def detect_purposes(text: str, kb: PermissionKnowledgeBase) -> tuple[list[PurposeMatch], set[str], bool]:
    """
    Scans extension text (name + description) for recognized purpose tag keywords.
    Returns (matched_purposes, union_of_typical_permissions, has_single_site_purpose).
    """
    text_lower = text.lower()
    matches: list[PurposeMatch] = []
    typical_perms: set[str] = set()
    has_single_site = False

    purposes = kb.get_purposes()
    for tag, data in purposes.items():
        label = data.get("label", tag)
        keywords = data.get("keywords", [])
        single_site = bool(data.get("single_site", False))

        for kw in keywords:
            if kw.lower() in text_lower:
                matches.append(PurposeMatch(tag=tag, label=label, matched_phrase=kw))
                typical_perms.update(data.get("typical_permissions", []))
                if single_site:
                    has_single_site = True
                break  # Record at most one match per purpose tag

    return matches, typical_perms, has_single_site


def extract_structural_evidence(parsed: ParsedManifest, kb: PermissionKnowledgeBase) -> dict[str, str]:
    """
    Inspects manifest structural features and maps justified permissions to triggering features.
    Returns dict mapping permission name -> structural feature name.
    """
    feature_map = kb.get_structural_evidence()
    justified_perms: dict[str, str] = {}

    for feat in parsed.features:
        if feat in feature_map:
            for perm in feature_map[feat]:
                justified_perms[perm] = feat

    # Content scripts structural presence
    if parsed.content_script_matches:
        justified_perms["activeTab"] = "content_scripts"

    return justified_perms


def evaluate_api_permission(
    info: PermissionInfo,
    *,
    description_insufficient: bool,
    missing_reason: str,
    matched_purposes: list[PurposeMatch],
    typical_perms: set[str],
    structural_perms: dict[str, str],
    kb: PermissionKnowledgeBase,
) -> JustifiedPermission:
    """
    Evaluates an API permission using Decision Rules 1-6 (first match wins).
    """
    name = info.name
    weight = info.weight
    alt = info.narrower_alternative or kb.get_narrower_alternative(name)

    # -------------------------------------------------------------------------
    # Rule 2 (R2): Manifest structural feature directly utilizes it -> justified, structural
    # -------------------------------------------------------------------------
    if name in structural_perms:
        feat = structural_perms[name]
        return JustifiedPermission(
            name=name,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="justified",
            reason=f"Manifest structural feature '{feat}' directly utilizes this permission.",
            rule_id="R2",
            evidence=[EvidenceItem(type="structural", text=f"Manifest structural feature '{feat}' is declared.")],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=alt,
        )

    # -------------------------------------------------------------------------
    # Rule 1 (R1): Weight 1 (low exposure, widely used) -> justified, common
    # -------------------------------------------------------------------------
    if weight == 1:
        return JustifiedPermission(
            name=name,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="justified",
            reason="Standard low-exposure permission widely used across extensions.",
            rule_id="R1",
            evidence=[EvidenceItem(type="common", text="Common capability with minimal risk exposure (weight 1).")],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=alt,
        )

    # -------------------------------------------------------------------------
    # Rule 3 (R3): A recognized purpose tag lists this permission -> justified, keyword
    # -------------------------------------------------------------------------
    if name in typical_perms:
        # Identify the triggering purpose match
        matching_purpose = next(
            (pm for pm in matched_purposes if name in kb.get_purposes().get(pm.tag, {}).get("typical_permissions", [])),
            matched_purposes[0] if matched_purposes else None,
        )
        tag_label = matching_purpose.label if matching_purpose else "Recognized Purpose"
        phrase = matching_purpose.matched_phrase if matching_purpose else "description keyword"

        return JustifiedPermission(
            name=name,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="justified",
            reason=f"Permission is standard for the recognized purpose '{tag_label}'.",
            rule_id="R3",
            evidence=[EvidenceItem(type="keyword", text=f"Description matched '{phrase}' for purpose '{tag_label}'.")],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=alt,
        )

    # -------------------------------------------------------------------------
    # Rule 4 (R4): Description missing, < 20 chars, or no purpose recognized -> unknown
    # (Never potentially_excessive under Rule 4, PRD line 227)
    # -------------------------------------------------------------------------
    if description_insufficient or len(matched_purposes) == 0:
        return JustifiedPermission(
            name=name,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="unknown",
            reason=missing_reason,
            rule_id="R4",
            evidence=[EvidenceItem(type="none", text=missing_reason)],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=alt,
        )

    # -------------------------------------------------------------------------
    # Rule 5 (R5): Purpose recognized, weight 4 or 5, unexplained, narrower alt exists
    # -> potentially_excessive
    # -------------------------------------------------------------------------
    if weight in (4, 5) and alt:
        return JustifiedPermission(
            name=name,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="potentially_excessive",
            reason=(
                f"High-exposure permission not accounted for by recognized purposes. "
                f"A narrower alternative '{alt}' is documented. "
                "This permission may still be legitimate for an undescribed feature."
            ),
            rule_id="R5",
            evidence=[EvidenceItem(type="keyword", text=f"Documented narrower alternative: '{alt}'.")],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=alt,
        )

    # -------------------------------------------------------------------------
    # Rule 6 (R6): Otherwise: weight >= 3 needs_review; else unknown
    # -------------------------------------------------------------------------
    if weight >= 3:
        return JustifiedPermission(
            name=name,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="needs_review",
            reason=f"Permission has weight {weight} and is not explained by recognized purposes or structural features.",
            rule_id="R6",
            evidence=[EvidenceItem(type="none", text="Requires manual review to verify functional necessity.")],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=alt,
        )

    return JustifiedPermission(
        name=name,
        kind=info.kind,
        weight=weight,
        risk_label=info.risk_label,
        status="unknown",
        reason="Not enough information to determine necessity.",
        rule_id="R6",
        evidence=[EvidenceItem(type="none", text="Weight 2 permission without specific keyword or structural match.")],
        allows=info.allows,
        legitimate_use=info.legitimate_use,
        source_url=info.source_url,
        reviewed=info.reviewed,
        narrower_alternative=alt,
    )


def evaluate_host_permission(
    info: PermissionInfo,
    *,
    description_text: str,
    description_insufficient: bool,
    missing_reason: str,
    matched_purposes: list[PurposeMatch],
    has_single_site_purpose: bool,
    structural_perms: dict[str, str],
    kb: PermissionKnowledgeBase,
) -> JustifiedPermission:
    """
    Evaluates a host pattern using Rules H1-H3 and base Rules 1, 4, 6.
    """
    pattern = info.name
    weight = info.weight
    parsed_pat = parse_match_pattern(pattern)
    tier = scope_tier(parsed_pat) if parsed_pat else ScopeTier.ALL_SITES
    alt = info.narrower_alternative or kb.get_narrower_alternative(tier.value)

    # -------------------------------------------------------------------------
    # Rule H1 (H1): Domain named in description -> justified, keyword
    # -------------------------------------------------------------------------
    if parsed_pat and parsed_pat.host and not parsed_pat.is_all_urls:
        clean_host = parsed_pat.host.lstrip("*.").lower()
        if clean_host and clean_host in description_text.lower():
            return JustifiedPermission(
                name=pattern,
                kind=info.kind,
                weight=weight,
                risk_label=info.risk_label,
                status="justified",
                reason=f"Target domain '{clean_host}' is explicitly named in the extension description.",
                rule_id="H1",
                evidence=[EvidenceItem(type="keyword", text=f"Description explicitly mentions '{clean_host}'.")],
                allows=info.allows,
                legitimate_use=info.legitimate_use,
                source_url=info.source_url,
                reviewed=info.reviewed,
                narrower_alternative=alt,
            )

    # -------------------------------------------------------------------------
    # Rule 1 (R1): Weight 1 (single_host) -> justified, common
    # -------------------------------------------------------------------------
    if weight == 1 or tier == ScopeTier.SINGLE_HOST:
        return JustifiedPermission(
            name=pattern,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="justified",
            reason="Narrow single-host pattern with low exposure.",
            rule_id="R1",
            evidence=[EvidenceItem(type="common", text="Single-host pattern (weight 1).")],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=alt,
        )

    # -------------------------------------------------------------------------
    # Rule 4 (R4): Description missing or < 20 chars -> unknown
    # (Never potentially_excessive under Rule 4, PRD line 227)
    # -------------------------------------------------------------------------
    if description_insufficient:
        return JustifiedPermission(
            name=pattern,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="unknown",
            reason=missing_reason,
            rule_id="R4",
            evidence=[EvidenceItem(type="none", text=missing_reason)],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=alt,
        )

    # -------------------------------------------------------------------------
    # Rule H2 (H2): all_sites on recognized single-site purpose -> potentially_excessive
    # -------------------------------------------------------------------------
    if tier == ScopeTier.ALL_SITES and has_single_site_purpose and not structural_perms:
        narrower = "specific site match patterns or activeTab"
        return JustifiedPermission(
            name=pattern,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="potentially_excessive",
            reason=(
                "Broad host access ('<all_urls>' or '*://*/*') requested for an extension with single-site purpose. "
                f"A narrower alternative '{narrower}' is documented. "
                "This access may still be legitimate for an undescribed feature."
            ),
            rule_id="H2",
            evidence=[
                EvidenceItem(
                    type="keyword", text="Single-site purpose recognized, but broad all-sites access requested."
                )
            ],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=narrower,
        )

    # -------------------------------------------------------------------------
    # Rule H3 (H3): Broad host access where narrower alternative activeTab exists
    # -------------------------------------------------------------------------
    if (
        tier
        in (
            ScopeTier.ALL_SITES,
            ScopeTier.SUFFIX_WIDE,
            ScopeTier.ALL_HOSTS_PARTIAL_PATH,
            ScopeTier.FILE_ACCESS,
        )
        or alt is not None
    ) and len(matched_purposes) > 0:
        narrower = alt or "specific site match patterns or activeTab"
        return JustifiedPermission(
            name=pattern,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="potentially_excessive",
            reason=(
                f"Broad host pattern '{pattern}' requested. "
                f"A narrower alternative '{narrower}' is documented. "
                "This access may still be legitimate for an undescribed feature."
            ),
            rule_id="H3",
            evidence=[EvidenceItem(type="keyword", text=f"Narrower alternative '{narrower}' available.")],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=narrower,
        )

    # -------------------------------------------------------------------------
    # Rule 4 (R4): No purpose recognized and no structural evidence -> unknown
    # -------------------------------------------------------------------------
    if len(matched_purposes) == 0:
        return JustifiedPermission(
            name=pattern,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="unknown",
            reason=missing_reason,
            rule_id="R4",
            evidence=[EvidenceItem(type="none", text=missing_reason)],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=alt,
        )

    # -------------------------------------------------------------------------
    # Rule 6 (R6): Otherwise: weight >= 3 needs_review; else unknown
    # -------------------------------------------------------------------------
    if weight >= 3:
        return JustifiedPermission(
            name=pattern,
            kind=info.kind,
            weight=weight,
            risk_label=info.risk_label,
            status="needs_review",
            reason=f"Host pattern has weight {weight} and is not explained by recognized purpose or structural features.",
            rule_id="R6",
            evidence=[EvidenceItem(type="none", text="Requires manual review to verify necessity.")],
            allows=info.allows,
            legitimate_use=info.legitimate_use,
            source_url=info.source_url,
            reviewed=info.reviewed,
            narrower_alternative=alt,
        )

    return JustifiedPermission(
        name=pattern,
        kind=info.kind,
        weight=weight,
        risk_label=info.risk_label,
        status="unknown",
        reason="Not enough information to determine necessity.",
        rule_id="R6",
        evidence=[EvidenceItem(type="none", text="Host pattern without specific keyword match.")],
        allows=info.allows,
        legitimate_use=info.legitimate_use,
        source_url=info.source_url,
        reviewed=info.reviewed,
        narrower_alternative=alt,
    )


def check(
    parsed: ParsedManifest,
    assessment: Assessment | None = None,
    *,
    kb: PermissionKnowledgeBase | None = None,
) -> JustificationReport:
    """
    Performs deterministic justification evaluation across API, Host, and Optional permission sets (FR-E1 to FR-E9).
    """
    if kb is None:
        kb = get_knowledge_base()

    desc_raw = (parsed.description or "").strip()
    description_insufficient = len(desc_raw) < 20
    if not desc_raw:
        missing_reason = "Extension description is missing. Not enough information to judge."
    elif len(desc_raw) < 20:
        missing_reason = "Extension description is too brief (under 20 characters). Not enough information to judge."
    else:
        missing_reason = "No recognized purpose keywords found in the extension description."

    full_text = f"{parsed.name} {desc_raw}"
    matched_purposes, typical_perms, has_single_site = detect_purposes(full_text, kb)
    structural_perms = extract_structural_evidence(parsed, kb)

    # 1. API permissions
    justified_api: list[JustifiedPermission] = []
    for perm_name in sorted(parsed.api_permissions):
        info = kb.info_for_api(perm_name, kind="api")
        item = evaluate_api_permission(
            info,
            description_insufficient=description_insufficient,
            missing_reason=missing_reason,
            matched_purposes=matched_purposes,
            typical_perms=typical_perms,
            structural_perms=structural_perms,
            kb=kb,
        )
        justified_api.append(item)

    # 2. Host permissions
    justified_host: list[JustifiedPermission] = []
    for pat in sorted(parsed.host_permissions):
        info = kb.info_for_host(pat, kind="host")
        item = evaluate_host_permission(
            info,
            description_text=desc_raw,
            description_insufficient=description_insufficient,
            missing_reason=missing_reason,
            matched_purposes=matched_purposes,
            has_single_site_purpose=has_single_site,
            structural_perms=structural_perms,
            kb=kb,
        )
        justified_host.append(item)

    # 3. Optional permissions (API + Host)
    justified_optional: list[JustifiedPermission] = []
    for opt_name in sorted(parsed.optional_api_permissions):
        info = kb.info_for_api(opt_name, kind="optional_api")
        item = evaluate_api_permission(
            info,
            description_insufficient=description_insufficient,
            missing_reason=missing_reason,
            matched_purposes=matched_purposes,
            typical_perms=typical_perms,
            structural_perms=structural_perms,
            kb=kb,
        )
        justified_optional.append(item)

    for opt_pat in sorted(parsed.optional_host_permissions):
        info = kb.info_for_host(opt_pat, kind="optional_host")
        item = evaluate_host_permission(
            info,
            description_text=desc_raw,
            description_insufficient=description_insufficient,
            missing_reason=missing_reason,
            matched_purposes=matched_purposes,
            has_single_site_purpose=has_single_site,
            structural_perms=structural_perms,
            kb=kb,
        )
        justified_optional.append(item)

    # -------------------------------------------------------------------------
    # 4. Excess Score (J) and Evidence Coverage Calculation (PRD s4.5 line 233)
    # J = 100 * sum(w_i * m_i) / sum(w_i) over assessed items only
    # Multipliers: justified: 0, needs_review: 0.5, potentially_excessive: 1.0
    # unknown items excluded from both sums
    # -------------------------------------------------------------------------
    all_requested = justified_api + justified_host
    total_weight = sum(p.weight for p in all_requested)
    assessed_items = [p for p in all_requested if p.status != "unknown"]
    assessed_weight = sum(p.weight for p in assessed_items)

    if total_weight == 0:
        coverage = 1.0
        excess_score: float | None = 0.0
    else:
        coverage = round(assessed_weight / total_weight, 4)
        if coverage < 0.5:
            excess_score = None  # "Not enough evidence to estimate."
        else:
            multipliers = {"justified": 0.0, "needs_review": 0.5, "potentially_excessive": 1.0}
            weighted_excess = sum(p.weight * multipliers.get(p.status, 0.5) for p in assessed_items)
            raw_j = 100.0 * weighted_excess / assessed_weight
            excess_score = float(_round_half_up(raw_j))

    return JustificationReport(
        api=justified_api,
        host=justified_host,
        optional=justified_optional,
        purposes=matched_purposes,
        excess_score=excess_score,
        evidence_coverage=coverage,
    )


def alignment_for(added_items: list[Any], report: JustificationReport) -> dict[str, str]:
    """
    Evaluates permission creep alignment for added items against justification report (PRD s4.5 line 235).
    """
    if not added_items:
        return {"status": "consistent", "text": "No permissions added in this version."}

    report_map = {p.name: p.status for p in report.api + report.host + report.optional}
    added_statuses = [report_map.get(getattr(i, "name", str(i)), "unknown") for i in added_items]

    if all(st == "justified" for st in added_statuses):
        return {
            "status": "consistent",
            "text": "Added permissions align with the extension's stated purpose and structure.",
        }
    if any(st == "potentially_excessive" for st in added_statuses):
        return {
            "status": "inconsistent",
            "text": "One or more added permissions exceed the capabilities explained by the stated purpose.",
        }
    return {
        "status": "unclear",
        "text": "Permission alignment with extension purpose is unclear or requires review.",
    }


def generate_plain_summary(
    parsed: ParsedManifest,
    report: JustificationReport,
    assessment: Assessment | None = None,
) -> str:
    """
    Constructs a deterministic, template-built summary for non-experts without AI (FR-E9).
    """
    if not parsed.api_permissions and not parsed.host_permissions:
        return "This extension declares no permissions."

    sentences: list[str] = []

    # 1. Host exposure
    all_sites = any(p.name in ("<all_urls>", "*://*/*") or "all_sites" in (p.allows.lower()) for p in report.host)
    if all_sites:
        sentences.append("This extension can read and change data on every website you visit (high exposure).")
    elif report.host:
        hosts_count = len(report.host)
        plural = "s" if hosts_count > 1 else ""
        sentences.append(f"This extension requests access to {hosts_count} specific website domain{plural}.")

    # 2. Key capabilities requested
    high_apis = [p for p in report.api if p.weight >= 4]
    if high_apis:
        names = ", ".join(f"'{p.name}'" for p in high_apis[:3])
        sentences.append(f"It requests sensitive browser capabilities including {names}.")
    elif report.api:
        low_names = ", ".join(f"'{p.name}'" for p in report.api[:3])
        sentences.append(f"It uses standard extension capabilities ({low_names}).")

    # 3. Justification summary
    excessive = [p for p in report.api + report.host if p.status == "potentially_excessive"]
    if excessive:
        excessive_names = ", ".join(f"'{p.name}'" for p in excessive[:2])
        sentences.append(f"Capabilities such as {excessive_names} appear broader than needed for the stated purpose.")

    return " ".join(sentences)
