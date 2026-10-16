-- AEGIS Database Schema: Migration 0002
-- Row Level Security (RLS) Policies & Role Grants
-- Least privilege enforcement: verified public catalogue read, private user data isolation,
-- service-role privileged operations, and append-only constraints (PRD Part 2b s4).

-- ============================================================================
-- 1. Enable and FORCE Row Level Security on all public tables
-- ============================================================================
alter table public.extensions enable row level security;
alter table public.extensions force row level security;

alter table public.extension_snapshots enable row level security;
alter table public.extension_snapshots force row level security;

alter table public.snapshot_permissions enable row level security;
alter table public.snapshot_permissions force row level security;

alter table public.permission_creep_records enable row level security;
alter table public.permission_creep_records force row level security;

alter table public.ai_analyses enable row level security;
alter table public.ai_analyses force row level security;

-- ============================================================================
-- 2. Revoke broad defaults from anon & grant least-privilege verbs
-- ============================================================================
revoke all on all tables in schema public from anon;
revoke all on all functions in schema public from anon;
revoke all on all sequences in schema public from anon;

alter default privileges in schema public revoke all on tables from anon;
alter default privileges in schema public revoke all on functions from anon;
alter default privileges in schema public revoke all on sequences from anon;

-- Grant verified catalog read-only access to anon on public catalogue tables
grant select on public.extensions to anon;
grant select on public.extension_snapshots to anon;
grant select on public.snapshot_permissions to anon;
grant select on public.permission_creep_records to anon;

-- Grant specific verbs to authenticated role
grant select, insert, update, delete on public.extensions to authenticated;
grant select, insert on public.extension_snapshots to authenticated;
grant select, insert on public.snapshot_permissions to authenticated;
grant select, insert on public.permission_creep_records to authenticated;
grant select, insert, delete on public.ai_analyses to authenticated;

-- Explicitly ensure UPDATE and DELETE are revoked where immutability is required
revoke update, delete on public.extension_snapshots from authenticated;
revoke update, delete on public.snapshot_permissions from authenticated;
revoke update, delete on public.permission_creep_records from authenticated;
revoke update on public.ai_analyses from authenticated;

-- ============================================================================
-- 3. Policies: public.extensions
-- ============================================================================
drop policy if exists extensions_select_policy on public.extensions;
create policy extensions_select_policy on public.extensions
  for select to anon, authenticated
  using (
    (is_public = true) or
    (user_id = (select auth.uid()))
  );

drop policy if exists extensions_insert_policy on public.extensions;
create policy extensions_insert_policy on public.extensions
  for insert to authenticated
  with check (
    user_id = (select auth.uid()) and
    is_public = false
  );

drop policy if exists extensions_update_policy on public.extensions;
create policy extensions_update_policy on public.extensions
  for update to authenticated
  using (user_id = (select auth.uid()))
  with check (
    user_id = (select auth.uid()) and
    is_public = false
  );

drop policy if exists extensions_delete_policy on public.extensions;
create policy extensions_delete_policy on public.extensions
  for delete to authenticated
  using (user_id = (select auth.uid()));

-- ============================================================================
-- 4. Policies: public.extension_snapshots (Append-only)
-- ============================================================================
drop policy if exists snapshots_select_policy on public.extension_snapshots;
create policy snapshots_select_policy on public.extension_snapshots
  for select to anon, authenticated
  using (
    (user_id = (select auth.uid())) or
    exists (
      select 1 from public.extensions e
      where e.id = extension_snapshots.extension_id and e.is_public = true
    )
  );

drop policy if exists snapshots_insert_policy on public.extension_snapshots;
create policy snapshots_insert_policy on public.extension_snapshots
  for insert to authenticated
  with check (
    user_id = (select auth.uid()) and
    exists (
      select 1 from public.extensions e
      where e.id = extension_snapshots.extension_id and e.user_id = (select auth.uid())
    )
  );

-- ============================================================================
-- 5. Policies: public.snapshot_permissions (Append-only)
-- ============================================================================
drop policy if exists snapshot_perms_select_policy on public.snapshot_permissions;
create policy snapshot_perms_select_policy on public.snapshot_permissions
  for select to anon, authenticated
  using (
    (user_id = (select auth.uid())) or
    exists (
      select 1 from public.extensions e
      where e.id = snapshot_permissions.extension_id and e.is_public = true
    )
  );

drop policy if exists snapshot_perms_insert_policy on public.snapshot_permissions;
create policy snapshot_perms_insert_policy on public.snapshot_permissions
  for insert to authenticated
  with check (
    user_id = (select auth.uid()) and
    exists (
      select 1 from public.extensions e
      where e.id = snapshot_permissions.extension_id and e.user_id = (select auth.uid())
    )
  );

-- ============================================================================
-- 6. Policies: public.permission_creep_records (Immutable audit records)
-- ============================================================================
drop policy if exists creep_select_policy on public.permission_creep_records;
create policy creep_select_policy on public.permission_creep_records
  for select to anon, authenticated
  using (
    (user_id = (select auth.uid())) or
    exists (
      select 1 from public.extensions e
      where e.id = permission_creep_records.extension_id and e.is_public = true
    )
  );

drop policy if exists creep_insert_policy on public.permission_creep_records;
create policy creep_insert_policy on public.permission_creep_records
  for insert to authenticated
  with check (
    user_id = (select auth.uid()) and
    exists (
      select 1 from public.extensions e
      where e.id = permission_creep_records.extension_id and e.user_id = (select auth.uid())
    )
  );

-- ============================================================================
-- 7. Policies: public.ai_analyses (Cache for Milestone M8, Deferred)
-- ============================================================================
drop policy if exists ai_analyses_select_policy on public.ai_analyses;
create policy ai_analyses_select_policy on public.ai_analyses
  for select to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists ai_analyses_insert_policy on public.ai_analyses;
create policy ai_analyses_insert_policy on public.ai_analyses
  for insert to authenticated
  with check (
    user_id = (select auth.uid()) and
    exists (
      select 1 from public.extension_snapshots s
      where s.id = ai_analyses.snapshot_id and s.user_id = (select auth.uid())
    )
  );

drop policy if exists ai_analyses_delete_policy on public.ai_analyses;
create policy ai_analyses_delete_policy on public.ai_analyses
  for delete to authenticated
  using (user_id = (select auth.uid()));
