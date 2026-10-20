"""
AEGIS Browser Extension Scanner (Backend/app/services/browser_scanner.py)
Discovers real extensions installed in local Chromium browsers (Chrome, Edge, Brave, etc.),
extracts manifests, resolves localized names/descriptions, extracts icons, and computes version history.
"""

import contextlib
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from Backend.app.logging_setup import logger
from Backend.core.manifest_parser import parse_manifest


def _clean_text(val: str | None) -> str:
    if not val:
        return ""
    # Replace non-printable replacement characters and normalize whitespace
    cleaned = val.replace("\ufffd", " - ")
    cleaned = re.sub(r"\s*-\s*", " - ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _resolve_locale_string(vpath: Path, raw_string: str) -> str:
    """Resolves __MSG_foo__ placeholders from _locales/<lang>/messages.json."""
    if not raw_string or not raw_string.startswith("__MSG_"):
        return _clean_text(raw_string)

    key = raw_string[6:-2] if raw_string.endswith("__") else raw_string[6:]
    locales_dir = vpath / "_locales"
    if not locales_dir.is_dir():
        return _clean_text(raw_string)

    # Preferred locales: en, en_US, en_GB, then any available
    candidate_locales = ["en", "en_US", "en_GB"]
    with contextlib.suppress(OSError):
        candidate_locales += [d.name for d in locales_dir.iterdir() if d.is_dir() and d.name not in candidate_locales]

    for loc in candidate_locales:
        msg_file = locales_dir / loc / "messages.json"
        if msg_file.is_file():
            try:
                with open(msg_file, encoding="utf-8") as f:
                    messages = json.load(f)
                for k, v in messages.items():
                    if k.lower() == key.lower():
                        msg = v.get("message")
                        if msg:
                            return _clean_text(msg)
            except Exception:
                continue

    return _clean_text(raw_string)


def _extract_icon(vpath: Path, manifest: dict[str, Any], ext_id: str, dest_dir: Path) -> str | None:
    """Finds best icon and copies it to dest_dir, returning relative URL for frontend."""
    icons = manifest.get("icons", {})
    icon_source: Path | None = None

    if isinstance(icons, dict):
        for size in ["128", "96", "64", "48", "32", "16"]:
            if size in icons:
                cand = vpath / icons[size]
                if cand.is_file():
                    icon_source = cand
                    break

    # Fallback to searching files inside version folder if not found in manifest
    if not icon_source:
        try:
            for root, _, files in os.walk(vpath):
                for f in files:
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".ico")) and "icon" in f.lower():
                        cand = Path(root) / f
                        if cand.is_file():
                            icon_source = cand
                            break
                if icon_source:
                    break
        except OSError:
            pass

    if not icon_source:
        return None

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = icon_source.suffix.lower() or ".png"
        dest_filename = f"{ext_id}{ext}"
        dest_path = dest_dir / dest_filename
        shutil.copy2(icon_source, dest_path)
        return f"/assets/installed_icons/{dest_filename}"
    except Exception as exc:
        logger.warning(f"Could not copy icon for {ext_id}: {exc}")
        return None


def get_browser_user_data_paths() -> dict[str, Path]:
    """Returns detected Chromium browser user data paths on the host system."""
    paths: dict[str, Path] = {}
    local = os.environ.get("LOCALAPPDATA")
    appdata = os.environ.get("APPDATA")

    if local:
        chrome = Path(local) / "Google" / "Chrome" / "User Data"
        if chrome.is_dir():
            paths["chrome"] = chrome

        edge = Path(local) / "Microsoft" / "Edge" / "User Data"
        if edge.is_dir():
            paths["edge"] = edge

        brave = Path(local) / "BraveSoftware" / "Brave-Browser" / "User Data"
        if brave.is_dir():
            paths["brave"] = brave

        vivaldi = Path(local) / "Vivaldi" / "User Data"
        if vivaldi.is_dir():
            paths["vivaldi"] = vivaldi

    if appdata:
        opera = Path(appdata) / "Opera Software" / "Opera Stable"
        if opera.is_dir():
            paths["opera"] = opera

    return paths


