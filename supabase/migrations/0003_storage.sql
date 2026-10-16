-- AEGIS Database Schema: Migration 0003
-- Storage Configuration for Extension Icons (PRD Part 2b s5)
-- Private bucket 'extension-icons' with MIME restrictions, 256 KB size limit, and user folder isolation.

-- ============================================================================
-- 1. Create Private Storage Bucket
-- ============================================================================
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'extension-icons',
  'extension-icons',
  false,
  262144, -- 256 KB
  array['image/png', 'image/jpeg', 'image/webp']
)
on conflict (id) do update set
  public = false,
  file_size_limit = 262144,
  allowed_mime_types = array['image/png', 'image/jpeg', 'image/webp'];

-- ============================================================================
-- 2. Storage Objects RLS Policies
-- ============================================================================
-- Object path structure: <user_id>/<extension_id>.<ext>

-- 2.1 SELECT Policy: Users can only read icons inside their own folder
drop policy if exists icons_select_policy on storage.objects;
create policy icons_select_policy on storage.objects
  for select to authenticated
  using (
    bucket_id = 'extension-icons' and
    (storage.foldername(name))[1] = (select auth.uid())::text
  );

-- 2.2 INSERT Policy: Users can only upload icons inside their own folder
drop policy if exists icons_insert_policy on storage.objects;
create policy icons_insert_policy on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'extension-icons' and
    (storage.foldername(name))[1] = (select auth.uid())::text
  );

-- 2.3 DELETE Policy: Users can only delete icons inside their own folder
drop policy if exists icons_delete_policy on storage.objects;
create policy icons_delete_policy on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'extension-icons' and
    (storage.foldername(name))[1] = (select auth.uid())::text
  );

-- Note: No UPDATE policy is created. Replacements must be performed via DELETE then INSERT.
