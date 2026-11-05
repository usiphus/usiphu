# Supabase private Source Inbox storage

This change moves original Source Inbox files and extraction JSON out of the
Streamlit local filesystem when `USIPHU_FILE_STORAGE_BACKEND=supabase`. Source
metadata and object keys are stored in PostgreSQL in `source_documents`.

## Create the bucket manually

In Supabase Dashboard → Storage → New bucket:

- Name: `source-inbox` (or set `USIPHU_SUPABASE_STORAGE_BUCKET` to your chosen name)
- **Public bucket: OFF**
- Maximum file size: 50 MB
- Allowed MIME types: PDF, DOCX, MS Word, plain text, PNG and JPEG

Do not create a public bucket. The application uses server-side Storage API calls.
The secret key must never be sent to a browser.

## Apply database migration

Apply `migrations/0002_source_documents.sql` after
`migrations/0001_postgresql_schema.sql` to the private PostgreSQL database.
The migration enables RLS and denies the Supabase `anon` and `authenticated`
roles access to source metadata. The app uses its server-side PostgreSQL
connection. This migration creates metadata only; it does not import any
existing local files.

## Streamlit Community Cloud secrets

Add these values in the app's Secrets settings (not in GitHub or chat):

```toml
USIPHU_DATABASE_BACKEND = "postgres"
USIPHU_FILE_STORAGE_BACKEND = "supabase"
SUPABASE_DB_URL = "postgresql://..."
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_..."  # server-only; apikey header only
USIPHU_SUPABASE_STORAGE_BUCKET = "source-inbox"
```

A legacy `SUPABASE_SERVICE_ROLE_KEY` is also accepted. New `sb_secret_...`
keys are sent only in the `apikey` header (they are not JWTs); legacy
`service_role` JWTs also use the Bearer header. Never use an `anon` or
publishable key for this server-side adapter. Keep all credentials server-only.

## What is durable now

- Original uploaded file bytes: private Supabase Storage object
- Source catalogue, SHA-256 duplicate key and provenance metadata: PostgreSQL
- Extracted candidate JSON: private Supabase Storage object
- Candidate edits and review-state changes: written back to the extraction object

The local backend remains the default for development and existing tests. Do not
set the Supabase backend selectors in a live deployment until PR #15 and this
PR are reviewed, merged in order, and the migration is applied.

## Remaining gaps

- Promoted question-bank and assessment-bank JSON files still use the local
  repository data directory and must be migrated before cloud deployment.
- Existing local Source Inbox files/manifests/extractions are not imported by
  this change. A separate dry-run-first migration utility is required.
- Faculty review authorization remains enforced by the PostgreSQL-backed review
  repositories; Storage itself uses a privileged server-side key. The app must
  authorize each action before requesting any object operation.
- No actual Supabase project or bucket has been created by this PR. Validate
  with synthetic files first and complete a backup/restore drill.

## Security notes

Private buckets are required. Supabase private objects are accessed with an
authenticated request or a time-limited signed URL. Signed URLs cannot be
individually revoked before expiry; deleting or moving the object invalidates
the link. The adapter limits generated signed URLs to one hour.

References:
- https://supabase.com/docs/guides/storage/buckets/fundamentals
- https://supabase.com/docs/guides/storage/serving/downloads
- https://supabase.com/docs/reference/python/storage-from-upload
- https://supabase.com/docs/reference/python/storage-from-createsignedurl
