# AEGIS Supabase Setup & Configuration Guide

This guide details the exact manual steps required in the Supabase Dashboard to configure development and production projects for AEGIS.

---

## 1. Project Creation

1. **Create Development Project**:
   - Create a dedicated development project (e.g., `aegis-dev`) in your preferred region.
   - *Reason: Tests and migrations must run against an isolated sandbox, never shared with production.*
2. **Create Production Project**:
   - Create a separate production project (e.g., `aegis-prod`).
   - *Reason: Strict isolation of user extension data from development and test harnesses.*

---

## 2. Applying Database Migrations

In the Supabase Dashboard, navigate to the **SQL Editor** (or use the Supabase CLI if linked) and run the migration scripts in sequential order:

1. **Migration 0001 (`supabase/migrations/0001_initial_schema.sql`)**:
   - Creates the `extensions`, `extension_snapshots`, `snapshot_permissions`, `permission_creep_records`, and `ai_analyses` tables, along with foreign keys, immutability triggers, quota triggers, and validation rules.
   - *Reason: Establishes the foundational relational schema and data integrity constraints.*
2. **Migration 0002 (`supabase/migrations/0002_rls_policies.sql`)**:
   - Enables and forces Row-Level Security, restricts public access to verified catalogue records (`is_public = true`), and binds user data to `(select auth.uid())`.
   - *Reason: Enforces tenant isolation so users can never view or modify another user's extensions.*
3. **Migration 0003 (`supabase/migrations/0003_storage.sql`)**:
   - Configures the private `extension-icons` bucket (256 KB size limit, PNG/JPEG/WebP only) and path-based RLS policies.
   - *Reason: Protects uploaded icons with authenticated folder-level access.*
4. **Mock Seed Data (`Backend/db/seed/mock_seed.sql`)** *(Development Project Only)*:
   - Populates the 8 deterministic mock extensions marked as `source = 'catalog_seed'` and `is_public = true`.
   - *Reason: Supplies realistic test fixtures for development and automated integration testing without manual entry.*

---

## 3. Verify Row Level Security (RLS)

1. Navigate to **Database** $\rightarrow$ **Tables**.
2. Verify that every table under `public` displays a green **RLS Enabled** badge:
   - `extensions`
   - `extension_snapshots`
   - `snapshot_permissions`
   - `permission_creep_records`
   - `ai_analyses`
3. Verify that `FORCE ROW LEVEL SECURITY` is enabled across all tables.
   - *Reason: Guarantees that even table owners or internal queries respect security policies.*

---

## 4. Supabase Authentication Settings

Navigate to **Authentication** $\rightarrow$ **Configuration** and apply the following settings:

| Setting | Value | Reason |
|---|---|---|
| **Enable Email Confirmations** | **ON** | Prevents account squatting and unverified email ingestion. |
| **Minimum Password Length** | **12 characters** | Protects user accounts against credential guessing and brute-force attacks. |
| **Leaked Password Protection** | **ON** (if plan supports) | Blocks commonly compromised passwords via HaveIBeenPwned database checks. |
| **External Providers** | **Disabled** (except approved) | Closes unused OAuth attack surfaces not implemented in Part 2c. |
| **JWT Expiry Limit** | **3600 seconds** (1 hour) | Limits the exposure window of compromised bearer tokens. |
| **Site URL** | `https://your-domain.com` (or `http://localhost:8000` for dev) | Restricts redirect origins for password resets and magic links. |

---

## 5. API Keys & Environment Configuration

Navigate to **Project Settings** $\rightarrow$ **API**:

- **Project URL (`SUPABASE_URL`)**:
  - Found under Project URL (e.g., `https://xyzproject.supabase.co`).
- **Publishable / Anon Key (`SUPABASE_PUBLISHABLE_KEY`)**:
  - The public-safe key used by the backend client or browser when scoped to public operations.
- **Secret / Service Role Key (`SUPABASE_SECRET_KEY`)**:
  - The privileged key that bypasses RLS.
  - *IMPORTANT: Keep this key strictly on the backend. Never include it in frontend code, git commits, or client-side assets.*
- **Project Reference (`AEGIS_TEST_PROJECT_REF`)**:
  - Found in the URL or project settings (e.g., `xyzproject`).
  - *Reason: Acts as a safety guard to ensure integration tests refuse to run against any database that is not explicitly designated as the test project.*

### Local `.env` Configuration File
Create a local `.env` file in the project root (never committed) with the following structure:

```env
ENVIRONMENT=development
SUPABASE_URL=https://<your-project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<your-anon-or-publishable-key>
SUPABASE_SECRET_KEY=<your-service-role-or-secret-key>
AEGIS_TEST_PROJECT_REF=<your-project-ref>
COOKIE_SECURE=false
AI_ENABLED=false
```
