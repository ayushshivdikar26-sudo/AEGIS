-- AEGIS Database Schema: Migration 0001
-- Tables: extensions, extension_snapshots, snapshot_permissions, permission_creep_records, ai_analyses
-- Enforces integrity constraints, foreign keys with cascade delete, immutability, and quotas (PRD Part 2b).

create extension if not exists pgcrypto;

-- ============================================================================
-- 1. Table: public.extensions
-- ============================================================================
create table if not exists public.extensions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  browser     text not null check (browser in ('chrome', 'edge', 'firefox', 'brave', 'opera', 'other')),
  store_id    text check (store_id ~ '^[A-Za-z0-9._@{}-]{1,128}$'),
  name        text not null check (char_length(name) between 1 and 200),
  icon_path   text check (char_length(icon_path) <= 300),
  is_public   boolean not null default false,
  source      text not null default 'user' check (source in ('user', 'catalog_seed', 'fixture')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (id, user_id)
);

create unique index if not exists extensions_user_store_uq
  on public.extensions (user_id, browser, store_id) where store_id is not null;
create index if not exists extensions_user_idx on public.extensions (user_id);
create index if not exists extensions_public_idx on public.extensions (is_public) where is_public = true;

-- ============================================================================
-- 2. Table: public.extension_snapshots (Append-only)
-- ============================================================================
create table if not exists public.extension_snapshots (
  id                        uuid primary key default gen_random_uuid(),
  extension_id              uuid not null,
  user_id                   uuid not null default auth.uid(),
  version                   text not null check (char_length(version) between 1 and 64),
  version_key               integer[],                -- parsed numeric version array, null if not parseable
  manifest_version          smallint not null check (manifest_version in (2, 3)),
  name                      text not null check (char_length(name) between 1 and 200),
  description               text check (char_length(description) <= 2000),
  api_permissions           text[] not null default '{}' check (cardinality(api_permissions) <= 500),
  host_permissions          text[] not null default '{}' check (cardinality(host_permissions) <= 500),
  optional_api_permissions  text[] not null default '{}' check (cardinality(optional_api_permissions) <= 500),
  optional_host_permissions text[] not null default '{}' check (cardinality(optional_host_permissions) <= 500),
  content_script_matches    text[] not null default '{}' check (cardinality(content_script_matches) <= 500),
  features                  text[] not null default '{}' check (cardinality(features) <= 50),
  manifest                  jsonb not null,            -- sanitized original manifest, <= 256 KB
  manifest_sha256           text not null check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  captured_at               timestamptz not null default now(),
  foreign key (extension_id, user_id)
    references public.extensions (id, user_id) on delete cascade,
  unique (extension_id, version),
  unique (id, user_id)
);

create index if not exists snapshots_ext_idx
  on public.extension_snapshots (extension_id, version_key desc nulls last, captured_at desc);
create index if not exists snapshots_user_idx
  on public.extension_snapshots (user_id);

-- ============================================================================
-- 3. Table: public.snapshot_permissions (Normalized permission records)
-- ============================================================================
create table if not exists public.snapshot_permissions (
  id              uuid primary key default gen_random_uuid(),
  snapshot_id     uuid not null,
  extension_id    uuid not null,
  user_id         uuid not null default auth.uid(),
  permission_type text not null check (permission_type in ('api', 'host', 'optional_api', 'optional_host', 'content_script')),
  permission_name text not null check (char_length(permission_name) between 1 and 2048),
  created_at      timestamptz not null default now(),
  foreign key (snapshot_id, user_id)
    references public.extension_snapshots (id, user_id) on delete cascade,
  foreign key (extension_id, user_id)
    references public.extensions (id, user_id) on delete cascade,
  unique (snapshot_id, permission_type, permission_name)
);

create index if not exists snapshot_perms_ext_idx
  on public.snapshot_permissions (extension_id, permission_name);
create index if not exists snapshot_perms_user_idx
  on public.snapshot_permissions (user_id);

