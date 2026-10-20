"""
Unit and Integration Tests for Snapshot History Persistence and Append-Only Revisions (Milestone 1c).
Verifies:
1. Saving v1 and v2 persists both versions.
2. Restarting / re-instantiating the repository preserves both versions.
3. Version comparison works between historical v1 and v2.
4. Identical version + identical hash is de-duplicated (skipped).
5. Identical version + different hash creates a new revision and is flagged as suspicious.
6. Export and import JSON backup restores all snapshots append-only.
"""

import tempfile
from pathlib import Path

import pytest

from Backend.app.config import settings
from Backend.app.db import (
    db_clear_all_tables,
    db_export_all_history,
    db_get_snapshot_by_version,
    db_import_history_data,
    db_insert_snapshot,
    db_list_snapshots,
    db_upsert_extension,
    init_db,
)
from Backend.app.repo import Repository
from Backend.app.services.assessment import compare_snapshot_rows


@pytest.fixture(autouse=True)
def temp_persistent_db(monkeypatch):
    """Points DATABASE_URL to a clean temporary SQLite database for test isolation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db_file = Path(tmpdir) / "test_aegis.db"
        monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_db_file}")
        init_db()
        yield tmp_db_file
        db_clear_all_tables()


def test_save_v1_save_v2_and_survive_restart():
    """Verify v1 and v2 are saved, survive repository re-instantiation, and are queryable."""
    user_id = "00000000-0000-0000-0000-000000000001"
    ext_id = "chrome-test-ext-1"

    # Step 1: Create extension
    ext_record = {
        "id": ext_id,
        "user_id": user_id,
        "browser": "chrome",
        "store_id": "test-ext-1",
        "name": "Audit Extension",
        "icon_path": None,
        "description": "A test extension for version persistence.",
    }
    db_upsert_extension(ext_record)

    # Step 2: Save v1 snapshot
    snap_v1 = {
        "id": f"snap-{ext_id}-1.0.0",
        "extension_id": ext_id,
        "user_id": user_id,
        "version": "1.0.0",
        "version_key": [1, 0, 0],
        "name": "Audit Extension",
        "description": "Version 1 description",
        "api_permissions": ["storage"],
        "host_permissions": ["https://example.com/*"],
        "manifest_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
        "risk_score": 20,
    }
    rec_v1, created_v1 = db_insert_snapshot(snap_v1)
    assert created_v1 is True

    # Step 3: Save v2 snapshot with updated permissions
    snap_v2 = {
        "id": f"snap-{ext_id}-2.0.0",
        "extension_id": ext_id,
        "user_id": user_id,
        "version": "2.0.0",
        "version_key": [2, 0, 0],
        "name": "Audit Extension",
        "description": "Version 2 description with added permissions",
        "api_permissions": ["storage", "cookies"],
        "host_permissions": ["https://example.com/*", "<all_urls>"],
        "manifest_sha256": "2222222222222222222222222222222222222222222222222222222222222222",
        "risk_score": 70,
    }
    rec_v2, created_v2 = db_insert_snapshot(snap_v2)
    assert created_v2 is True

    # Step 4: Simulate application / repo restart
    # Create fresh repository instance (not in pytest mock mode)
    repo = Repository(client=None, use_mock=False)

    # Assert both snapshots still exist in persistent database
    snaps = repo.list_snapshots(user_id, ext_id)
    assert len(snaps) == 2
    # Verify semantic order: newest (2.0.0) first
    assert snaps[0]["version"] == "2.0.0"
    assert snaps[1]["version"] == "1.0.0"

    # Step 5: Compare v1 vs v2
    diff = compare_snapshot_rows(snaps[1], snaps[0])
    assert diff["score_from"] == 20
    assert diff["score_to"] == 70
    # Cookies and <all_urls> were added in v2
    added_names = [item["name"] for item in diff["api"]["added"] + diff["host"]["added"]]
    assert "cookies" in added_names
    assert "<all_urls>" in added_names


def test_append_only_deduplication_and_suspicious_hash_revision():
    """Verify identical hash is skipped, while changed hash on same version flags suspicious revision."""
    user_id = "00000000-0000-0000-0000-000000000001"
    ext_id = "chrome-test-ext-hash"

    db_upsert_extension({
        "id": ext_id,
        "user_id": user_id,
        "browser": "chrome",
        "name": "Tamper Test",
    })

    snap = {
        "extension_id": ext_id,
        "user_id": user_id,
        "version": "1.0.0",
        "version_key": [1, 0, 0],
        "name": "Tamper Test",
        "api_permissions": ["storage"],
        "manifest_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "risk_score": 20,
    }

    # 1. Initial insert
    rec1, created1 = db_insert_snapshot(snap)
    assert created1 is True
    assert rec1["revision"] == 1
    assert rec1["is_suspicious"] is False

    # 2. Re-scan with identical hash -> skipped
    rec2, created2 = db_insert_snapshot(snap)
    assert created2 is False
    assert rec2["id"] == rec1["id"]

    # 3. Same version with DIFFERENT hash (suspicious update / tampering)
    tampered_snap = dict(snap)
    tampered_snap["manifest_sha256"] = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    tampered_snap["api_permissions"] = ["storage", "debugger"]
    tampered_snap["risk_score"] = 70

    rec3, created3 = db_insert_snapshot(tampered_snap)
    assert created3 is True
    assert rec3["revision"] == 2
    assert rec3["is_suspicious"] is True

    # Verify all snapshots for this extension
    snaps = db_list_snapshots(ext_id)
    assert len(snaps) == 2
    assert snaps[0]["revision"] == 2
    assert snaps[0]["is_suspicious"] is True
    assert snaps[1]["revision"] == 1
    assert snaps[1]["is_suspicious"] is False


def test_history_export_and_import():
    """Verify exporting history to JSON backup and restoring it."""
    user_id = "00000000-0000-0000-0000-000000000001"
    ext_id = "chrome-export-test"

    db_upsert_extension({
        "id": ext_id,
        "user_id": user_id,
        "browser": "chrome",
        "name": "Export Test",
    })
    db_insert_snapshot({
        "extension_id": ext_id,
        "user_id": user_id,
        "version": "1.0.0",
        "name": "Export Test",
        "manifest_sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        "risk_score": 20,
    })

    # Export backup
    exported = db_export_all_history()
    assert exported["format"] == "aegis_history_backup"
    assert len(exported["extensions"]) >= 1

    # Clear DB
    db_clear_all_tables()
    assert len(db_list_snapshots(ext_id)) == 0

    # Import backup
    result = db_import_history_data(exported)
    assert result["imported_snapshots"] >= 1

    # Verify restored
    restored_snap = db_get_snapshot_by_version(ext_id, "1.0.0")
    assert restored_snap["version"] == "1.0.0"
    assert restored_snap["manifest_sha256"] == "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
