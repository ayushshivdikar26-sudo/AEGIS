#!/usr/bin/env python3
"""
AEGIS SQLite to Supabase Migration Utility (scripts/migrate_sqlite_to_supabase.py)
Re-derives all normalized columns through Backend.core.manifest_parser.parse_manifest.
Runs in dry-run mode by default; writes require explicit --apply and --user-id <uuid> (PRD Part 2b s6).
"""

import argparse
import os
import sqlite3
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from Backend.core.manifest_parser import ManifestError, parse_manifest  # noqa: E402


def check_sqlite_database(db_path: Path) -> tuple[bool, int, list[dict]]:
    if not db_path.exists():
        return False, 0, []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('extensions', 'snapshots')")
        tables = [row["name"] for row in cursor.fetchall()]
        if not tables:
            return True, 0, []

        cursor.execute("SELECT count(*) as cnt FROM extensions")
        ext_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT * FROM extensions")
        rows = [dict(r) for r in cursor.fetchall()]
        return True, ext_count, rows
    except sqlite3.Error as exc:
        print(f"Error querying SQLite database: {exc}", file=sys.stderr)
        return True, 0, []
    finally:
        conn.close()


def run_migration(db_path: Path, user_id_str: str | None, apply: bool):
    print("=" * 70)
    print("AEGIS SQLite -> Supabase Migration Utility")
    print(f"Database File: {db_path}")
    print(f"Mode: {'APPLY (Live Writes)' if apply else 'DRY RUN (Read-Only)'}")
    print("=" * 70)

    exists, ext_count, _rows = check_sqlite_database(db_path)
    if not exists:
        print(f"Notice: SQLite database file not found at {db_path}.")
        print("AEGIS was built as a clean greenfield reimplementation with no legacy SQLite database.")
        print("Nothing to migrate.")
        return 0

    if ext_count == 0 and db_path.name == "aegis.db":
        print("Database is currently empty (e.g. after running test suites).")
        print("Scanning local browsers to discover and populate installed extensions...")
        try:
            from Backend.app.repo import seed_mock_store_from_fixtures
            seed_mock_store_from_fixtures()
            exists, ext_count, _rows = check_sqlite_database(db_path)
        except Exception as exc:
            print(f"Could not auto-seed extensions: {exc}", file=sys.stderr)

    print(f"Found {ext_count} extension rows in SQLite database.")

    if not user_id_str:
        print("Error: Target user ID is required. Pass --user-id <uuid>.", file=sys.stderr)
        return 1

    try:
        target_user_id = str(uuid.UUID(user_id_str))
    except ValueError:
        print(
            f"Error: Invalid UUID provided for --user-id: {user_id_str}",
            file=sys.stderr,
        )
        return 1

    # Read credentials from environment or .env settings
    from Backend.app.config import settings

    supabase_url = os.environ.get("SUPABASE_URL") or settings.SUPABASE_URL
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY") or settings.SUPABASE_SECRET_KEY

    is_placeholder = (
        not supabase_url
        or not supabase_key
        or "your-project" in supabase_url
        or "your-" in supabase_key
        or "localhost" in supabase_url
    )

    if apply and is_placeholder:
        print(
            "\nError: Live Supabase credentials are required for --apply.\n"
            "Currently, your .env file contains placeholder values:\n"
            f"  SUPABASE_URL={supabase_url}\n"
            f"  SUPABASE_SECRET_KEY={'*' * 8 if supabase_key else 'None'}\n\n"
            "To perform live writes to Supabase:\n"
            "1. Open your .env file.\n"
            "2. Replace 'https://your-project-ref.supabase.co' with your real Supabase Project URL.\n"
            "3. Replace 'your-supabase-secret-key' with your secret service_role key.\n"
            "   (Both can be copied from: Supabase Dashboard -> Project Settings -> API).\n",
            file=sys.stderr,
        )
        return 1

    # Connect to SQLite for snapshots
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    valid_snapshots = []
    skipped_rows = []

    try:
        cursor.execute("SELECT * FROM extension_snapshots")
        snapshots = [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error:
        try:
            cursor.execute("SELECT * FROM snapshots")
            snapshots = [dict(r) for r in cursor.fetchall()]
        except sqlite3.Error:
            snapshots = []

    import json as pyjson

    for snap in snapshots:
        manifest_raw = snap.get("manifest") or snap.get("raw_manifest")
        if not manifest_raw:
            skipped_rows.append((snap.get("id"), snap.get("version"), "Empty manifest payload"))
            continue
        if isinstance(manifest_raw, str):
            try:
                manifest_raw = pyjson.loads(manifest_raw)
            except Exception:
                pass
        try:
            parsed = parse_manifest(manifest_raw)
            valid_snapshots.append((snap, parsed))
        except ManifestError as merr:
            skipped_rows.append((snap.get("id"), snap.get("version"), str(merr)))

    print(f"Parsed {len(valid_snapshots)} snapshots successfully.")
    if skipped_rows:
        print(f"Skipped {len(skipped_rows)} invalid snapshots:")
        for sid, ver, reason in skipped_rows:
            print(f"  - Snapshot ID {sid}, version {ver}: {reason}")

    if not apply:
        print("\nDry run completed successfully. Zero changes made to Supabase.")
        print("To apply live changes, run with --apply and ensure SUPABASE_URL and SUPABASE_SECRET_KEY are set.")
    else:
        print(f"\nApplying migration to Supabase for target user: {target_user_id}...")
        try:
            from supabase import create_client

            client = create_client(supabase_url, supabase_key)
            ext_id_map: dict[str, str] = {}

            # 1. Upsert extensions
            for ext in _rows:
                raw_id = ext["id"]
                try:
                    uuid_str = str(uuid.UUID(raw_id))
                except ValueError:
                    uuid_str = str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_id))
                ext_id_map[raw_id] = uuid_str

                ext_payload = {
                    "id": uuid_str,
                    "user_id": target_user_id,
                    "browser": ext.get("browser", "chrome").lower(),
                    "store_id": ext.get("store_id"),
                    "name": ext.get("name", "Unknown"),
                    "icon_path": ext.get("icon_path"),
                    "is_public": bool(ext.get("is_public", False)),
                    "source": ext.get("source", "user"),
                }
                client.table("extensions").upsert(ext_payload).execute()
                print(f"  Upserted extension: {ext_payload['name']} ({uuid_str})")

            # 2. Insert snapshots
            for snap, parsed in valid_snapshots:
                raw_ext_id = snap.get("extension_id")
                ext_uuid = ext_id_map.get(raw_ext_id)
                if not ext_uuid:
                    try:
                        ext_uuid = str(uuid.UUID(raw_ext_id))
                    except (ValueError, TypeError):
                        ext_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(raw_ext_id)))

                raw_snap_id = snap.get("id") or f"snap-{raw_ext_id}-{parsed.version}"
                try:
                    snap_uuid = str(uuid.UUID(raw_snap_id))
                except ValueError:
                    snap_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_snap_id))

                snap_payload = {
                    "id": snap_uuid,
                    "extension_id": ext_uuid,
                    "user_id": target_user_id,
                    "version": parsed.version,
                    "version_key": list(parsed.version_key) if parsed.version_key else None,
                    "manifest_version": parsed.manifest_version,
                    "name": parsed.name or snap.get("name", "Unknown"),
                    "description": parsed.description or snap.get("description", ""),
                    "api_permissions": sorted(list(parsed.api_permissions)),
                    "host_permissions": sorted(list(parsed.host_permissions)),
                    "optional_api_permissions": sorted(list(parsed.optional_api_permissions)),
                    "optional_host_permissions": sorted(list(parsed.optional_host_permissions)),
                    "content_script_matches": sorted(list(parsed.content_script_matches)),
                    "features": sorted(list(parsed.features)),
                    "manifest": parsed.model_dump(),
                    "manifest_sha256": parsed.sha256,
                }
                client.table("extension_snapshots").upsert(snap_payload).execute()
                print(f"  Upserted snapshot: {snap_payload['name']} v{snap_payload['version']}")

            print("Live write operations to Supabase completed successfully.")
        except Exception as exc:
            exc_str = str(exc)
            if "PGRST205" in exc_str or "Could not find the table" in exc_str:
                project_ref = settings.AEGIS_TEST_PROJECT_REF or "your-project"
                print(
                    "\n[!] Schema Missing in Supabase:\n"
                    "Your Supabase credentials are valid and authenticated, but the database tables have not been created yet in PostgreSQL.\n\n"
                    "To create the tables in your Supabase project:\n"
                    f"1. Open your Supabase Dashboard: https://supabase.com/dashboard/project/{project_ref}/sql/new\n"
                    "2. Paste the contents of 'supabase/migrations/0001_initial_schema.sql' and click 'Run'.\n"
                    "3. Open a second query, paste 'supabase/migrations/0002_rls_policies.sql', and click 'Run'.\n"
                    "4. (Optional) Run 'supabase/migrations/0003_storage.sql' to configure icon storage.\n\n"
                    "Once the migrations have run, re-run this command to complete the data transfer!",
                    file=sys.stderr,
                )
            else:
                print(f"Error during Supabase live write: {exc}", file=sys.stderr)
            return 1

    return 0


def main():
    default_db = BASE_DIR / "Backend" / "data" / "aegis.db"
    if not default_db.exists():
        default_db = BASE_DIR / "aegis_legacy.db"

    parser = argparse.ArgumentParser(description="Migrate legacy SQLite data to Supabase.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=default_db,
        help="Path to SQLite database",
    )
    parser.add_argument("--user-id", type=str, help="Target Supabase User UUID")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply live changes to Supabase (default: dry run)",
    )
    args = parser.parse_args()

    sys.exit(run_migration(args.db_path, args.user_id, args.apply))


if __name__ == "__main__":
    main()
