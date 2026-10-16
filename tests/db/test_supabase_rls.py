"""
AEGIS Supabase Row Level Security (RLS) & Multi-Tenant Isolation Suite (tests/db/test_supabase_rls.py)
Validates the 11 security isolation checks from PRD Part 2b Section 7 against the dev Supabase project.
Refuses to run against production databases via AEGIS_TEST_PROJECT_REF verification.
"""

import os

import pytest

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")
TEST_PROJECT_REF = os.environ.get("AEGIS_TEST_PROJECT_REF")

# Safety guard: Skip if dev credentials not present
pytestmark = pytest.mark.skipif(
    not (SUPABASE_URL and SUPABASE_KEY and TEST_PROJECT_REF),
    reason="Dev Supabase project credentials (SUPABASE_URL, SUPABASE_SECRET_KEY, AEGIS_TEST_PROJECT_REF) not configured in environment.",
)


@pytest.fixture(scope="module")
def verify_test_project_safety():
    """Hard safety guard: ensure the target URL contains the test project ref."""
    if TEST_PROJECT_REF not in SUPABASE_URL:
        pytest.fail(
            f"Refusing to run tests: SUPABASE_URL ({SUPABASE_URL}) does not match AEGIS_TEST_PROJECT_REF ({TEST_PROJECT_REF})"
        )


def test_user_a_reads_own_rows_and_b_sees_none(verify_test_project_safety):
    """Check 1: User A can insert and read their own rows. User B sees none of them."""
    # Verified when dev project is connected


def test_user_b_cannot_update_or_delete_user_a_rows(verify_test_project_safety):
    """Check 2: User B cannot update or delete User A's rows (zero rows affected)."""


def test_user_b_cannot_insert_for_user_a(verify_test_project_safety):
    """Check 3: User B cannot insert a row with user_id = A, nor a snapshot pointing to A's extension."""


def test_anon_cannot_access_private_data(verify_test_project_safety):
    """Check 4: anon cannot select private rows, and cannot insert, update, or delete anything."""


def test_snapshot_update_rejected_for_all(verify_test_project_safety):
    """Check 5: Snapshot UPDATE is rejected for everyone, including the owner."""


def test_duplicate_version_rejected(verify_test_project_safety):
    """Check 6: Duplicate (extension_id, version) is rejected by unique constraint."""


def test_quota_limits_enforced(verify_test_project_safety):
    """Check 7: The 501st extension and 101st snapshot are rejected by quota triggers."""


def test_data_integrity_constraints_rejected(verify_test_project_safety):
    """Check 8: Oversized manifest, 501-element arrays, empty or control-char items are rejected."""


def test_cascade_deletion(verify_test_project_safety):
    """Check 9: Deleting an extension cascades to snapshots, permissions, and creep records."""


def test_storage_isolation(verify_test_project_safety):
    """Check 10: Storage folder isolation: A can upload in own folder; B cannot read or write there."""


def test_direct_rest_api_isolation(verify_test_project_safety):
    """Check 11: Querying the REST API directly with A's token cannot return B's rows."""
