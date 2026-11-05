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

Apply migrations in order: `0001_postgresql_schema.sql`, `0002_source_documents.sql`, then `0003_app_documents.sql` to the private PostgreSQL database.
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
- Candidate edits, AI review history and review-state changes: written back to the extraction object
- Promoted MCQ and written-assessment bank JSON: private Storage objects referenced by PostgreSQL `app_documents`
- Pilot validation latest report and timestamped snapshots: private Storage objects referenced by PostgreSQL `app_documents`

The local backend remains the default for development and existing tests. Do not
set the Supabase backend selectors in a live deployment until PR #15 and this
PR are reviewed, merged in order, and the migration is applied.

## Remaining gaps

- The durable bank/report adapter and `scripts/migrate_durable_documents.py` provide a dry-run-first import. Existing local bank/report files are not uploaded automatically; run and review the dry run, then apply with a backup directory.
- Existing local Source Inbox originals/manifests/extractions are not imported by this change. The existing Source Inbox migration helper is a local directory copy, not a Supabase import; remote import and verification remain outstanding.
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


## Import existing promoted banks and pilot reports

After applying migration `0003_app_documents.sql`, set the server-side Supabase environment in a protected operator shell or deployment environment. First inspect the dry-run inventory:

```bash
python scripts/migrate_durable_documents.py --data-root data --report /tmp/usiphu-document-dry-run.json
```

The default mode is non-destructive and does not contact the remote database. Review every listed key, file size and checksum. Then create a protected backup directory and explicitly apply:

```bash
python scripts/migrate_durable_documents.py --data-root data --apply \
  --backup-dir /secure/backups/usiphu-documents-YYYYMMDD \
  --report /secure/backups/usiphu-document-import-report.json
```

The importer refuses to replace differing remote documents unless `--replace-existing` is explicitly supplied. It keeps source files unchanged, backs them up before writing, and verifies the canonical JSON checksum after each import. A failed run may have completed earlier documents; inspect its report and resume only after reconciling those keys. This is not a substitute for a full database plus Storage backup/restore drill.


## Import an existing local Source Inbox

The `scripts/migrate_source_inbox_to_supabase.py` command preserves legacy source IDs, uploader provenance, original timestamps, metadata and extraction candidate IDs. It validates manifest SHA-256 values and does not delete or rewrite the local source directory.

Start with a dry run:

```bash
python scripts/migrate_source_inbox_to_supabase.py --source-dir data/source_inbox --report /tmp/usiphu-source-import-dry-run.json
```

After reviewing the inventory and confirming a protected backup location, apply explicitly:

```bash
python scripts/migrate_source_inbox_to_supabase.py --source-dir data/source_inbox --apply \\
  --backup-dir /secure/backups/usiphu-source-inbox-YYYYMMDD \\
  --report /secure/backups/usiphu-source-import-report.json
```

If an existing remote extraction differs from the local snapshot, the importer refuses to overwrite it unless `--replace-existing` is supplied. Review that difference first: remote reviewer edits may be newer than the local copy. The import is resumable by source ID and checksum; inspect the report after any partial failure. Keep the local originals and backups until a separate restore drill verifies both PostgreSQL metadata and Storage objects.
