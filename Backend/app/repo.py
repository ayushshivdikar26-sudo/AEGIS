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


def seed_mock_store_from_fixtures() -> None:
    """Populates in-memory store with real installed browser extensions, or fallback fixtures."""
    import json
    from pathlib import Path

    if _MOCK_STORE["extensions"]:
        return

    # 1. Attempt to scan real installed extensions from Chromium browsers on the system
    try:
        from Backend.app.services.browser_scanner import populate_installed_extensions_into_store

        count = populate_installed_extensions_into_store(_MOCK_STORE)
        if count > 0:
            return
    except Exception as exc:
        logger.warning(f"Error scanning installed browser extensions: {exc}")

    dataset_path = Path(__file__).resolve().parents[2] / "dev" / "mock-api" / "fixtures" / "dataset.json"
    if not dataset_path.exists():
        return

    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)

    user_id = "00000000-0000-0000-0000-000000000001"
    for ext in data.get("extensions", []):
        ext_id = ext["id"]
        desc_obj = ext.get("description", {})
        desc_text = desc_obj.get("text") if isinstance(desc_obj, dict) else str(desc_obj or "")

        _MOCK_STORE["extensions"][ext_id] = {
            "id": ext_id,
            "user_id": user_id,
            "browser": ext.get("browser", "chrome").lower().replace("google ", ""),
            "store_id": ext_id,
            "name": ext["name"],
            "is_public": True,
            "icon_path": ext.get("icon_url"),
            "description": desc_text,
            "updated_at": "2026-10-15T12:00:00Z",
        }

        perms = ext.get("permissions", {})
        versions_list = ext.get(
            "versions", [{"version": ext.get("version", "1.0.0"), "captured_at": "2026-10-15T12:00:00Z"}]
        )
        for v_entry in versions_list:
            v_str = v_entry["version"]
            v_key = [int(p) for p in v_str.split(".") if p.isdigit()]
            snap_id = f"snap-{ext_id}-{v_str}"

            api_list = [p["name"] if isinstance(p, dict) else str(p) for p in perms.get("api", [])]
            host_list = [p["name"] if isinstance(p, dict) else str(p) for p in perms.get("host", [])]
            opt_list = [p["name"] if isinstance(p, dict) else str(p) for p in perms.get("optional", [])]

            if ext_id == "sample-notes-sync" and v_str in ("2.3.0", "2.0.0"):
                host_list = ["https://example.com/*"]
                api_list = ["storage", "alarms"]
            elif ext_id == "sample-ad-shield" and v_str == "3.0.0":
                host_list = ["https://adserver.com/*"]

            _MOCK_STORE["snapshots"][snap_id] = {
                "id": snap_id,
                "extension_id": ext_id,
                "user_id": user_id,
                "version": v_str,
                "version_key": v_key,
                "manifest_version": 3,
                "name": ext["name"],
                "description": desc_text,
                "api_permissions": api_list,
                "host_permissions": host_list,
                "optional_api_permissions": [p for p in opt_list if not str(p).startswith(("*", "http", "file", "<"))],
                "optional_host_permissions": [p for p in opt_list if str(p).startswith(("*", "http", "file", "<"))],
                "content_script_matches": [],
                "features": [],
                "manifest": {},
                "manifest_sha256": f"mock_sha_{ext_id}_{v_str}",
                "captured_at": v_entry.get("captured_at", "2026-10-15T12:00:00Z"),
            }


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
