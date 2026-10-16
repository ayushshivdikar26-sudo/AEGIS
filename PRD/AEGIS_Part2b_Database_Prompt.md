# AEGIS Part 2b: Supabase database (prompt for Antigravity)

## 0. Context and rules

AEGIS is a browser-extension Permission Creep Auditor. Source of truth: `AEGIS_Handover_Document.md`. Stack and security rules: `AEGIS_Antigravity_Build_Prompt.md`. Part 2a (core analysis modules) is done and defines `ParsedManifest`.

| Step | Scope |
|---|---|
| 2a | Core analysis modules (done) |
| **2b (this prompt)** | Supabase database: schema, RLS, storage, quotas, migration of real data, DB tests |
| 2c | FastAPI connecting frontend and backend |
| 2d | `justification_checker`, `ai_analyzer` |
| 3 | Testing and security checks |

**Do only 2b.** No FastAPI routes, no frontend changes.

**Rules.** Never put a key, password, or connection string in code, chat, logs, or Git. If you need one, name the environment variable and tell me to set it myself. Never use or touch a production database for tests. Do not insert sample, demo, or test rows into any shared database. Do not claim anything works unless you ran it.

---

## 1. Phase 0: inspect and plan (do this first)

Report the existing SQLite schema and row counts (read only), which rows look like sample or test data (list them, do not decide for me), and whether Docker and the Supabase CLI are available. Then propose the migration files and the test environment. **Stop and wait for my approval before editing.**

**Test environment.** Prefer the Supabase CLI local stack (`supabase start`, needs Docker). If Docker is not available, use a separate dev Supabase project that I create, never the project that will serve real users. Tests create their own users and delete them afterwards.

---

## 2. Design decisions (already made)

- **Architecture.** The backend (2c) talks to Supabase using the **signed-in user's own JWT**, so Row Level Security is enforced on every query. The service role key is used only in a small isolated module for narrow admin tasks and never to read user data. The browser never holds a Supabase key (auth is mediated by the backend in 2c).
- **The knowledge base stays in `Backend/data/permission_knowledge.json`.** Do not copy it into a table; two sources of truth is a hazard.
- **Scores are never stored.** They are derived by pure code (2a) on every read, so a rule change cannot leave stale numbers behind. API responses carry `formula_version` and `knowledge_version`.
- **Snapshots are append-only.** A saved version is never edited, so comparisons stay reproducible.
- **Passwords are handled by Supabase Auth.** No password columns anywhere.

---

## 3. Schema

Write versioned migrations in `supabase/migrations/` (`0001_init.sql`, `0002_rls.sql`, `0003_storage.sql`, and so on). Skeleton below. Improve it where you have a reason, and explain each change in the report.

```sql
create extension if not exists pgcrypto;

create table public.extensions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  browser     text not null check (browser in ('chrome','edge','firefox','brave','opera','other')),
  store_id    text check (store_id ~ '^[A-Za-z0-9._@{}-]{1,128}$'),
  name        text not null check (char_length(name) between 1 and 200),
  icon_path   text check (char_length(icon_path) <= 300),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (id, user_id)
);
create unique index extensions_user_store_uq
  on public.extensions (user_id, browser, store_id) where store_id is not null;
create index extensions_user_idx on public.extensions (user_id);

create table public.extension_snapshots (
  id                        uuid primary key default gen_random_uuid(),
  extension_id              uuid not null,
  user_id                   uuid not null default auth.uid(),
  version                   text not null check (char_length(version) between 1 and 64),
  version_key               integer[],                -- parsed numeric version, null if not parseable
  manifest_version          smallint not null check (manifest_version in (2,3)),
  name                      text not null check (char_length(name) between 1 and 200),
  description               text check (char_length(description) <= 2000),
  api_permissions           text[] not null default '{}' check (cardinality(api_permissions) <= 500),
  host_permissions          text[] not null default '{}' check (cardinality(host_permissions) <= 500),
  optional_api_permissions  text[] not null default '{}' check (cardinality(optional_api_permissions) <= 500),
  optional_host_permissions text[] not null default '{}' check (cardinality(optional_host_permissions) <= 500),
  content_script_matches    text[] not null default '{}' check (cardinality(content_script_matches) <= 500),
  features                  text[] not null default '{}' check (cardinality(features) <= 50),
  manifest                  jsonb not null,            -- sanitized original, size-capped below
  manifest_sha256           text not null check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  captured_at               timestamptz not null default now(),
  foreign key (extension_id, user_id)
    references public.extensions (id, user_id) on delete cascade,
  unique (extension_id, version)
);
create index snapshots_ext_idx on public.extension_snapshots (extension_id, version_key desc nulls last, captured_at desc);

create table public.ai_analyses (            -- cache for 2d, so repeat clicks do not spend quota
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  snapshot_id   uuid not null references public.extension_snapshots(id) on delete cascade,
  input_sha256  text not null check (input_sha256 ~ '^[0-9a-f]{64}$'),
  model         text not null check (char_length(model) <= 100),
  result        jsonb not null,
  created_at    timestamptz not null default now(),
  unique (snapshot_id, input_sha256, model)
);
```

