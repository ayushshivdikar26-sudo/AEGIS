#!/usr/bin/env python3
"""
AEGIS Deterministic Mock Seed Data Generator (Backend/db/seed/seed_mock_extensions.py)
Reads dev/mock-api/fixtures/dataset.json and produces deterministic database seed records
with source='catalog_seed' and is_public=true (PRD Part 2b).
"""

import json
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
FIXTURES_FILE = BASE_DIR / "dev" / "mock-api" / "fixtures" / "dataset.json"
OUTPUT_SQL_FILE = BASE_DIR / "Backend" / "db" / "seed" / "mock_seed.sql"

# Well-known deterministic UUIDs for seed catalog
SYSTEM_SEED_USER_ID = "00000000-0000-0000-0000-000000000001"
NAMESPACE_EXT = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

BROWSER_MAP = {
    "google chrome": "chrome",
    "chrome": "chrome",
    "mozilla firefox": "firefox",
    "firefox": "firefox",
    "microsoft edge": "edge",
    "edge": "edge",
    "brave": "brave",
    "opera": "opera",
}


def parse_version_key(v_str: str) -> list[int] | None:
    parts = []
    for p in v_str.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            return None
    return parts if parts else None


def escape_sql(val: str | None) -> str:
    if val is None:
        return "null"
    clean = val.replace("'", "''")
    return f"'{clean}'"


def text_array_sql(items: list[str]) -> str:
    if not items:
        return "'{}'::text[]"
    escaped_items = []
    for it in items:
        clean = it.replace('"', '\\"').replace("'", "''")
        escaped_items.append(f'"{clean}"')
    inner = ",".join(escaped_items)
    return f"'{inner}'::text[]"


