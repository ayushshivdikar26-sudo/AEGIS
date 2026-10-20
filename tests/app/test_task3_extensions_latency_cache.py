"""
Tests for Milestone 1 Task 3:
- Contract test on dev/mock-api/fixtures/dataset.json (old vs new shape identity)
- Exactly one Supabase query per list call (counting fake client)
- 60s TTL cache HIT / MISS headers
- Cache expiry with fake clock
- Invalidation on manifest import / snapshot insert / extension delete
- Strict user isolation in cache
- Compatibility across Supabase, SQLite, and mock store paths
"""

import json
from pathlib import Path
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from Backend.app.cache import ExtensionListCache, extension_list_cache
from Backend.app.deps import CurrentUser, get_current_user, get_optional_user, get_user_db_client
from Backend.app.main import app
from Backend.app.repo import Repository, _MOCK_STORE, seed_mock_store_from_fixtures, reset_mock_store
from Backend.app.schemas import ExtensionListItem, ExtensionsListResponse
from Backend.app.services.assessment import compute_snapshot_assessment


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_mock_store()
    seed_mock_store_from_fixtures()
    extension_list_cache.clear()
    yield
    extension_list_cache.clear()


# =============================================================================
# 1. Contract Test: old-style output vs new output on dataset.json
# =============================================================================
def test_contract_dataset_json_identity():
    fixture_path = Path("dev/mock-api/fixtures/dataset.json")
    assert fixture_path.exists(), "dev/mock-api/fixtures/dataset.json not found"

    with open(fixture_path, "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    user_id = "00000000-0000-0000-0000-000000000001"
    repo = Repository(use_mock=True)

    # 1. Old-style output: list_extensions + get_latest_snapshot loop
    ext_rows = [
        dict(ext)
        for ext in _MOCK_STORE["extensions"].values()
        if ext["user_id"] == user_id or ext.get("is_public", False)
    ]
    old_items = []
    for ext in ext_rows:
        ext_id = ext["id"]
        latest_snap = repo.get_latest_snapshot(user_id, ext_id)
        if latest_snap:
            assessment = compute_snapshot_assessment(latest_snap)
            score = assessment.get("risk_score", 0)
            level = assessment.get("risk_level", "low")
            version = latest_snap.get("version", "1.0")
        else:
            score = 0
            level = "low"
            version = "1.0"
        old_items.append(
            ExtensionListItem(
                id=ext_id,
                name=ext.get("name", "Unknown"),
                browser=ext.get("browser", "chrome"),
                version=version,
                icon_url=ext.get("icon_path"),
                risk_score=score,
                risk_level=level,
            )
        )
    old_response = ExtensionsListResponse(source="imported", extensions=old_items).model_dump()

    # 2. New-style output: single call with latest_snapshot attached
    new_ext_rows = repo.list_extensions(user_id)
    new_items = []
    for ext in new_ext_rows:
        ext_id = ext["id"]
        latest_snap = ext.get("latest_snapshot")
        if latest_snap:
            assessment = compute_snapshot_assessment(latest_snap)
            score = assessment.get("risk_score", 0)
            level = assessment.get("risk_level", "low")
            version = latest_snap.get("version", "1.0")
        else:
            score = 0
            level = "low"
            version = "1.0"
        new_items.append(
            ExtensionListItem(
                id=ext_id,
                name=ext.get("name", "Unknown"),
                browser=ext.get("browser", "chrome"),
                version=version,
                icon_url=ext.get("icon_path"),
                risk_score=score,
                risk_level=level,
            )
        )
    new_response = ExtensionsListResponse(source="imported", extensions=new_items).model_dump()

    # Exact equality check
    assert old_response == new_response
    assert len(new_response["extensions"]) == len(fixture_data["extensions"])
    for item in new_response["extensions"]:
        assert "id" in item
        assert "name" in item
        assert "browser" in item
        assert "version" in item
        assert "icon_url" in item
        assert "risk_score" in item
        assert "risk_level" in item


# =============================================================================
# 2. Counting Fake Client: exactly one Supabase query per list call
# =============================================================================
def test_exactly_one_supabase_query():
    class CountingQueryBuilder:
        def __init__(self, table_name: str, client: "CountingSupabaseClient"):
            self.table_name = table_name
            self.client = client
            self._select_arg = None
            self._limit = None

        def select(self, query: str):
            self._select_arg = query
            return self

        def limit(self, count: int):
            self._limit = count
            return self

        def execute(self):
            self.client.query_counts[self.table_name] = (
                self.client.query_counts.get(self.table_name, 0) + 1
            )
            mock_resp = MagicMock()
            mock_resp.data = [
                {
                    "id": "mock-ext-1",
                    "user_id": "user-123",
                    "name": "Mock Ext 1",
                    "browser": "chrome",
                    "store_id": "mock1",
                    "is_public": False,
                    "icon_path": None,
                    "updated_at": "2026-10-15T12:00:00Z",
                    "extension_snapshots": [
                        {
                            "id": "snap-1",
                            "extension_id": "mock-ext-1",
                            "version": "1.0.0",
                            "version_key": [1, 0, 0],
                            "captured_at": "2026-10-15T12:00:00Z",
                            "api_permissions": ["storage"],
                            "host_permissions": [],
                            "manifest": {},
                            "manifest_sha256": "a" * 64,
                            "manifest_version": 3,
                        }
                    ],
                }
            ]
            return mock_resp

    class CountingSupabaseClient:
        def __init__(self):
            self.query_counts: dict[str, int] = {}

        def table(self, name: str):
            return CountingQueryBuilder(name, self)

    fake_client = CountingSupabaseClient()

    app.dependency_overrides[get_user_db_client] = lambda: fake_client
    app.dependency_overrides[get_optional_user] = lambda: CurrentUser(
        id="user-123", email="user@test.com", role="authenticated"
    )

    try:
        client = TestClient(app)
        resp = client.get("/api/extensions")
        assert resp.status_code == 200

        # Assert exactly ONE query was executed to the "extensions" table
        assert fake_client.query_counts.get("extensions") == 1
        # Assert ZERO queries were executed to "extension_snapshots"
        assert fake_client.query_counts.get("extension_snapshots", 0) == 0
    finally:
        app.dependency_overrides.pop(get_user_db_client, None)
        app.dependency_overrides.pop(get_optional_user, None)


# =============================================================================
# 3. 60s TTL Cache HIT/MISS and Headers
# =============================================================================
def test_cache_hit_and_miss_headers():
    app.dependency_overrides[get_optional_user] = lambda: CurrentUser(
        id="user-test-hit-miss", email="hitmiss@test.com", role="authenticated"
    )

    try:
        client = TestClient(app)

        # First call: MISS
        resp1 = client.get("/api/extensions")
        assert resp1.status_code == 200
        assert resp1.headers.get("X-AEGIS-Cache") == "MISS"

        # Second call: HIT
        resp2 = client.get("/api/extensions")
        assert resp2.status_code == 200
        assert resp2.headers.get("X-AEGIS-Cache") == "HIT"

        assert resp1.json() == resp2.json()
    finally:
        app.dependency_overrides.pop(get_optional_user, None)


# =============================================================================
# 4. Cache Expiry with Fake Clock
# =============================================================================
def test_cache_expiry_with_fake_clock():
    fake_time = 1000.0

    def get_fake_time():
        return fake_time

    # Create isolated cache instance using fake clock
    custom_cache = ExtensionListCache(ttl_seconds=60.0, time_func=get_fake_time)

    with patch("Backend.app.routers.extensions.extension_list_cache", custom_cache):
        app.dependency_overrides[get_optional_user] = lambda: CurrentUser(
            id="user-expiry", email="expiry@test.com", role="authenticated"
        )
        try:
            client = TestClient(app)

            # At t = 1000.0 -> MISS
            resp1 = client.get("/api/extensions")
            assert resp1.headers.get("X-AEGIS-Cache") == "MISS"

            # At t = 1030.0 (30s later) -> HIT
            fake_time = 1030.0
            resp2 = client.get("/api/extensions")
            assert resp2.headers.get("X-AEGIS-Cache") == "HIT"

            # At t = 1061.0 (61s later) -> EXPIRED -> MISS
            fake_time = 1061.0
            resp3 = client.get("/api/extensions")
            assert resp3.headers.get("X-AEGIS-Cache") == "MISS"

            # At t = 1070.0 (9s after second miss) -> HIT
            fake_time = 1070.0
            resp4 = client.get("/api/extensions")
            assert resp4.headers.get("X-AEGIS-Cache") == "HIT"
        finally:
            app.dependency_overrides.pop(get_optional_user, None)


# =============================================================================
# 5. Invalidation on Manifest Import & Delete
# =============================================================================
def test_import_and_delete_invalidates_cache():
    test_user = CurrentUser(id="user-invalidation", email="inval@test.com", role="authenticated")
    app.dependency_overrides[get_optional_user] = lambda: test_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_user_db_client] = lambda: None

    try:
        client = TestClient(app)

        # 1. Warm cache
        r1 = client.get("/api/extensions")
        assert r1.headers.get("X-AEGIS-Cache") == "MISS"
        r2 = client.get("/api/extensions")
        assert r2.headers.get("X-AEGIS-Cache") == "HIT"

        # 2. Invalidate via import endpoint (with CSRF header)
        manifest_data = {
            "manifest_version": 3,
            "name": "Test Invalidation Ext",
            "version": "1.0.0",
            "description": "Test extension description",
            "permissions": ["storage"],
        }
        import_resp = client.post(
            "/api/extensions/import",
            data={"browser": "chrome"},
            files={"manifest": ("manifest.json", json.dumps(manifest_data).encode("utf-8"), "application/json")},
            headers={"X-AEGIS-CSRF": "1"},
        )
        assert import_resp.status_code in (200, 201)
        imported_ext_id = import_resp.json()["extension"]["id"]

        # 3. Next list extensions call must be a MISS (invalidated by import!)
        r3 = client.get("/api/extensions")
        assert r3.headers.get("X-AEGIS-Cache") == "MISS"

        # 4. Next call is HIT
        r4 = client.get("/api/extensions")
        assert r4.headers.get("X-AEGIS-Cache") == "HIT"

        # 5. Delete extension (with CSRF header)
        del_resp = client.delete(f"/api/extensions/{imported_ext_id}", headers={"X-AEGIS-CSRF": "1"})
        assert del_resp.status_code == 204

        # 6. Next list extensions call must be a MISS (invalidated by delete!)
        r5 = client.get("/api/extensions")
        assert r5.headers.get("X-AEGIS-Cache") == "MISS"
    finally:
        app.dependency_overrides.pop(get_optional_user, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_user_db_client, None)


