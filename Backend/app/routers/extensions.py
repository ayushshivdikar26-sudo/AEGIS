from Backend.core.manifest_parser import PLACEHOLDER_REGEX, TRANSLATED_DESC_FALLBACK
"""
AEGIS Extensions Router (Backend/app/routers/extensions.py)
Contract v1 extension queries, permissions inspection, version diffing, and creep audits (PRD Part 2c s6).
"""

from fastapi import APIRouter, Depends, Query, Response, status

from Backend.app.deps import (
    CurrentUser,
    get_current_user,
    get_optional_user,
    get_user_db_client,
)
from Backend.app.cache import extension_list_cache
from Backend.app.db import pick_latest_snapshot
from Backend.app.errors import NotFoundError
from Backend.app.repo import Repository
from Backend.app.schemas import (
    ComparisonResponse,
    CreepAlignment,
    CreepResponse,
    ExtensionDetailResponse,
    ExtensionListItem,
    ExtensionsListResponse,
    PermissionsResponse,
    VersionsResponse,
)
from Backend.app.services.ai import get_ai_capabilities
from Backend.app.services.assessment import (
    compare_snapshot_rows,
    compute_snapshot_assessment,
    snapshot_row_to_parsed_manifest,
)
from Backend.app.services.justification import enrich_permissions_from_manifest
from Backend.core.justification_checker import alignment_for, check

router = APIRouter(prefix="/api/extensions", tags=["extensions"])


def get_repo(client=Depends(get_user_db_client)) -> Repository:
    return Repository(client=client)


@router.get("", response_model=ExtensionsListResponse)
async def list_extensions(
    response: Response,
    limit: int = Query(default=200, ge=1, le=200),
    user: CurrentUser | None = Depends(get_optional_user),
    repo: Repository = Depends(get_repo),
) -> ExtensionsListResponse:
    """Lists extensions for authenticated user or public catalogue."""
    user_id = user.id if user else "00000000-0000-0000-0000-000000000001"

    cached = extension_list_cache.get(user_id, limit=limit)
    if cached is not None:
        response.headers["X-AEGIS-Cache"] = "HIT"
        return cached

    response.headers["X-AEGIS-Cache"] = "MISS"
    ext_rows = repo.list_extensions(user_id, limit=limit)

    items = []
    for ext in ext_rows:
        ext_id = ext["id"]
        latest_snap = ext.get("latest_snapshot")
        if not latest_snap and ext.get("extension_snapshots"):
            latest_snap = pick_latest_snapshot(ext["extension_snapshots"])
        if not latest_snap and repo.client is None and not repo.use_mock:
            latest_snap = repo.get_latest_snapshot(user_id, ext_id)

        if latest_snap:
            assessment = compute_snapshot_assessment(latest_snap)
            score = assessment.get("risk_score", 0)
            level = assessment.get("risk_level", "low")
            version = latest_snap.get("version", "1.0")
        else:
            score = 0
            level = "low"
            version = "1.0"

        ext_name = ext.get("name", "Unknown")
        if ext_name and PLACEHOLDER_REGEX.match(ext_name.strip()):
            ext_name = ext.get("store_id") or "Unnamed Extension"

        items.append(
            ExtensionListItem(
                id=ext_id,
                name=ext_name,
                browser=ext.get("browser", "chrome"),
                version=version,
                icon_url=ext.get("icon_path"),
                risk_score=score,
                risk_level=level,
            )
        )

    result = ExtensionsListResponse(source="imported", extensions=items)
    extension_list_cache.set(user_id, result, limit=limit)
    return result


