from Backend.core.manifest_parser import PLACEHOLDER_REGEX, TRANSLATED_DESC_FALLBACK
"""
AEGIS History Backup & Migration Router (Backend/app/routers/history.py)
Provides Export and Import of extension version history as JSON backups (Milestone 1c).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from Backend.app.db import db_export_all_history, db_import_history_data
from Backend.app.deps import CurrentUser, get_optional_user
from Backend.app.logging_setup import logger

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/export")
async def export_history(
    user: CurrentUser | None = Depends(get_optional_user),
) -> dict[str, Any]:
    """Exports all stored extensions and their complete snapshot version history as JSON."""
    user_id = user.id if user else None
    try:
        data = db_export_all_history(user_id=user_id)
        for ext in data.get("extensions", []):
            if ext.get("name") and PLACEHOLDER_REGEX.match(str(ext["name"]).strip()):
                ext["name"] = ext.get("store_id") or "Unnamed Extension"
            if ext.get("description") and PLACEHOLDER_REGEX.match(str(ext["description"]).strip()):
                ext["description"] = TRANSLATED_DESC_FALLBACK
            for snap in ext.get("snapshots", []):
                if snap.get("name") and PLACEHOLDER_REGEX.match(str(snap["name"]).strip()):
                    snap["name"] = ext.get("store_id") or "Unnamed Extension"
                if snap.get("description") and PLACEHOLDER_REGEX.match(str(snap["description"]).strip()):
                    snap["description"] = TRANSLATED_DESC_FALLBACK
        return data
    except Exception as exc:
        logger.error(f"Error exporting history: {exc}")
        raise HTTPException(status_code=500, detail="Failed to export snapshot history.")


@router.post("/import")
async def import_history(
    payload: dict[str, Any],
    user: CurrentUser | None = Depends(get_optional_user),
) -> dict[str, Any]:
    """
    Imports extension snapshots from a backup JSON.
    Appends new snapshots, skips identical hashes, and flags different hashes on existing versions.
    """
    user_id = user.id if user else "00000000-0000-0000-0000-000000000001"
    if not isinstance(payload, dict) or "extensions" not in payload:
        raise HTTPException(
            status_code=422,
            detail="Invalid history backup payload. Missing 'extensions' array.",
        )

    try:
        res = db_import_history_data(payload, user_id=user_id)
        return {
            "status": "success",
            "message": "Snapshot history imported successfully.",
            **res,
        }
    except Exception as exc:
        logger.error(f"Error importing history: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to import history: {exc}")
