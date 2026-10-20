"""
Unit tests for SQLite ai_overviews database migration (tests/app/test_db_migration.py).
Verifies:
1. Migrating an existing database with the old FOREIGN KEY constraint preserves cached rows
   and removes the constraint.
2. Inserting an AI overview for an extension_id not present in extensions table succeeds.
3. Running init_db() multiple times is idempotent.
"""

import json
import sqlite3
from pathlib import Path
import pytest

from Backend.app.config import settings
from Backend.app.db import (
    db_get_ai_overview,
    db_save_ai_overview,
    init_db,
)

OLD_SCHEMA = """
CREATE TABLE extensions (
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

CREATE TABLE ai_overviews (
    id TEXT PRIMARY KEY,
    extension_id TEXT NOT NULL,
    version TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    overview_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(extension_id, version, manifest_hash, prompt_version),
    FOREIGN KEY (extension_id) REFERENCES extensions(id) ON DELETE CASCADE
);

CREATE INDEX idx_ai_overviews_lookup
    ON ai_overviews(extension_id, version, manifest_hash, prompt_version);
"""


def test_ai_overviews_fk_migration_and_idempotence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Builds a temp SQLite DB with the OLD schema containing a foreign key and one cached row.
    Runs init_db(), verifies foreign key is gone, cached data is preserved,
    inserting an unreferenced extension_id works, and a second init_db() call changes nothing.
    """
    db_file = tmp_path / "test_migration.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

    # 1. Setup OLD schema with Foreign Key constraint and 1 row
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(OLD_SCHEMA)

    # Insert parent extension
    conn.execute(
        """
        INSERT INTO extensions (id, user_id, browser, store_id, name, updated_at)
        VALUES ('ext-parent-001', '00000000-0000-0000-0000-000000000001', 'chrome', 'store-1', 'Test Ext', '2026-10-15T00:00:00Z')
        """
    )
    # Insert child cached overview
    cached_content = {
        "summary": "Old cached overview summary.",
        "permission_fit": "Good fit",
        "creep_detected": False,
    }
    conn.execute(
        """
        INSERT INTO ai_overviews (id, extension_id, version, manifest_hash, prompt_version, overview_json, created_at)
        VALUES ('aio-old-001', 'ext-parent-001', '1.0.0', 'hash-12345', 'v1', ?, '2026-10-15T00:00:00Z')
        """,
        (json.dumps(cached_content),),
    )
    conn.commit()

    # Verify old schema has foreign_key_list entry
    fk_list_before = conn.execute("PRAGMA foreign_key_list(ai_overviews);").fetchall()
    assert len(fk_list_before) > 0, "Old table must have foreign key to extensions"
    conn.close()

    # 2. Run init_db() to trigger migration
    init_db()

    # 3. Assert foreign_key_list is now empty and cached row is preserved
    verify_conn = sqlite3.connect(str(db_file))
    verify_conn.execute("PRAGMA foreign_keys = ON;")
    fk_list_after = verify_conn.execute("PRAGMA foreign_key_list(ai_overviews);").fetchall()
    assert len(fk_list_after) == 0, "Migrated table must have NO foreign key constraint"

    rows = verify_conn.execute("SELECT * FROM ai_overviews WHERE id = 'aio-old-001'").fetchall()
    assert len(rows) == 1, "Cached overview row must survive the migration"
    verify_conn.close()

    # Verify retrieval via helper
    retrieved = db_get_ai_overview("ext-parent-001", "1.0.0", "hash-12345", "v1")
    assert retrieved is not None
    assert retrieved["summary"] == "Old cached overview summary."

    # 4. Assert inserting an overview for an extension_id that is NOT in extensions succeeds
    supabase_uuid_ext_id = "dcdf15d2-85fc-505d-9ce4-0a58a4f50fb6"
    new_cached_payload = {
        "summary": "Overview for remote Supabase extension",
        "permission_fit": "Aligned",
        "creep_detected": True,
        "creep_risks": ["Access to all sites"],
        "recommended_actions": ["Review permissions"],
        "model": "llama-3.1-8b-instant",
    }
    # This must NOT raise sqlite3.IntegrityError
    db_save_ai_overview(
        extension_id=supabase_uuid_ext_id,
        version="2.0.0",
        manifest_hash="hash-remote-uuid",
        prompt_version="v1",
        overview_dict=new_cached_payload,
    )

    remote_cached = db_get_ai_overview(supabase_uuid_ext_id, "2.0.0", "hash-remote-uuid", "v1")
    assert remote_cached is not None
    assert remote_cached["summary"] == "Overview for remote Supabase extension"

    # 5. Assert a second init_db() call is idempotent and changes nothing
    init_db()

    check_conn = sqlite3.connect(str(db_file))
    fk_list_second = check_conn.execute("PRAGMA foreign_key_list(ai_overviews);").fetchall()
    assert len(fk_list_second) == 0
    total_count = check_conn.execute("SELECT count(*) FROM ai_overviews").fetchone()[0]
    assert total_count == 2, "Second init_db() must not delete or duplicate rows"
    check_conn.close()