@router.get("/{id}", response_model=ExtensionDetailResponse)
async def get_extension_detail(
    id: str,
    user: CurrentUser | None = Depends(get_optional_user),
    repo: Repository = Depends(get_repo),
) -> ExtensionDetailResponse:
    """Get metadata and pure derived risk assessment for extension."""
    user_id = user.id if user else "00000000-0000-0000-0000-000000000001"
    ext = repo.get_extension(user_id, id)
    latest_snap = repo.get_latest_snapshot(user_id, id)

    if latest_snap:
        assessment = compute_snapshot_assessment(latest_snap)
        version = latest_snap.get("version", "1.0")
        desc_text = latest_snap.get("description")
        if desc_text and PLACEHOLDER_REGEX.match(desc_text.strip()):
            desc_text = ext.get("description") or TRANSLATED_DESC_FALLBACK
            if desc_text and PLACEHOLDER_REGEX.match(desc_text.strip()):
                desc_text = TRANSLATED_DESC_FALLBACK
        desc_origin = "manifest" if desc_text else "unavailable"
    else:
        assessment = {
            "formula_version": "1",
            "knowledge_version": "2026.10.1",
            "risk_score": 0,
            "risk_level": "low",
            "thresholds": {"low_max": 34, "mid_max": 69},
            "api_score": 0.0,
            "host_score": 0.0,
            "max_weight": 1,
            "critical_flags": [],
            "breakdown": [],
            "potential_score": 0,
            "plain_summary": "No permissions declared.",
            "notes": [],
            "unrecognized": [],
            "calculation": [],
        }
        version = "1.0"
        desc_text = None
        desc_origin = "unavailable"

    return ExtensionDetailResponse(
        id=ext["id"],
        name=(ext.get("store_id") or "Unnamed Extension") if PLACEHOLDER_REGEX.match(ext.get("name", "").strip()) else ext.get("name", "Unknown"),
        browser=ext.get("browser", "chrome"),
        version=version,
        icon_url=ext.get("icon_path"),
        developer=None,
        description={"text": desc_text, "origin": desc_origin},  # type: ignore[arg-type]
        capabilities=get_ai_capabilities(),  # type: ignore[arg-type]
        assessment=assessment,
    )


@router.get("/{id}/permissions", response_model=PermissionsResponse)
async def get_extension_permissions(
    id: str,
    user: CurrentUser | None = Depends(get_optional_user),
    repo: Repository = Depends(get_repo),
) -> PermissionsResponse:
    """Get grouped API, Host, and Optional permissions with justification metadata."""
    user_id = user.id if user else "00000000-0000-0000-0000-000000000001"
    ext = repo.get_extension(user_id, id)
    latest_snap = repo.get_latest_snapshot(user_id, id)

    if not latest_snap:
        return PermissionsResponse(api=[], host=[], optional=[])

    snap_dict = dict(latest_snap)
    if not snap_dict.get("description") and ext.get("description"):
        snap_dict["description"] = ext.get("description")

    parsed = snapshot_row_to_parsed_manifest(snap_dict)
    enriched = enrich_permissions_from_manifest(parsed)
    return PermissionsResponse(**enriched)  # type: ignore[arg-type]


@router.get("/{id}/versions", response_model=VersionsResponse)
async def list_extension_versions(
    id: str,
    user: CurrentUser | None = Depends(get_optional_user),
    repo: Repository = Depends(get_repo),
) -> VersionsResponse:
    """List all captured snapshots for an extension ordered newest first."""
    user_id = user.id if user else "00000000-0000-0000-0000-000000000001"
    repo.get_extension(user_id, id)
    snaps = repo.list_snapshots(user_id, id)

    items = []
    for s in snaps:
        score = s.get("risk_score")
        if score is None or score == 0:
            try:
                assessment = compute_snapshot_assessment(s)
                score = assessment.get("risk_score", 0)
            except Exception:
                score = 0
        items.append(
            {
                "version": s["version"],
                "released": str(s.get("captured_at", ""))[:10],
                "risk_score": score,
                "captured_at": str(s.get("captured_at", "")),
                "manifest_hash": str(s.get("manifest_sha256", "")),
                "is_suspicious": bool(s.get("is_suspicious", False)),
            }
        )
    return VersionsResponse(versions=items)  # type: ignore[arg-type]