-- ============================================================================
-- 4. Table: public.permission_creep_records (Immutable comparison audit records)
-- ============================================================================
create table if not exists public.permission_creep_records (
  id                    uuid primary key default gen_random_uuid(),
  extension_id          uuid not null,
  user_id               uuid not null default auth.uid(),
  from_version          text not null check (char_length(from_version) between 1 and 64),
  to_version            text not null check (char_length(to_version) between 1 and 64),
  from_snapshot_id      uuid not null,
  to_snapshot_id        uuid not null,
  outcome               text not null check (outcome in ('significant_increase', 'needs_review', 'no_significant_creep', 'baseline_not_available')),
  added_permissions     text[] not null default '{}',
  removed_permissions   text[] not null default '{}',
  broadened_hosts       jsonb not null default '[]'::jsonb,
  diff_summary          jsonb not null default '{}'::jsonb,
  detected_at           timestamptz not null default now(),
  foreign key (extension_id, user_id)
    references public.extensions (id, user_id) on delete cascade,
  foreign key (from_snapshot_id, user_id)
    references public.extension_snapshots (id, user_id) on delete cascade,
  foreign key (to_snapshot_id, user_id)
    references public.extension_snapshots (id, user_id) on delete cascade,
  unique (extension_id, from_version, to_version)
);

create index if not exists creep_ext_idx
  on public.permission_creep_records (extension_id, detected_at desc);
create index if not exists creep_user_idx
  on public.permission_creep_records (user_id);

-- ============================================================================
-- 5. Table: public.ai_analyses (Cache for Milestone M8, Deferred)
-- ============================================================================
create table if not exists public.ai_analyses (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  snapshot_id   uuid not null,
  input_sha256  text not null check (input_sha256 ~ '^[0-9a-f]{64}$'),
  model         text not null check (char_length(model) <= 100),
  result        jsonb not null,
  created_at    timestamptz not null default now(),
  foreign key (snapshot_id, user_id)
    references public.extension_snapshots (id, user_id) on delete cascade,
  unique (snapshot_id, input_sha256, model)
);

create index if not exists ai_analyses_user_idx on public.ai_analyses (user_id);

-- ============================================================================
-- 6. Trigger Functions & Triggers
-- ============================================================================

-- Function 6.1: updated_at updater
create or replace function public.set_updated_at()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_extensions_updated_at on public.extensions;
create trigger trg_extensions_updated_at
  before update on public.extensions
  for each row
  execute function public.set_updated_at();

-- Function 6.2: Manifest byte size validation (262,144 bytes limit)
create or replace function public.validate_manifest_size()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if octet_length(new.manifest::text) > 262144 then
    raise exception 'Manifest payload exceeds maximum allowed size of 262,144 bytes'
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_validate_manifest_size on public.extension_snapshots;
create trigger trg_validate_manifest_size
  before insert or update on public.extension_snapshots
  for each row
  execute function public.validate_manifest_size();

-- Function 6.3: Snapshot array elements validation
-- (no empty items, length <= 2048, no ASCII control chars)
create or replace function public.validate_snapshot_arrays()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  arr text[];
  item text;
begin
  foreach arr slice 1 in array array[
    new.api_permissions,
    new.host_permissions,
    new.optional_api_permissions,
    new.optional_host_permissions,
    new.content_script_matches
  ] loop
    if arr is not null then
      foreach item in array arr loop
        if item is null or char_length(item) = 0 or char_length(item) > 2048 then
          raise exception 'Snapshot permission item must be between 1 and 2048 characters'
            using errcode = 'check_violation';
        end if;
        if item ~ '[\x00-\x1f\x7f]' then
          raise exception 'Snapshot permission item contains prohibited control characters'
            using errcode = 'check_violation';
        end if;
      end loop;
    end if;
  end loop;
  return new;
end;
$$;

drop trigger if exists trg_validate_snapshot_arrays on public.extension_snapshots;
create trigger trg_validate_snapshot_arrays
  before insert or update on public.extension_snapshots
  for each row
  execute function public.validate_snapshot_arrays();

-- Function 6.4: Immutability triggers (snapshots, permissions, creep)
create or replace function public.raise_immutable_modification()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  raise exception 'Modification disallowed: records in this table are append-only and immutable'
    using errcode = 'integrity_constraint_violation';