def generate_seed_sql(seed_user_id: str = SYSTEM_SEED_USER_ID) -> str:
    with open(FIXTURES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    extensions = data.get("extensions", [])
    sql_lines = [
        "-- AEGIS Deterministic Mock Seed Data (8 Mock Extensions)",
        "-- Separated from user data with source = 'catalog_seed' and is_public = true",
        f"-- Seed User ID: {seed_user_id}",
        "",
        "begin;",
        "",
        "-- 0. Optional: Ensure system seed user placeholder exists in auth.users if foreign key is active",
        "do $$",
        "begin",
        "  if exists (select 1 from information_schema.tables where table_schema = 'auth' and table_name = 'users') then",
        f"    if not exists (select 1 from auth.users where id = '{seed_user_id}') then",
        "      insert into auth.users (id, email, role, aud, created_at, updated_at)",
        f"      values ('{seed_user_id}', 'catalog-seed@aegis.local', 'authenticated', 'authenticated', now(), now());",
        "    end if;",
        "  end if;",
        "end $$;",
        "",
    ]

    for ext in extensions:
        ext_slug = ext["id"]
        ext_uuid = str(uuid.uuid5(NAMESPACE_EXT, f"aegis:extension:{ext_slug}"))
        raw_browser = ext.get("browser", "chrome").lower()
        browser = BROWSER_MAP.get(raw_browser, "other")
        name = ext.get("name", "Unknown Extension")
        desc_obj = ext.get("description", {})
        desc_text = (
            desc_obj.get("text") if isinstance(desc_obj, dict) else str(desc_obj)
        )
        current_version = ext.get("version", "1.0.0")

        sql_lines.append(f"-- Extension: {name} ({ext_slug})")
        sql_lines.append(
            f"insert into public.extensions (id, user_id, browser, store_id, name, is_public, source) values "
            f"('{ext_uuid}', '{seed_user_id}', '{browser}', {escape_sql(ext_slug)}, {escape_sql(name)}, true, 'catalog_seed') "
            f"on conflict (id) do update set name = excluded.name, is_public = true, source = 'catalog_seed';"
        )

        # Versions / Snapshots
        versions_list = ext.get("versions", [])
        if not versions_list:
            versions_list = [{"version": current_version, "released": "2026-01-01"}]

        # Permissions from fixture
        perms_obj = ext.get("permissions", {})
        api_perms = [p["name"] for p in perms_obj.get("api", []) if "name" in p]
        host_perms = [p["name"] for p in perms_obj.get("host", []) if "name" in p]
        opt_perms = [p["name"] for p in perms_obj.get("optional", []) if "name" in p]

        snapshot_uuids = {}
        for ver_info in versions_list:
            v_str = ver_info["version"]
            snap_uuid = str(
                uuid.uuid5(NAMESPACE_EXT, f"aegis:snapshot:{ext_slug}:{v_str}")
            )
            snapshot_uuids[v_str] = snap_uuid
            v_key = parse_version_key(v_str)
            v_key_sql = f"array{v_key}" if v_key else "null"

            # Synthetic valid manifest JSON for snapshot
            synthetic_manifest = {
                "manifest_version": 3,
                "name": name,
                "version": v_str,
                "description": desc_text or "",
                "permissions": api_perms,
                "host_permissions": host_perms,
                "optional_permissions": opt_perms,
            }
            manifest_json_str = json.dumps(synthetic_manifest).replace("'", "''")
            sha256_mock = f"{snap_uuid.replace('-', '')}{snap_uuid.replace('-', '')}"[
                :64
            ]

            sql_lines.append(
                f"insert into public.extension_snapshots ("
                f"id, extension_id, user_id, version, version_key, manifest_version, name, description, "
                f"api_permissions, host_permissions, optional_api_permissions, manifest, manifest_sha256"
                f") values ("
                f"'{snap_uuid}', '{ext_uuid}', '{seed_user_id}', '{v_str}', {v_key_sql}, 3, "
                f"{escape_sql(name)}, {escape_sql(desc_text)}, "
                f"{text_array_sql(api_perms)}, {text_array_sql(host_perms)}, {text_array_sql(opt_perms)}, "
                f"'{manifest_json_str}'::jsonb, '{sha256_mock}'"
                f") on conflict (extension_id, version) do nothing;"
            )

        # Creep records if available
        creep_data = ext.get("creep", {})
        if creep_data.get("available") and len(versions_list) >= 2:
            from_v = versions_list[1]["version"]
            to_v = versions_list[0]["version"]
            from_sid = snapshot_uuids.get(from_v)
            to_sid = snapshot_uuids.get(to_v)
            if from_sid and to_sid:
                creep_uuid = str(
                    uuid.uuid5(NAMESPACE_EXT, f"aegis:creep:{ext_slug}:{from_v}:{to_v}")
                )
                added = [i["name"] for i in creep_data.get("added", []) if "name" in i]
                removed = [
                    i["name"] for i in creep_data.get("removed", []) if "name" in i
                ]
                broadened = json.dumps(creep_data.get("broadened", [])).replace(
                    "'", "''"
                )
                outcome = (
                    "significant_increase"
                    if creep_data.get("score_to", 0) - creep_data.get("score_from", 0)
                    >= 15
                    else "no_significant_creep"
                )

                sql_lines.append(
                    f"insert into public.permission_creep_records ("
                    f"id, extension_id, user_id, from_version, to_version, from_snapshot_id, to_snapshot_id, "
                    f"outcome, added_permissions, removed_permissions, broadened_hosts"
                    f") values ("
                    f"'{creep_uuid}', '{ext_uuid}', '{seed_user_id}', '{from_v}', '{to_v}', "
                    f"'{from_sid}', '{to_sid}', '{outcome}', {text_array_sql(added)}, {text_array_sql(removed)}, '{broadened}'::jsonb"
                    f") on conflict (extension_id, from_version, to_version) do nothing;"
                )

        sql_lines.append("")

    sql_lines.append("commit;")
    return "\n".join(sql_lines)


def main():
    print(f"Generating deterministic mock seed SQL from {FIXTURES_FILE}...")
    sql_content = generate_seed_sql()
    OUTPUT_SQL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_SQL_FILE, "w", encoding="utf-8") as f:
        f.write(sql_content)
    print(f"Saved seed SQL to {OUTPUT_SQL_FILE} ({len(sql_content)} bytes).")


if __name__ == "__main__":
    main()