@router.get("/{id}/compare", response_model=ComparisonResponse)
async def compare_extension_versions(
    id: str,
    from_version: str = Query(alias="from", min_length=1, max_length=64),
    to_version: str = Query(alias="to", min_length=1, max_length=64),
    user: CurrentUser | None = Depends(get_optional_user),
    repo: Repository = Depends(get_repo),
) -> ComparisonResponse:
    """Compare two snapshots using core set-theoretic diffing and host broadening rules."""
    user_id = user.id if user else "00000000-0000-0000-0000-000000000001"
    repo.get_extension(user_id, id)

    snap_old = repo.get_snapshot_by_version(user_id, id, from_version)
    snap_new = repo.get_snapshot_by_version(user_id, id, to_version)

    comp_dict = compare_snapshot_rows(snap_old, snap_new)

    return ComparisonResponse(
        **{
            "from": from_version,
            "to": to_version,
            "score_from": comp_dict["score_from"],
            "score_to": comp_dict["score_to"],
            "api": comp_dict["api"],
            "host": comp_dict["host"],
            "optional": comp_dict["optional"],
        }
    )


@router.get("/{id}/creep", response_model=CreepResponse)
async def get_extension_creep(
    id: str,
    user: CurrentUser | None = Depends(get_optional_user),
    repo: Repository = Depends(get_repo),
) -> CreepResponse:
    """Evaluate permission creep across the two most recent versions."""
    user_id = user.id if user else "00000000-0000-0000-0000-000000000001"
    ext = repo.get_extension(user_id, id)
    snaps = repo.list_snapshots(user_id, id)

    if len(snaps) < 2:
        return CreepResponse(
            available=False,
            reason="baseline_not_available",
        )

    snap_new = snaps[0]
    snap_old = snaps[1]
    comp_dict = compare_snapshot_rows(snap_old, snap_new)

    # Transform diff dict to CreepResponse format
    added_items = [
        {"name": i["name"], "kind": "api" if i in comp_dict["api"]["added"] else "host"}
        for i in (comp_dict["api"]["added"] + comp_dict["host"]["added"])
    ]
    removed_items = [
        {"name": i["name"], "kind": "api" if i in comp_dict["api"]["removed"] else "host"}
        for i in (comp_dict["api"]["removed"] + comp_dict["host"]["removed"])
    ]
    retained_items = [
        {"name": i["name"], "kind": "api" if i in comp_dict["api"]["retained"] else "host"}
        for i in (comp_dict["api"]["retained"] + comp_dict["host"]["retained"])
    ]

    snap_new_dict = dict(snap_new)
    if not snap_new_dict.get("description") and ext.get("description"):
        snap_new_dict["description"] = ext.get("description")
    parsed_new = snapshot_row_to_parsed_manifest(snap_new_dict)
    report_new = check(parsed_new)
    added_names = [i["name"] for i in added_items]
    alignment_dict = alignment_for(added_names, report_new)

    return CreepResponse(
        available=True,
        outcome=comp_dict["outcome"],
        score_from=comp_dict["score_from"],
        score_to=comp_dict["score_to"],
        summary=comp_dict["summary"],
        limitations=comp_dict["limitations"],
        added=added_items,
        removed=removed_items,
        retained=retained_items,
        broadened=comp_dict["host"].get("broadened", []),
        alignment=CreepAlignment(**alignment_dict),
    )


@router.post("/{id}/analyze")
async def analyze_extension(id: str) -> None:
    """Optional AI analysis stub (deferred to Milestone M8)."""
    raise NotFoundError("AI analysis is unavailable.", code="ai_unavailable")


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_extension(
    id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repo),
) -> Response:
    """Deletes the caller's extension and associated snapshots."""
    repo.delete_extension(user.id, id)
    extension_list_cache.invalidate(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