end;
$$;

drop trigger if exists trg_snapshot_immutability on public.extension_snapshots;
create trigger trg_snapshot_immutability
  before update on public.extension_snapshots
  for each row
  execute function public.raise_immutable_modification();

drop trigger if exists trg_snapshot_perms_immutability on public.snapshot_permissions;
create trigger trg_snapshot_perms_immutability
  before update on public.snapshot_permissions
  for each row
  execute function public.raise_immutable_modification();

drop trigger if exists trg_creep_immutability on public.permission_creep_records;
create trigger trg_creep_immutability
  before update on public.permission_creep_records
  for each row
  execute function public.raise_immutable_modification();

-- Function 6.5: User quotas (500 extensions per user, 100 snapshots per extension)
create or replace function public.enforce_quota_limits()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  ext_count integer;
  snap_count integer;
  max_ext constant integer := 500;
  max_snap constant integer := 100;
begin
  if tg_table_name = 'extensions' then
    select count(*) into ext_count from public.extensions where user_id = new.user_id;
    if ext_count >= max_ext then
      raise exception 'Quota exceeded: maximum of % extensions per user', max_ext
        using errcode = 'check_violation';
    end if;
  elsif tg_table_name = 'extension_snapshots' then
    select count(*) into snap_count from public.extension_snapshots where extension_id = new.extension_id;
    if snap_count >= max_snap then
      raise exception 'Quota exceeded: maximum of % snapshots per extension', max_snap
        using errcode = 'check_violation';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_extensions_quota on public.extensions;
create trigger trg_extensions_quota
  before insert on public.extensions
  for each row
  execute function public.enforce_quota_limits();

drop trigger if exists trg_snapshots_quota on public.extension_snapshots;
create trigger trg_snapshots_quota
  before insert on public.extension_snapshots
  for each row
  execute function public.enforce_quota_limits();

-- Function 6.6: Synchronize snapshot arrays into snapshot_permissions table
create or replace function public.sync_snapshot_permissions()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  perm text;
begin
  if new.api_permissions is not null then
    foreach perm in array new.api_permissions loop
      insert into public.snapshot_permissions (snapshot_id, extension_id, user_id, permission_type, permission_name)
      values (new.id, new.extension_id, new.user_id, 'api', perm)
      on conflict (snapshot_id, permission_type, permission_name) do nothing;
    end loop;
  end if;

  if new.host_permissions is not null then
    foreach perm in array new.host_permissions loop
      insert into public.snapshot_permissions (snapshot_id, extension_id, user_id, permission_type, permission_name)
      values (new.id, new.extension_id, new.user_id, 'host', perm)
      on conflict (snapshot_id, permission_type, permission_name) do nothing;
    end loop;
  end if;

  if new.optional_api_permissions is not null then
    foreach perm in array new.optional_api_permissions loop
      insert into public.snapshot_permissions (snapshot_id, extension_id, user_id, permission_type, permission_name)
      values (new.id, new.extension_id, new.user_id, 'optional_api', perm)
      on conflict (snapshot_id, permission_type, permission_name) do nothing;
    end loop;
  end if;

  if new.optional_host_permissions is not null then
    foreach perm in array new.optional_host_permissions loop
      insert into public.snapshot_permissions (snapshot_id, extension_id, user_id, permission_type, permission_name)
      values (new.id, new.extension_id, new.user_id, 'optional_host', perm)
      on conflict (snapshot_id, permission_type, permission_name) do nothing;
    end loop;
  end if;

  if new.content_script_matches is not null then
    foreach perm in array new.content_script_matches loop
      insert into public.snapshot_permissions (snapshot_id, extension_id, user_id, permission_type, permission_name)
      values (new.id, new.extension_id, new.user_id, 'content_script', perm)
      on conflict (snapshot_id, permission_type, permission_name) do nothing;
    end loop;
  end if;

  return new;
end;
$$;

drop trigger if exists trg_sync_snapshot_permissions on public.extension_snapshots;
create trigger trg_sync_snapshot_permissions
  after insert on public.extension_snapshots
  for each row
  execute function public.sync_snapshot_permissions();
