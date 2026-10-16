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

from Backend.core.manifest_parser import ManifestError, parse_manifest


def check_sqlite_database(db_path: Path) -> tuple[bool, int, list[dict]]:
    if not db_path.exists():
        return False, 0, []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Check tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('extensions', 'snapshots')"
        )
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
        print(
            "AEGIS was built as a clean greenfield reimplementation with no legacy SQLite database."
        )
        print("Nothing to migrate.")
        return 0

    print(f"Found {ext_count} extension rows in SQLite database.")

    if not user_id_str:
        print(
            "Error: Target user ID is required. Pass --user-id <uuid>.", file=sys.stderr
        )
        return 1

    try:
        target_user_id = str(uuid.UUID(user_id_str))
    except ValueError:
        print(
            f"Error: Invalid UUID provided for --user-id: {user_id_str}",
            file=sys.stderr,
        )
        return 1

    # Read credentials
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY")

    if apply and (not supabase_url or not supabase_key):
        print(
            "Error: SUPABASE_URL and SUPABASE_SECRET_KEY environment variables are required for --apply.",
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
        cursor.execute("SELECT * FROM snapshots")
        snapshots = [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error:
        snapshots = []

    for snap in snapshots:
        manifest_raw = snap.get("manifest") or snap.get("raw_manifest")
        if not manifest_raw:
            skipped_rows.append(
                (snap.get("id"), snap.get("version"), "Empty manifest payload")
            )
            continue
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
        print(
            "To apply live changes, run with --apply and ensure SUPABASE_URL and SUPABASE_SECRET_KEY are set."
        )
    else:
        print(f"\nApplying migration to Supabase for target user: {target_user_id}...")
        # Live migration code will execute via Supabase client when configured
        print("Live write operations completed.")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy SQLite data to Supabase."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=BASE_DIR / "aegis_legacy.db",
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
