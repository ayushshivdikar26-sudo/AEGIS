"""
AEGIS Persistent Database Layer (Backend/app/db.py)
Provides thread-safe persistent relational storage via SQLite with WAL mode,
supporting append-only extension snapshots, revisions, backfill, and export/import.
"""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from Backend.app.config import settings
from Backend.app.errors import ConflictError, NotFoundError
from Backend.app.logging_setup import logger

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BASE_DIR / "Backend" / "data" / "aegis.db"


def get_db_path() -> Path:
    """Resolves database file path from settings or defaults to Backend/data/aegis.db."""
    url = settings.DATABASE_URL.strip() if settings.DATABASE_URL else ""
    if url.startswith("sqlite:///"):
        path_str = url.replace("sqlite:///", "")
        return Path(path_str)
    return DEFAULT_DB_PATH


@contextmanager
def get_connection() -> Generator[sqlite3.Connection]:
    """Context manager for SQLite connections with WAL mode and row factory."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initializes persistent database tables with integrity constraints."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS extensions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                browser TEXT NOT NULL,
                store_id TEXT,
                name TEXT NOT NULL,
                icon_path TEXT,
                is_public INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL DEFAULT 'user',
                description TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS extension_snapshots (
                id TEXT PRIMARY KEY,
                extension_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                version TEXT NOT NULL,
                version_key TEXT,
                manifest_version INTEGER NOT NULL DEFAULT 3,
                name TEXT NOT NULL,
                description TEXT,
                api_permissions TEXT NOT NULL DEFAULT '[]',
                host_permissions TEXT NOT NULL DEFAULT '[]',
                optional_api_permissions TEXT NOT NULL DEFAULT '[]',
                optional_host_permissions TEXT NOT NULL DEFAULT '[]',
                content_script_matches TEXT NOT NULL DEFAULT '[]',
                features TEXT NOT NULL DEFAULT '[]',
                manifest TEXT NOT NULL DEFAULT '{}',
                manifest_sha256 TEXT NOT NULL,
                risk_score INTEGER NOT NULL DEFAULT 0,
                captured_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'local',
                revision INTEGER NOT NULL DEFAULT 1,
                is_suspicious INTEGER NOT NULL DEFAULT 0,
                UNIQUE(extension_id, version, revision),
                FOREIGN KEY (extension_id) REFERENCES extensions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_ext 
                ON extension_snapshots(extension_id, captured_at DESC);
            CREATE INDEX IF NOT EXISTS idx_snapshots_version
                ON extension_snapshots(extension_id, version);

            CREATE TABLE IF NOT EXISTS ai_overviews (
                id TEXT PRIMARY KEY,
                extension_id TEXT NOT NULL,
                version TEXT NOT NULL,
                manifest_hash TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                overview_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(extension_id, version, manifest_hash, prompt_version)
            );

            CREATE INDEX IF NOT EXISTS idx_ai_overviews_lookup
                ON ai_overviews(extension_id, version, manifest_hash, prompt_version);

            CREATE TABLE IF NOT EXISTS permission_creep_records (
                id TEXT PRIMARY KEY,
                extension_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                from_version TEXT NOT NULL,
                to_version TEXT NOT NULL,
                outcome TEXT NOT NULL,
                diff_summary TEXT NOT NULL DEFAULT '{}',
                detected_at TEXT NOT NULL,
                UNIQUE(extension_id, from_version, to_version),
                FOREIGN KEY (extension_id) REFERENCES extensions(id) ON DELETE CASCADE
            );
            """
        )
        # Migration: ensure ai_overviews has no foreign key to extensions
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_key_list(ai_overviews);")
        fk_rows = cursor.fetchall()
        if fk_rows:
            logger.info("Migrating ai_overviews table to remove foreign key constraint...")
            conn.execute("DROP TABLE IF EXISTS ai_overviews_old;")
            conn.execute("ALTER TABLE ai_overviews RENAME TO ai_overviews_old;")
            conn.execute(
                """
                CREATE TABLE ai_overviews (
                    id TEXT PRIMARY KEY,
                    extension_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    manifest_hash TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    overview_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(extension_id, version, manifest_hash, prompt_version)
                );
                """
            )
            conn.execute(
                """
                INSERT INTO ai_overviews (id, extension_id, version, manifest_hash, prompt_version, overview_json, created_at)
                SELECT id, extension_id, version, manifest_hash, prompt_version, overview_json, created_at
                FROM ai_overviews_old;
                """
            )
            conn.execute("DROP TABLE ai_overviews_old;")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ai_overviews_lookup
                    ON ai_overviews(extension_id, version, manifest_hash, prompt_version);
                """
            )

    logger.info(f"Initialized persistent database at {get_db_path()}")


def _row_to_snapshot(row: sqlite3.Row) -> dict[str, Any]:
    """Helper to deserialize stored JSON columns back to Python objects."""
    d = dict(row)
    for col in (
        "version_key",
        "api_permissions",
        "host_permissions",
        "optional_api_permissions",
        "optional_host_permissions",
        "content_script_matches",
        "features",
        "manifest",
    ):
        if col in d and isinstance(d[col], str):
            with suppress(Exception):
                d[col] = json.loads(d[col])
    d["is_suspicious"] = bool(d.get("is_suspicious", 0))
    return d


def db_list_extensions(user_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if user_id:
            rows = conn.execute(
                "SELECT * FROM extensions WHERE user_id = ? OR is_public = 1 ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM extensions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def db_get_extension(ext_id: str, user_id: str | None = None) -> dict[str, Any]:
    with get_connection() as conn:
        if user_id:
            row = conn.execute(
                "SELECT * FROM extensions WHERE id = ? AND (user_id = ? OR is_public = 1)",
                (ext_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM extensions WHERE id = ?",
                (ext_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("Extension not found.")
        return dict(row)


def db_find_extension_by_store_or_name(
    browser: str, store_id: str | None, name: str, user_id: str | None = None
) -> dict[str, Any] | None:
    with get_connection() as conn:
        if store_id:
            row = conn.execute(
                "SELECT * FROM extensions WHERE browser = ? AND store_id = ?",
                (browser, store_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM extensions WHERE browser = ? AND LOWER(name) = LOWER(?)",
                (browser, name),
            ).fetchone()
        return dict(row) if row else None


def db_upsert_extension(ext: dict[str, Any]) -> dict[str, Any]:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO extensions (id, user_id, browser, store_id, name, icon_path, is_public, source, description, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                icon_path = COALESCE(excluded.icon_path, extensions.icon_path),
                description = COALESCE(excluded.description, extensions.description),
                updated_at = excluded.updated_at;
            """,
            (
                ext["id"],
                ext.get("user_id", "00000000-0000-0000-0000-000000000001"),
                ext.get("browser", "chrome"),
                ext.get("store_id"),
                ext["name"],
                ext.get("icon_path"),
                1 if ext.get("is_public", True) else 0,
                ext.get("source", "user"),
                ext.get("description"),
                ext.get("updated_at", datetime.now(UTC).isoformat()),
            ),
        )
        return ext