**Extra integrity (use triggers where a CHECK cannot do it)**
- Cap `manifest` at 262,144 bytes. Try `octet_length(manifest::text)` in a CHECK; if Postgres rejects it as non-immutable, use a validation trigger.
- Validation trigger on snapshots: every array element is non-empty and at most 2,048 characters, and contains no control characters.
- `updated_at` trigger on `extensions`.
- **Immutability trigger** on `extension_snapshots` that raises on any UPDATE (belt and braces on top of having no UPDATE policy or grant).
- **Quota triggers** (constants at the top of the migration): at most 500 extensions per user and 100 snapshots per extension. This stops storage abuse even if someone calls the database API directly.
- Same-user guarantee for `ai_analyses.snapshot_id`: the snapshot must belong to `user_id` (composite FK or trigger).
- Do not enable Realtime on these tables.

---

## 4. Row Level Security

Enable and **force** RLS on every table in `public`. Use the cached form `(select auth.uid())` in policies, for performance. Policies apply to the `authenticated` role only; `anon` gets nothing.

```sql
alter table public.extensions enable row level security;
alter table public.extensions force  row level security;

create policy extensions_select on public.extensions for select to authenticated
  using (user_id = (select auth.uid()));
create policy extensions_insert on public.extensions for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy extensions_update on public.extensions for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy extensions_delete on public.extensions for delete to authenticated
  using (user_id = (select auth.uid()));
```

- `extension_snapshots`: SELECT and INSERT policies only. No UPDATE policy, and `revoke update` from `authenticated`. Deleting an extension must still cascade to its snapshots (referential actions bypass RLS; verify this in a test rather than assuming).
- `ai_analyses`: SELECT, INSERT, and DELETE for the owner.
- `revoke all on all tables in schema public from anon;` and revoke default privileges that Supabase grants to `anon`. Grant only the exact verbs the policies need to `authenticated`.
- No `security definer` function unless it is unavoidable, and then it must set `search_path = ''`, validate `auth.uid()` inside, and be explained in the report.
- Views, if any, must use `security_invoker = true`.

---

## 5. Storage for icons

Private bucket `extension-icons`. Object path is `<user_id>/<extension_id>.<ext>`.

- Bucket settings: private, file size limit 262,144 bytes, allowed MIME types `image/png`, `image/jpeg`, `image/webp`. No SVG.
- Policies on `storage.objects`: SELECT, INSERT, and DELETE allowed only when `bucket_id = 'extension-icons'` and `(storage.foldername(name))[1] = (select auth.uid())::text`. No UPDATE (replace by delete then insert).
- The backend (2c) will check magic bytes and return short-lived signed URLs. Nothing is ever public.

---

## 6. Moving real data

Write `scripts/migrate_sqlite_to_supabase.py`.

- Dry run by default: prints counts and what would change. Real writes require `--apply`, and an explicit `--user-id <uuid>` that I choose.
- Re-derive every normalized column by running each stored manifest through `core.manifest_parser`. Rows that fail to parse are skipped and listed in the report.
- Skip anything I marked as sample or test data after your Phase 0 list. When unsure, skip and ask.
- Reads credentials only from environment variables. Idempotent: running twice creates no duplicates (use `unique (extension_id, version)` and the SHA-256).
- Do not delete the SQLite file. Removing it is a later cleanup step, after I confirm the migration.

---

## 7. Tests (required)

Use pgTAP (`supabase test db`) in `supabase/tests/` if the CLI is available, otherwise a Python script using two real test users and their real JWTs. Cover all of these:

1. User A can insert and read their own rows. User B sees none of them (select returns zero rows).
2. B cannot update or delete A's rows (zero rows affected, no error leak).
3. B cannot insert a row with `user_id = A`. B cannot insert a snapshot pointing at A's extension.
4. `anon` cannot select, insert, update, or delete anything, with or without a valid anon key.
5. Snapshot UPDATE is rejected for everyone, including the owner.
6. Duplicate `(extension_id, version)` is rejected.
7. The 501st extension and the 101st snapshot are rejected by the quota triggers.
8. Oversized manifest, 501-element arrays, empty or control-character array elements, and bad SHA-256 are rejected.
9. Deleting an extension cascades to its snapshots and AI analyses. Deleting a user removes all their data.
10. Storage: A can upload and read in their own folder; B cannot read, list, or write there; a disallowed MIME type and an oversized file are rejected.
11. Querying the REST API directly with A's token cannot return B's rows (this proves RLS holds even if the backend is bypassed).

Tests clean up after themselves and never touch a shared database.

---

## 8. Manual setup document

Write `docs/SUPABASE_SETUP.md` listing the steps only I can do in the Supabase dashboard, each with a one-line reason: create the dev and production projects; apply migrations; confirm RLS shows enabled on all tables; Auth settings (email confirmation on, minimum password length 12, leaked-password protection if my plan supports it, unused providers off, JWT expiry 3600 s, Site URL set); which API keys exist and which one goes where; where to put each variable in `.env` (never committed). Include `.env.example` with placeholders for `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and the JWT settings 2c needs.

---

## 9. Deliverables and report

1. Migrations, tests, the migration script, `docs/SUPABASE_SETUP.md`, `docs/DATABASE.md` (a table-by-table description and an ER sketch in Mermaid), and `.env.example`.
2. A report with the test results (paste the real output), every deviation from the skeleton and why, anything that needs a manual step from me, and anything you could not verify.

Do not describe anything as working unless you ran it.
