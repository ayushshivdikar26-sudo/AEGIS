from Backend.core.manifest_parser import PLACEHOLDER_REGEX, TRANSLATED_DESC_FALLBACK
"""
AEGIS AI Overview Router (Backend/app/routers/ai.py)
Server-side endpoint for AI-generated security overviews.
Enforces per-IP rate limiting, DB caching, prompt injection defense, and input validation (Milestone 2).
"""

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request

from Backend.app.db import (
    db_get_ai_overview,
    db_save_ai_overview,
)
from Backend.app.deps import (
    CurrentUser,
    get_optional_user,
    get_user_db_client,
)
from Backend.app.errors import NotFoundError
from Backend.app.rate_limiter import limiter
from Backend.app.repo import Repository
from Backend.app.schemas import AIOverviewRequest, AIOverviewResponse
from Backend.app.services.ai import (
    PROMPT_VERSION,
    call_groq_api,
    get_ai_capabilities,
)
from Backend.app.services.assessment import compare_snapshot_rows

router = APIRouter(prefix="/api/ai-overview", tags=["ai-overview"])

# In-flight task de-duplication for concurrent identical requests
_in_flight_tasks: dict[tuple[str, str], asyncio.Task] = {}
_in_flight_lock = asyncio.Lock()


def get_repo(client=Depends(get_user_db_client)) -> Repository:
    return Repository(client=client)


@router.get("/status")
async def ai_status():
    """Returns AI service availability and model status."""
    return get_ai_capabilities()


@router.post("", response_model=AIOverviewResponse)
@limiter.limit("15/minute")
async def generate_ai_overview(
    request: Request,
    payload: AIOverviewRequest,
    user: CurrentUser | None = Depends(get_optional_user),
    repo: Repository = Depends(get_repo),
) -> AIOverviewResponse:
    """
    Generates or retrieves a cached AI-powered risk overview for an extension.
    Reads data strictly server-side from the database to defend against prompt injection.
    """
    user_id = user.id if user else "00000000-0000-0000-0000-000000000001"
    ext_id = payload.extension_id

    # 1. Fetch extension metadata strictly from DB
    try:
        ext = repo.get_extension(user_id, ext_id)
    except NotFoundError:
        raise NotFoundError("Extension not found.") from None

    # 2. Resolve version and snapshot
    snapshots = repo.list_snapshots(user_id, ext_id)
    if not snapshots:
        raise NotFoundError("No snapshot data available for this extension.")

    target_snap = None
    if payload.version:
        for s in snapshots:
            if s.get("version") == payload.version:
                target_snap = s
                break
        if not target_snap:
            raise NotFoundError(f"Version {payload.version} not found for this extension.")
    else:
        target_snap = snapshots[0]

    version_str = target_snap.get("version", "1.0")
    manifest_hash = target_snap.get("manifest_sha256", f"hash-{ext_id}-{version_str}")

    # 3. Check DB Cache if force_refresh is not requested
    if not payload.force_refresh:
        cached_data = db_get_ai_overview(ext_id, version_str, manifest_hash, PROMPT_VERSION)
        if cached_data:
            return AIOverviewResponse(
                extension_id=ext_id,
                version=version_str,
                summary=cached_data.get("summary", ""),
                permission_fit=cached_data.get("permission_fit", ""),
                creep_detected=cached_data.get("creep_detected", False),
                creep_risks=cached_data.get("creep_risks", []),
                recommended_actions=cached_data.get("recommended_actions", []),
                model=cached_data.get("model", "llama-3.1-8b-instant"),
                disclaimer=cached_data.get(
                    "disclaimer",
                    "AI-generated from the manifest and description. AEGIS does not inspect extension code.",
                ),
                cached=True,
            )

    # 4. Resolve creep information (comparing with older_version or immediate baseline)
    creep_info: dict[str, Any] = {"has_diff": False}
    older_snap = None

    if payload.older_version:
        for s in snapshots:
            if s.get("version") == payload.older_version:
                older_snap = s
                break
    elif len(snapshots) >= 2:
        # Default older snapshot is second-latest
        older_snap = snapshots[1]

    if older_snap and older_snap.get("version") != version_str:
        diff = compare_snapshot_rows(older_snap, target_snap)
        added_items = diff.get("api", {}).get("added", []) + diff.get("host", {}).get("added", [])
        broadened_items = diff.get("host", {}).get("broadened", [])

        added_names = [item["name"] for item in added_items]
        broadened_names = [item["name"] for item in broadened_items]

        creep_info = {
            "has_diff": bool(added_names or broadened_names),
            "older_version": older_snap.get("version"),
            "newer_version": version_str,
            "added": added_names,
            "broadened": broadened_names,
        }

    # 5. Extract manifest permissions from snapshot
    api_perms = target_snap.get("api_permissions") or []
    host_perms = target_snap.get("host_permissions") or []
    if isinstance(api_perms, str):
        import json as j

        api_perms = j.loads(api_perms)
    if isinstance(host_perms, str):
        import json as j

        host_perms = j.loads(host_perms)

    # 6. Call Groq API via AI Service with concurrent de-duplication
    snap_id = target_snap.get("id", version_str)
    flight_key = (ext_id, snap_id)

    async def _execute_call():
        return await call_groq_api(
            name=ext.get("name", "Unnamed Extension"),
            browser=ext.get("browser", "chrome"),
            version=version_str,
            description=(
                TRANSLATED_DESC_FALLBACK
                if (target_snap.get("description") and PLACEHOLDER_REGEX.match(str(target_snap.get("description")).strip()))
                else (target_snap.get("description") or ext.get("description"))
            ),
            api_permissions=api_perms,
            host_permissions=host_perms,
            creep_info=creep_info,
        )

    async with _in_flight_lock:
        if flight_key in _in_flight_tasks:
            task = _in_flight_tasks[flight_key]
        else:
            task = asyncio.create_task(_execute_call())
            _in_flight_tasks[flight_key] = task

    try:
        ai_output, model_used = await task
    finally:
        async with _in_flight_lock:
            if _in_flight_tasks.get(flight_key) is task and task.done():
                _in_flight_tasks.pop(flight_key, None)

    is_fallback = model_used.endswith("-fallback") or model_used.endswith("-mock")

    # 7. Save to DB Cache ONLY if not fallback (genuine Groq results are cached)
    if not is_fallback:
        cache_record = {
            "summary": ai_output.summary,
            "permission_fit": ai_output.permission_fit,
            "creep_detected": ai_output.creep_detected,
            "creep_risks": ai_output.creep_risks,
            "recommended_actions": ai_output.recommended_actions,
            "model": model_used,
            "disclaimer": "AI-generated from the manifest and description. AEGIS does not inspect extension code.",
        }
        db_save_ai_overview(ext_id, version_str, manifest_hash, PROMPT_VERSION, cache_record)

    return AIOverviewResponse(
        extension_id=ext_id,
        version=version_str,
        summary=ai_output.summary,
        permission_fit=ai_output.permission_fit,
        creep_detected=ai_output.creep_detected,
        creep_risks=ai_output.creep_risks,
        recommended_actions=ai_output.recommended_actions,
        model=model_used,
        cached=False,
        is_fallback=is_fallback,
    )