def scan_installed_extensions(
    dest_icons_dir: Path | None = None,
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """
    Scans all detected browsers for installed extensions.
    Returns a list of tuples: (extension_record, [snapshot_records]).
    """
    if dest_icons_dir is None:
        base_dir = Path(__file__).resolve().parents[3]
        dest_icons_dir = base_dir / "Frontend" / "assets" / "installed_icons"

    results: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    browser_paths = get_browser_user_data_paths()

    # Track seen (browser, store_id) to avoid duplicates across multiple profiles of same browser
    seen_browser_store: set[tuple[str, str]] = set()

    for browser_name, user_data_path in browser_paths.items():
        try:
            profile_candidates = [p for p in user_data_path.iterdir() if p.is_dir()]
        except OSError:
            continue

        for profile_dir in profile_candidates:
            ext_base = profile_dir / "Extensions"
            if not ext_base.is_dir():
                continue

            try:
                extension_dirs = [e for e in ext_base.iterdir() if e.is_dir() and e.name != "Temp"]
            except OSError:
                continue

            for ext_folder in extension_dirs:
                store_id = ext_folder.name
                if len(store_id) < 16:  # Invalid extension ID
                    continue

                if (browser_name, store_id) in seen_browser_store:
                    continue

                try:
                    version_dirs = [v for v in ext_folder.iterdir() if v.is_dir()]
                except OSError:
                    continue

                valid_versions: list[tuple[Path, dict[str, Any], Any]] = []
                for vdir in version_dirs:
                    manifest_file = vdir / "manifest.json"
                    if not manifest_file.is_file():
                        continue
                    try:
                        with open(manifest_file, encoding="utf-8") as f:
                            m_raw = json.load(f)
                        parsed = parse_manifest(m_raw)
                        valid_versions.append((vdir, m_raw, parsed))
                    except Exception as exc:
                        logger.debug(f"Failed parsing {manifest_file}: {exc}")
                        continue

                if not valid_versions:
                    continue

                seen_browser_store.add((browser_name, store_id))

                # Sort versions so newest is first
                valid_versions.sort(key=lambda item: (item[2].version_key or (), item[2].version), reverse=True)

                latest_vdir, latest_raw, latest_parsed = valid_versions[0]
                resolved_name = _resolve_locale_string(latest_vdir, latest_parsed.name or store_id)
                resolved_desc = _resolve_locale_string(latest_vdir, latest_parsed.description or "")
                icon_path = _extract_icon(latest_vdir, latest_raw, store_id, dest_icons_dir)

                ext_id = f"{browser_name}-{store_id}"
                now_iso = datetime.now(UTC).isoformat()

                ext_record = {
                    "id": ext_id,
                    "user_id": "00000000-0000-0000-0000-000000000001",
                    "browser": browser_name,
                    "store_id": store_id,
                    "name": resolved_name,
                    "is_public": True,
                    "icon_path": icon_path,
                    "description": resolved_desc,
                    "updated_at": now_iso,
                }

                snapshot_records: list[dict[str, Any]] = []
                for vdir, raw_m, parsed in valid_versions:
                    snap_id = f"snap-{ext_id}-{parsed.version}"
                    snap_desc = _resolve_locale_string(vdir, parsed.description or "")
                    snap_record = {
                        "id": snap_id,
                        "extension_id": ext_id,
                        "user_id": "00000000-0000-0000-0000-000000000001",
                        "version": parsed.version,
                        "version_key": parsed.version_key,
                        "manifest_version": parsed.manifest_version,
                        "name": resolved_name,
                        "description": snap_desc,
                        "api_permissions": parsed.api_permissions,
                        "host_permissions": parsed.host_permissions,
                        "optional_api_permissions": parsed.optional_api_permissions,
                        "optional_host_permissions": parsed.optional_host_permissions,
                        "content_script_matches": parsed.content_script_matches,
                        "features": parsed.features,
                        "manifest": raw_m,
                        "manifest_sha256": parsed.sha256,
                        "captured_at": now_iso,
                    }
                    snapshot_records.append(snap_record)

                results.append((ext_record, snapshot_records))

    return results


def populate_installed_extensions_into_store(
    target_store: dict[str, dict[str, Any]],
    user_id: str = "00000000-0000-0000-0000-000000000001",
) -> int:
    """
    Populates target store with real extensions discovered on the system.
    Returns the count of extensions loaded.
    """
    scanned = scan_installed_extensions()
    if not scanned:
        return 0

    # Append-only: do NOT clear snapshots, preserve historical versions
    from Backend.app.db import db_insert_snapshot, db_upsert_extension

    # Optional Supabase synchronization when remote project credentials are configured
    supabase_client = None
    try:
        from Backend.app.config import settings

        if (
            settings.SUPABASE_URL
            and "localhost" not in settings.SUPABASE_URL
            and "your-project" not in settings.SUPABASE_URL
            and settings.SUPABASE_SECRET_KEY
            and not settings.SUPABASE_SECRET_KEY.startswith("mock-")
            and "your-" not in settings.SUPABASE_SECRET_KEY
        ):
            from Backend.app.admin import get_admin_client

            supabase_client = get_admin_client()
    except Exception:
        supabase_client = None

    import uuid

    count = 0
    for ext_rec, snaps in scanned:
        ext_rec["user_id"] = user_id
        ext_id = ext_rec["id"]
        target_store["extensions"][ext_id] = ext_rec
        with contextlib.suppress(Exception):
            db_upsert_extension(ext_rec)

        # Sync extension to Supabase if client is active
        if supabase_client is not None:
            with contextlib.suppress(Exception):
                ext_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, ext_id))
                supabase_client.table("extensions").upsert({
                    "id": ext_uuid,
                    "user_id": user_id,
                    "browser": ext_rec.get("browser", "chrome").lower(),
                    "store_id": ext_rec.get("store_id"),
                    "name": ext_rec.get("name", "Unknown"),
                    "icon_path": ext_rec.get("icon_path"),
                    "is_public": bool(ext_rec.get("is_public", True)),
                    "source": ext_rec.get("source", "user"),
                }).execute()

        # Add snapshots append-only
        for s in snaps:
            s["user_id"] = user_id
            target_store["snapshots"][s["id"]] = s
            with contextlib.suppress(Exception):
                db_insert_snapshot(s)

            if supabase_client is not None:
                with contextlib.suppress(Exception):
                    ext_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, ext_id))
                    snap_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, s["id"]))
                    supabase_client.table("extension_snapshots").upsert({
                        "id": snap_uuid,
                        "extension_id": ext_uuid,
                        "user_id": user_id,
                        "version": s["version"],
                        "version_key": list(s.get("version_key") or []),
                        "manifest_version": int(s.get("manifest_version", 3)),
                        "name": s.get("name", "Unknown"),
                        "description": s.get("description", ""),
                        "api_permissions": sorted(list(s.get("api_permissions", []))),
                        "host_permissions": sorted(list(s.get("host_permissions", []))),
                        "optional_api_permissions": sorted(list(s.get("optional_api_permissions", []))),
                        "optional_host_permissions": sorted(list(s.get("optional_host_permissions", []))),
                        "content_script_matches": sorted(list(s.get("content_script_matches", []))),
                        "features": sorted(list(s.get("features", []))),
                        "manifest": s.get("manifest", {}),
                        "manifest_sha256": s.get("manifest_sha256", ""),
                    }).execute()

        # If extension has multiple versions, generate real creep records between pairs
        if len(snaps) >= 2:
            # snaps is sorted newest first: snaps[0] is newest, snaps[1] is previous
            from Backend.app.services.assessment import compare_snapshot_rows

            for i in range(len(snaps) - 1):
                s_new = snaps[i]
                s_old = snaps[i + 1]
                diff = compare_snapshot_rows(s_old, s_new)
                creep_id = f"creep-{ext_id}-{s_old['version']}-{s_new['version']}"
                target_store["creep_records"][creep_id] = {
                    "id": creep_id,
                    "extension_id": ext_id,
                    "old_version": s_old["version"],
                    "new_version": s_new["version"],
                    "creep_type": diff.get("creep_type", "clean"),
                    "added_api_permissions": diff.get("added_api_permissions", []),
                    "removed_api_permissions": diff.get("removed_api_permissions", []),
                    "added_host_permissions": diff.get("added_host_permissions", []),
                    "removed_host_permissions": diff.get("removed_host_permissions", []),
                    "broadened_host_patterns": diff.get("broadened_host_patterns", []),
                    "newly_covered_origins": diff.get("newly_covered_origins", []),
                    "score_delta": diff.get("score_delta", 0),
                    "created_at": s_new["captured_at"],
                }

        count += 1

    logger.info(f"Loaded {count} actual installed extensions into repository store.")
    return count