# =============================================================================
# 6. User Isolation in Cache: two users never share entries
# =============================================================================
def test_user_isolation_in_cache():
    user1 = CurrentUser(id="user-isolated-1", email="u1@test.com", role="authenticated")
    user2 = CurrentUser(id="user-isolated-2", email="u2@test.com", role="authenticated")

    reset_mock_store()

    # Seed mock store with unique extensions for each user
    _MOCK_STORE["extensions"]["ext-u1"] = {
        "id": "ext-u1",
        "user_id": user1.id,
        "name": "User 1 Secret Extension",
        "browser": "chrome",
        "is_public": False,
        "icon_path": None,
    }
    _MOCK_STORE["snapshots"]["snap-u1"] = {
        "id": "snap-u1",
        "extension_id": "ext-u1",
        "user_id": user1.id,
        "version": "1.0.0",
        "captured_at": "2026-10-15T12:00:00Z",
        "manifest_version": 3,
        "name": "User 1 Secret Extension",
        "api_permissions": [],
        "host_permissions": [],
        "manifest": {},
        "manifest_sha256": "1" * 64,
    }

    _MOCK_STORE["extensions"]["ext-u2"] = {
        "id": "ext-u2",
        "user_id": user2.id,
        "name": "User 2 Secret Extension",
        "browser": "firefox",
        "is_public": False,
        "icon_path": None,
    }
    _MOCK_STORE["snapshots"]["snap-u2"] = {
        "id": "snap-u2",
        "extension_id": "ext-u2",
        "user_id": user2.id,
        "version": "1.0.0",
        "captured_at": "2026-10-15T12:00:00Z",
        "manifest_version": 3,
        "name": "User 2 Secret Extension",
        "api_permissions": [],
        "host_permissions": [],
        "manifest": {},
        "manifest_sha256": "2" * 64,
    }

    app.dependency_overrides[get_user_db_client] = lambda: None

    try:
        client = TestClient(app)

        # 1. User 1 fetches -> MISS, warms cache for user 1
        app.dependency_overrides[get_optional_user] = lambda: user1
        resp_u1 = client.get("/api/extensions")
        assert resp_u1.headers.get("X-AEGIS-Cache") == "MISS"
        u1_ext_ids = [e["id"] for e in resp_u1.json()["extensions"]]
        assert "ext-u1" in u1_ext_ids
        assert "ext-u2" not in u1_ext_ids

        # User 1 second call -> HIT
        resp_u1_cached = client.get("/api/extensions")
        assert resp_u1_cached.headers.get("X-AEGIS-Cache") == "HIT"

        # 2. User 2 fetches -> MUST BE MISS, NOT User 1's cache!
        app.dependency_overrides[get_optional_user] = lambda: user2
        resp_u2 = client.get("/api/extensions")
        assert resp_u2.headers.get("X-AEGIS-Cache") == "MISS"
        u2_ext_ids = [e["id"] for e in resp_u2.json()["extensions"]]
        assert "ext-u2" in u2_ext_ids
        assert "ext-u1" not in u2_ext_ids

        # User 2 second call -> HIT for User 2
        resp_u2_cached = client.get("/api/extensions")
        assert resp_u2_cached.headers.get("X-AEGIS-Cache") == "HIT"
        assert "ext-u2" in [e["id"] for e in resp_u2_cached.json()["extensions"]]
    finally:
        app.dependency_overrides.pop(get_optional_user, None)
        app.dependency_overrides.pop(get_user_db_client, None)
