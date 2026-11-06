# Learner and faculty data migration

The PostgreSQL migrations create the learner/faculty tables, but do not copy existing SQLite records. Use `scripts/migrate_learner_faculty_data.py` before enabling the hosted PostgreSQL backend.

## Scope and safeguards

The importer covers all 13 persistence tables in migrations 0001-0003. It preserves Auth0 issuer-qualified owner/reviewer IDs, review decisions, comments, timestamps, attestations, snapshots and explicit event IDs. It is dry-run by default. Apply mode creates a consistent SQLite backup plus SHA-256 checksum, refuses any non-empty destination table, requires identical column layouts, imports in one PostgreSQL transaction, verifies row counts and content hashes, and resets identity sequences. It never modifies the source database.

## Operator procedure

1. Stop the app and all writers. Do not migrate while learner or faculty activity continues.
2. Apply migrations 0001, 0002 and 0003 to the intended Supabase database.
3. Obtain the authoritative SQLite file from the operator-controlled host. Do not assume Streamlit Community Cloud's local filesystem is persistent or contains the authoritative database.
4. Keep the backup directory on encrypted, access-restricted storage and create a separately encrypted off-provider copy.
5. Set `SUPABASE_DB_URL` in your local shell (never in chat or GitHub). Use SSL. Supabase recommends the Shared Pooler session-mode endpoint for persistent clients on IPv4-only networks; direct connections are IPv6-only on Free projects. See [Supabase connection guidance](https://supabase.com/docs/guides/database/connecting-to-postgres).
6. Run a dry run:
   ```bash
   python scripts/migrate_learner_faculty_data.py --database /secure/path/usiphu_data.sqlite3 --backup-dir /secure/encrypted-backups
   ```
7. Confirm the per-table counts and that the target is the correct, empty project. Then apply:
   ```bash
   python scripts/migrate_learner_faculty_data.py --database /secure/path/usiphu_data.sqlite3 --backup-dir /secure/encrypted-backups --apply
   ```
8. Keep the backup and report. Run synthetic learner, admin, clinical-reviewer and exam-reviewer acceptance tests. Rehearse restore into a separate disposable database before cutover.

## Remaining operational limits

This importer migrates database rows only. `scripts/migrate_to_supabase.py` separately migrates Source Inbox objects, reviewed banks and report snapshots. The operator must locate and validate the authoritative SQLite file. A migration is not complete until a separate restore rehearsal succeeds. Do not load real patient-identifiable or regulated data without institutional privacy/security approval.