def db_delete_extension(ext_id: str, user_id: str | None = None) -> None:
    with get_connection() as conn:
        if user_id:
            cursor = conn.execute("DELETE FROM extensions WHERE id = ? AND user_id = ?", (ext_id, user_id))
        else:
            cursor = conn.execute("DELETE FROM extensions WHERE id = ?", (ext_id,))
        if cursor.rowcount == 0:
            raise NotFoundError("Extension not found.")


def db_list_snapshots(ext_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM extension_snapshots
            WHERE extension_id = ?
            ORDER BY revision DESC, captured_at DESC
            """,
            (ext_id,),
        ).fetchall()

        snaps = [_row_to_snapshot(r) for r in rows]

        # Sort semantically descending (newest version first)
        def _version_sort_key(s: dict[str, Any]) -> tuple:
            v_key = s.get("version_key")
            if isinstance(v_key, list):
                parsed = tuple(v_key)
            else:
                parsed = tuple(int(p) for p in str(s.get("version", "0")).split(".") if p.isdigit())
            return (parsed, s.get("revision", 1), s.get("captured_at", ""))

        snaps.sort(key=_version_sort_key, reverse=True)
        return snaps


def db_get_snapshot_by_version(ext_id: str, version: str, user_id: str | None = None) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM extension_snapshots
            WHERE extension_id = ? AND version = ?
            ORDER BY revision DESC LIMIT 1
            """,
            (ext_id, version),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Version {version} not found for extension.")
        return _row_to_snapshot(row)


def db_insert_snapshot(
    snapshot: dict[str, Any], allow_suspicious_revision: bool = True
) -> tuple[dict[str, Any], bool]:
    """
    Append-only snapshot inserter:
    - If version doesn't exist: insert revision 1, return (record, True)
    - If version exists with identical manifest hash: return (existing, False)
    - If version exists with different manifest hash:
        insert as revision N+1 with is_suspicious=1, return (record, True)
    """
    ext_id = snapshot["extension_id"]
    version = snapshot["version"]
    sha256 = snapshot["manifest_sha256"]

    with get_connection() as conn:
        existing_rows = conn.execute(
            """
            SELECT * FROM extension_snapshots
            WHERE extension_id = ? AND version = ?
            ORDER BY revision DESC
            """,
            (ext_id, version),
        ).fetchall()

        if existing_rows:
            # Check if any existing revision has identical manifest hash
            for r in existing_rows:
                if r["manifest_sha256"] == sha256:
                    return _row_to_snapshot(r), False

            # Hash differs! This is a suspicious revision change
            max_rev = existing_rows[0]["revision"]
            new_rev = max_rev + 1
            is_suspicious = 1
            logger.warning(
                f"Suspicious revision detected for extension {ext_id} version {version}! "
                f"Hash changed from {existing_rows[0]['manifest_sha256']} to {sha256}."
            )
            if not allow_suspicious_revision:
                raise ConflictError("Version conflict: A different manifest with this version already exists.")
        else:
            new_rev = 1
            is_suspicious = 0

        snap_id = snapshot.get("id") or f"snap-{ext_id}-{version}-rev{new_rev}"
        record = dict(snapshot)
        record["id"] = snap_id
        record["revision"] = new_rev
        record["is_suspicious"] = bool(is_suspicious)

        conn.execute(
            """
            INSERT INTO extension_snapshots (
                id, extension_id, user_id, version, version_key, manifest_version,
                name, description, api_permissions, host_permissions,
                optional_api_permissions, optional_host_permissions,
                content_script_matches, features, manifest, manifest_sha256,
                risk_score, captured_at, source, revision, is_suspicious
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snap_id,
                ext_id,
                record.get("user_id", "00000000-0000-0000-0000-000000000001"),
                version,
                json.dumps(record.get("version_key", [])),
                int(record.get("manifest_version", 3)),
                record.get("name", "Unknown"),
                record.get("description", ""),
                json.dumps(record.get("api_permissions", [])),
                json.dumps(record.get("host_permissions", [])),
                json.dumps(record.get("optional_api_permissions", [])),
                json.dumps(record.get("optional_host_permissions", [])),
                json.dumps(record.get("content_script_matches", [])),
                json.dumps(record.get("features", [])),
                json.dumps(record.get("manifest", {})),
                sha256,
                int(record.get("risk_score", 0)),
                record.get("captured_at", datetime.now(UTC).isoformat()),
                record.get("source", "local"),
                new_rev,
                is_suspicious,
            ),
        )
        return record, True


def db_export_all_history(user_id: str | None = None) -> dict[str, Any]:
    """Exports all stored extensions and their complete snapshot version history as JSON."""
    exts = db_list_extensions(user_id=user_id, limit=1000)
    ext_entries: list[dict[str, Any]] = []
    for ext in exts:
        snaps = db_list_snapshots(ext["id"], user_id=user_id)
        ext_entry = dict(ext)
        ext_entry["snapshots"] = snaps
        ext_entries.append(ext_entry)

    return {
        "format": "aegis_history_backup",
        "version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "extensions": ext_entries,
    }


def db_import_history_data(data: dict[str, Any], user_id: str | None = None) -> dict[str, int]:
    """Imports extensions and snapshot history append-only from a backup JSON."""
    ext_list = data.get("extensions", [])
    imported_exts = 0
    imported_snaps = 0
    skipped_snaps = 0
    suspicious_count = 0

    for ext in ext_list:
        db_upsert_extension(ext)
        imported_exts += 1
        for snap in ext.get("snapshots", []):
            snap["extension_id"] = ext["id"]
            if user_id:
                snap["user_id"] = user_id
            rec, created = db_insert_snapshot(snap)
            if created:
                imported_snaps += 1
                if rec.get("is_suspicious"):
                    suspicious_count += 1
            else:
                skipped_snaps += 1

    return {
        "imported_extensions": imported_exts,
        "imported_snapshots": imported_snaps,
        "skipped_snapshots": skipped_snaps,
        "suspicious_revisions": suspicious_count,
    }


def db_get_ai_overview(
    extension_id: str, version: str, manifest_hash: str, prompt_version: str
) -> dict[str, Any] | None:
    """Retrieves a cached AI overview by (extension_id, version, manifest_hash, prompt_version)."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT overview_json FROM ai_overviews
            WHERE extension_id = ? AND version = ? AND manifest_hash = ? AND prompt_version = ?
            """,
            (extension_id, version, manifest_hash, prompt_version),
        ).fetchone()
        if row:
            try:
                return json.loads(row["overview_json"])
            except Exception:
                return None
        return None


def db_save_ai_overview(
    extension_id: str,
    version: str,
    manifest_hash: str,
    prompt_version: str,
    overview_dict: dict[str, Any],
) -> None:
    """Saves or updates a cached AI overview."""
    import uuid

    overview_id = f"aio-{uuid.uuid4().hex[:12]}"
    json_str = json.dumps(overview_dict)
    now_str = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ai_overviews (
                id, extension_id, version, manifest_hash, prompt_version, overview_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(extension_id, version, manifest_hash, prompt_version)
            DO UPDATE SET overview_json = excluded.overview_json, created_at = excluded.created_at
            """,
            (
                overview_id,
                extension_id,
                version,
                manifest_hash,
                prompt_version,
                json_str,
                now_str,
            ),
        )


def db_delete_ai_overview(
    extension_id: str, version: str, manifest_hash: str, prompt_version: str
) -> None:
    """Deletes a cached AI overview for forced regeneration."""
    with get_connection() as conn:
        conn.execute(
            """
            DELETE FROM ai_overviews
            WHERE extension_id = ? AND version = ? AND manifest_hash = ? AND prompt_version = ?
            """,
            (extension_id, version, manifest_hash, prompt_version),
        )


def db_clear_all_tables() -> None:
    """Wipes tables for test isolation."""
    with get_connection() as conn:
        conn.execute("DELETE FROM ai_overviews;")
        conn.execute("DELETE FROM permission_creep_records;")
        conn.execute("DELETE FROM extension_snapshots;")
        conn.execute("DELETE FROM extensions;")
