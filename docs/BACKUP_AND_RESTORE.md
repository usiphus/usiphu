# Encrypted Supabase backup and restore

USIPHU’s free-tier deployment must not depend on provider-managed backups. These commands create a locally staged, encrypted archive containing a PostgreSQL custom-format dump and every object in the configured private Storage bucket.

## Requirements

- PostgreSQL client tools (pg_dump and pg_restore)
- age for client-side encryption
- A private Supabase Storage bucket
- Server-side Supabase URL, database URL and secret key in the operator’s environment
- An age public recipient for backup, and its matching private identity stored offline

Generate an age key pair on a trusted operator device:

```bash
age-keygen -o ~/.config/usiphu/backup-identity.txt
```

Keep the identity file offline and protected. Use only the public recipient printed by age-keygen for backup jobs. Never commit either key to GitHub or place it in Streamlit Secrets.

## Create an encrypted backup

Set these environment values in a protected operator shell (never paste credentials into chat or commit them):

- USIPHU_DATABASE_BACKEND=postgres
- USIPHU_FILE_STORAGE_BACKEND=supabase
- SUPABASE_DB_URL
- SUPABASE_URL
- SUPABASE_SECRET_KEY (or the legacy server-only service-role JWT)
- USIPHU_SUPABASE_STORAGE_BUCKET

Run:

```bash
python scripts/backup_supabase.py \\
  --age-recipient "age1..." \\
  --output-dir /secure/off-provider-backups/usiphu
```

The script runs pg_dump, recursively lists and downloads private Storage objects, records object and database-dump SHA-256 checksums, creates a tar.gz archive in a temporary directory and encrypts it with age. Temporary plaintext staging is removed when the command exits. Copy the resulting .age file to a separate off-provider location. The backup command does not delete old backups; apply a retention policy to the encrypted copies.

## Restore drill

Restore only into a separate disposable Supabase project/database with a private bucket created in advance. Configure the environment variables above for the target project and bucket. The restore command drops/replaces objects in the target database, so it requires explicit confirmation:

```bash
python scripts/restore_supabase.py \\
  --backup /secure/off-provider-backups/usiphu/usiphu-backup-YYYYMMDDTHHMMSSZ.tar.gz.age \\
  --age-identity ~/.config/usiphu/backup-identity.txt \\
  --confirm-overwrite
```

Restore decrypts the archive into a temporary directory, rejects unsafe archive paths and links, verifies every checksum, uploads and re-download-verifies all objects, then runs pg_restore --clean --if-exists against the target database. Do not point this command at the live pilot database during a test. A restore is successful only after the operator verifies learner records, faculty roles and audit history, source metadata, extraction objects, promoted banks and pilot reports in the restored project.

## Operational acceptance

- [ ] Encrypted backup completes and its output is copied off-provider.
- [ ] Restore completes in a separate disposable Supabase project.
- [ ] Sample source originals and extraction JSON download and checksum-match.
- [ ] Learner data, faculty roles, two-person decisions and audit events are present.
- [ ] Promoted question/assessment banks and pilot reports are present.
- [ ] Auth0 sign-in and role checks pass against the restored staging app.
- [ ] Record recovery time and the age of the newest recoverable backup.
- [ ] Repeat the drill periodically and after schema or Storage layout changes.

This is an operator-run backup tool, not a managed scheduled service. Streamlit Community Cloud does not schedule the job, and this repository does not upload encrypted archives to a third-party backup provider. The operator must schedule, retain and monitor off-provider copies. A code-level test is not a completed restore drill.
