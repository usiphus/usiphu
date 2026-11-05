# Database backend architecture

USIPHU supports SQLite for local development and PostgreSQL for managed hosting.
The application remains on SQLite unless `USIPHU_DATABASE_BACKEND=postgres` is
explicitly configured. PostgreSQL connections require `SUPABASE_DB_URL` (preferred)
or `DATABASE_URL`, supplied through the hosting provider's secret manager.

## PostgreSQL connection requirements

- Use a Supabase PostgreSQL connection string; for Streamlit Community Cloud, use
  the Supabase pooler connection string if direct IPv6 connectivity is unavailable.
- The driver requires TLS (`sslmode=require`) and disables client-side prepared
  statements for compatibility with transaction-mode poolers.
- Keep database credentials server-side. Never use a service-role key as a
  substitute for the database password, and never commit connection strings.
- Keep the Supabase database schema private. The app connects directly to Postgres;
  it does not need to expose these tables through the Supabase Data API.
- PostgreSQL is not enabled merely by adding a URL: set both the backend selector
  and the connection secret intentionally after applying the schema migration.

## SQL compatibility

The adapter translates qmark placeholders to psycopg placeholders and executes
the existing plain DDL scripts statement-by-statement. It also preserves both
mapping-style row access (`row["field"]`) and legacy positional access
(`row[0]`). The repository schema uses identity columns in PostgreSQL in place
of SQLite's `AUTOINCREMENT`. SQL constructs that are not portable must be
rewritten explicitly; do not add SQLite-only pragmas or `INSERT OR IGNORE`.

## Schema migration

Apply `migrations/0001_postgresql_schema.sql` once to an empty PostgreSQL
database before enabling the backend. It creates all 13 learner and faculty
persistence tables and their indexes. The repositories also retain idempotent
`CREATE TABLE IF NOT EXISTS` setup for local SQLite use. The migration is
intended for a fresh PostgreSQL schema; it is not a data migration.

## Remaining work before production use

- Add a reviewed SQLite-to-PostgreSQL import utility with dry-run default,
  explicit apply, row-count and checksum verification.
- Move Source Inbox originals, manifests, extraction JSON and derived files to a
  private Supabase Storage bucket with stable object IDs and authorization.
- Test PostgreSQL integration against an actual disposable PostgreSQL service,
  including learner isolation, faculty role checks, clinical-before-exam ordering,
  two-person separation, audit history and snapshot invalidation.
- Exercise backup/restore and recovery. Supabase Free is a staging tier, not a
  production availability guarantee.

Do not switch a live deployment to PostgreSQL until the schema migration and
integration suite have passed. Keep synthetic data only until privacy, security,
institutional approval and recovery gates are signed off.
