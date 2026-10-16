"""
AEGIS Database Access Repository (Backend/app/repo.py)
Sole point of database access; executes queries using user-scoped Supabase client or local mock store (PRD Part 2c s4).
"""

import uuid
from typing import Any

from Backend.app.errors import ConflictError, NotFoundError
from Backend.app.logging_setup import logger
from Backend.core.models import ParsedManifest
from supabase import Client

# In-memory mock store for offline testing and local verification
_MOCK_STORE: dict[str, dict[str, Any]] = {
    "extensions": {},
    "snapshots": {},
    "creep_records": {},
}


def reset_mock_store() -> None:
    """Resets in-memory mock store for test isolation."""
    global _MOCK_STORE
    _MOCK_STORE = {"extensions": {}, "snapshots": {}, "creep_records": {}}


class Repository:
    def __init__(self, client: Client | None = None, use_mock: bool = False):
        self.client = client
        self.use_mock = use_mock or (client is None)

    # =========================================================================
    # 1. Extensions
    # =========================================================================
    def list_extensions(self, user_id: str, limit: int = 200) -> list[dict[str, Any]]:
        if self.use_mock:
            user_exts = [
                ext
                for ext in _MOCK_STORE["extensions"].values()
                if ext["user_id"] == user_id or ext.get("is_public", False)
            ]
            return user_exts[:limit]

        try:
            assert self.client is not None
            resp = (
                self.client.table("extensions")
                .select("id, name, browser, store_id, is_public, icon_path, updated_at")
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception as exc:
            logger.warning(f"Error fetching extensions: {exc}")
            return []

    def get_extension(self, user_id: str, ext_id: str) -> dict[str, Any]:
        if self.use_mock:
            ext = _MOCK_STORE["extensions"].get(ext_id)
            if not ext or (ext["user_id"] != user_id and not ext.get("is_public", False)):
                raise NotFoundError("Extension not found.")
            return ext

        try:
            assert self.client is not None
            resp = self.client.table("extensions").select("*").eq("id", ext_id).limit(1).execute()
            if not resp.data:
                raise NotFoundError("Extension not found.")
            return resp.data[0]
        except Exception as exc:
            if isinstance(exc, NotFoundError):
                raise exc
            logger.warning(f"Error getting extension {ext_id}: {exc}")
            raise NotFoundError("Extension not found.")

    def find_extension_by_store_or_name(
        self, user_id: str, browser: str, store_id: str | None, name: str
    ) -> dict[str, Any] | None:
        if self.use_mock:
            for ext in _MOCK_STORE["extensions"].values():
                if ext["user_id"] == user_id and ext["browser"] == browser:
                    if store_id and ext.get("store_id") == store_id:
                        return ext
                    if not store_id and ext.get("name", "").lower() == name.lower():
                        return ext
            return None

        try:
            assert self.client is not None
            query = self.client.table("extensions").select("*").eq("browser", browser)
            if store_id:
                query = query.eq("store_id", store_id)
            else:
                query = query.ilike("name", name)

            resp = query.limit(1).execute()
            return resp.data[0] if resp.data else None
        except Exception as exc:
            logger.warning(f"Error finding extension: {exc}")
            return None

    def insert_extension(
        self, user_id: str, browser: str, store_id: str | None, name: str, icon_path: str | None = None
    ) -> dict[str, Any]:
        ext_id = str(uuid.uuid4())
        record = {
            "id": ext_id,
            "user_id": user_id,
            "browser": browser,
            "store_id": store_id,
            "name": name,
            "icon_path": icon_path,
            "is_public": False,
            "source": "user",
        }

        if self.use_mock:
            _MOCK_STORE["extensions"][ext_id] = record
            return record

        try:
            assert self.client is not None
            resp = self.client.table("extensions").insert(record).execute()
            return resp.data[0] if resp.data else record
        except Exception as exc:
            logger.error(f"Error inserting extension: {exc}")
            raise exc

    def delete_extension(self, user_id: str, ext_id: str) -> None:
        if self.use_mock:
            ext = _MOCK_STORE["extensions"].get(ext_id)
            if not ext or ext["user_id"] != user_id:
                raise NotFoundError("Extension not found.")
            del _MOCK_STORE["extensions"][ext_id]
            # Cascade snapshots
            to_del = [sid for sid, s in _MOCK_STORE["snapshots"].items() if s["extension_id"] == ext_id]
            for sid in to_del:
                del _MOCK_STORE["snapshots"][sid]
            return

        try:
            assert self.client is not None
            resp = self.client.table("extensions").delete().eq("id", ext_id).execute()
            if not resp.data:
                raise NotFoundError("Extension not found.")
        except Exception as exc:
            if isinstance(exc, NotFoundError):
                raise exc
            logger.error(f"Error deleting extension {ext_id}: {exc}")
            raise NotFoundError("Extension not found.")

    # =========================================================================
    # 2. Snapshots
    # =========================================================================
    def get_latest_snapshot(self, user_id: str, ext_id: str) -> dict[str, Any] | None:
        snaps = self.list_snapshots(user_id, ext_id)
        return snaps[0] if snaps else None

    def list_snapshots(self, user_id: str, ext_id: str) -> list[dict[str, Any]]:
        if self.use_mock:
            snaps = [s for s in _MOCK_STORE["snapshots"].values() if s["extension_id"] == ext_id]
            # Sort newest version first
            snaps.sort(key=lambda s: (s.get("version_key") or (), s.get("captured_at", "")), reverse=True)
            return snaps

        try:
            assert self.client is not None
            resp = (
                self.client.table("extension_snapshots")
                .select("*")
                .eq("extension_id", ext_id)
                .order("version_key", desc=True, nullsfirst=False)
                .order("captured_at", desc=True)
                .execute()
            )
            return resp.data or []
        except Exception as exc:
            logger.warning(f"Error listing snapshots for {ext_id}: {exc}")
            return []

    def get_snapshot_by_version(self, user_id: str, ext_id: str, version: str) -> dict[str, Any]:
        if self.use_mock:
            for s in _MOCK_STORE["snapshots"].values():
                if s["extension_id"] == ext_id and s["version"] == version:
                    return s
            raise NotFoundError(f"Version {version} not found for extension.")

        try:
            assert self.client is not None
            resp = (
                self.client.table("extension_snapshots")
                .select("*")
                .eq("extension_id", ext_id)
                .eq("version", version)
                .limit(1)
                .execute()
            )
            if not resp.data:
                raise NotFoundError(f"Version {version} not found.")
            return resp.data[0]
        except Exception as exc:
            if isinstance(exc, NotFoundError):
                raise exc
            logger.warning(f"Error getting snapshot {version}: {exc}")
            raise NotFoundError(f"Version {version} not found.")

    def insert_snapshot(self, user_id: str, ext_id: str, manifest: ParsedManifest) -> tuple[dict[str, Any], bool]:
        """
        Inserts snapshot append-only.
        Returns (snapshot_record, created_boolean).
        Raises ConflictError if version exists with different SHA-256.
        """
        # Check existing version
        try:
            existing = self.get_snapshot_by_version(user_id, ext_id, manifest.version)
            if existing["manifest_sha256"] == manifest.sha256:
                return existing, False
            raise ConflictError("Version conflict: A different manifest with this version already exists.")
        except NotFoundError:
            pass

        snap_id = str(uuid.uuid4())
        record = {
            "id": snap_id,
            "extension_id": ext_id,
            "user_id": user_id,
            "version": manifest.version,
            "version_key": list(manifest.version_key) if manifest.version_key else None,
            "manifest_version": manifest.manifest_version,
            "name": manifest.name,
            "description": manifest.description,
            "api_permissions": sorted(list(manifest.api_permissions)),
            "host_permissions": sorted(list(manifest.host_permissions)),
            "optional_api_permissions": sorted(list(manifest.optional_api_permissions)),
            "optional_host_permissions": sorted(list(manifest.optional_host_permissions)),
            "content_script_matches": sorted(list(manifest.content_script_matches)),
            "features": sorted(list(manifest.features)),
            "manifest": manifest.model_dump(),
            "manifest_sha256": manifest.sha256,
        }

        if self.use_mock:
            _MOCK_STORE["snapshots"][snap_id] = record
            return record, True

        try:
            assert self.client is not None
            resp = self.client.table("extension_snapshots").insert(record).execute()
            return (resp.data[0] if resp.data else record), True
        except Exception as exc:
            logger.error(f"Error inserting snapshot: {exc}")
            raise exc
