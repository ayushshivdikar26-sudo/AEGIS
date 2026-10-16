"""
AEGIS Database Schema Integrity & Policy Static Verification Suite (tests/db/test_schema_integrity.py)
Validates migration SQL files, constraints, triggers, RLS policies, storage rules, and seed definitions.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
MIGRATION_DIR = BASE_DIR / "supabase" / "migrations"
MIG_0001 = MIGRATION_DIR / "0001_initial_schema.sql"
MIG_0002 = MIGRATION_DIR / "0002_rls_policies.sql"
MIG_0003 = MIGRATION_DIR / "0003_storage.sql"
SEED_SQL = BASE_DIR / "Backend" / "db" / "seed" / "mock_seed.sql"


def test_migration_files_exist():
    """Verify all required migration files exist in supabase/migrations."""
    assert MIG_0001.exists(), f"Missing {MIG_0001}"
    assert MIG_0002.exists(), f"Missing {MIG_0002}"
    assert MIG_0003.exists(), f"Missing {MIG_0003}"
    assert SEED_SQL.exists(), f"Missing {SEED_SQL}"


def test_schema_tables_and_columns():
    """Verify all 5 required tables and essential audit/security columns in 0001."""
    content = MIG_0001.read_text(encoding="utf-8")

    required_tables = [
        "public.extensions",
        "public.extension_snapshots",
        "public.snapshot_permissions",
        "public.permission_creep_records",
        "public.ai_analyses",
    ]
    for table in required_tables:
        assert (
            f"create table if not exists {table}" in content
            or f"create table {table}" in content
        ), f"Table {table} not found in 0001_initial_schema.sql"

    # Check key columns
    assert (
        "browser in ('chrome', 'edge', 'firefox', 'brave', 'opera', 'other')" in content
    )
    assert "is_public" in content
    assert "source in ('user', 'catalog_seed', 'fixture')" in content
    assert "manifest_version in (2, 3)" in content
    assert "manifest_sha256 ~ '^[0-9a-f]{64}$'" in content
    assert "version_key" in content
    assert "on delete cascade" in content


def test_triggers_and_integrity_constraints():
    """Verify size limits, array validation, immutability, and quota triggers in 0001."""
    content = MIG_0001.read_text(encoding="utf-8")

    # Manifest size cap (262,144 bytes)
    assert "octet_length(new.manifest::text) > 262144" in content
    assert "trg_validate_manifest_size" in content

    # Array validation (2048 chars, control characters)
    assert "char_length(item) > 2048" in content
    assert r"[\x00-\x1f\x7f]" in content
    assert "trg_validate_snapshot_arrays" in content

    # Immutability triggers
    assert "trg_snapshot_immutability" in content
    assert "trg_snapshot_perms_immutability" in content
    assert "trg_creep_immutability" in content
    assert "append-only and immutable" in content

    # Quota triggers (500 extensions, 100 snapshots)
    assert "max_ext constant integer := 500" in content
    assert "max_snap constant integer := 100" in content
    assert "trg_extensions_quota" in content
    assert "trg_snapshots_quota" in content

    # Permission synchronization trigger
    assert "trg_sync_snapshot_permissions" in content


def test_rls_policies_and_privileges():
    """Verify RLS enforcement, force directive, cached auth.uid(), and role grants in 0002."""
    content = MIG_0002.read_text(encoding="utf-8")

    tables = [
        "public.extensions",
        "public.extension_snapshots",
        "public.snapshot_permissions",
        "public.permission_creep_records",
        "public.ai_analyses",
    ]

    for table in tables:
        assert f"alter table {table} enable row level security;" in content, (
            f"RLS not enabled on {table}"
        )
        assert f"alter table {table} force row level security;" in content, (
            f"RLS not forced on {table}"
        )

    # Verify revoke from anon
    assert "revoke all on all tables in schema public from anon;" in content

    # Verify public catalogue read for anon and authenticated
    assert "is_public = true" in content

    # Verify cached auth.uid()
    assert "(select auth.uid())" in content

    # Verify snapshots and creep records have NO update policy and revoke update
    assert (
        "revoke update, delete on public.extension_snapshots from authenticated;"
        in content
    )
    assert (
        "revoke update, delete on public.snapshot_permissions from authenticated;"
        in content
    )
    assert (
        "revoke update, delete on public.permission_creep_records from authenticated;"
        in content
    )


def test_storage_bucket_and_policies():
    """Verify extension-icons bucket, MIME limits, 256 KB cap, and folder RLS in 0003."""
    content = MIG_0003.read_text(encoding="utf-8")

    assert "'extension-icons'" in content
    assert "262144" in content  # 256 KB
    assert "'image/png', 'image/jpeg', 'image/webp'" in content
    assert "image/svg" not in content  # No SVG allowed

    # Folder isolation policy
    assert "(storage.foldername(name))[1] = (select auth.uid())::text" in content


def test_mock_seed_data_integrity():
    """Verify that mock_seed.sql contains all 8 mock extensions separated from user data."""
    content = SEED_SQL.read_text(encoding="utf-8")

    assert "catalog_seed" in content
    assert "is_public" in content

    expected_slugs = [
        "sample-notes-sync",
        "sample-tab-manager",
        "sample-ad-shield",
        "sample-minimal-util",
        "sample-no-desc",
        "sample-xss-name",
        "sample-long-name",
        "sample-rtl-name",
    ]
    for slug in expected_slugs:
        assert slug in content, f"Expected slug {slug} not found in mock_seed.sql"
