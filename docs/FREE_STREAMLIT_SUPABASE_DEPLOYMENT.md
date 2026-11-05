# $0 Streamlit + Supabase deployment plan

## Decision

Use Streamlit Community Cloud for the Streamlit runtime and Supabase Free for PostgreSQL plus private object storage. Keep Auth0 as the identity provider. Do not introduce Supabase Auth or change the existing issuer-qualified Auth0 subject model.

This is a $0 pilot target only, not an uptime-guaranteed or institutionally approved production environment.

## Implemented in the hosted-backend branch

The current implementation adds:
- a psycopg 3 PostgreSQL connection adapter while retaining SQLite for local development;
- a versioned migration for learner progress, generated drafts, faculty roles/audit events, two-stage assessment review, source metadata/extractions, and approved draft banks;
- private Supabase Storage upload/download for original Source Inbox files, with SHA-256 duplicate detection;
- PostgreSQL-backed source metadata and extraction JSON;
- PostgreSQL-backed persistence for extracted question and written-assessment draft-bank additions;
- Streamlit Secrets bridging for the database URL and server-side Storage credentials.

This is a first implementation pass, not yet a verified release. The code has not yet been exercised against a live Supabase project, and CI/PostgreSQL integration tests and backup/restore acceptance are still required.

**Do not deploy with real learner, faculty, patient, or examination-source data until CI, PostgreSQL integration, Auth0 authorization, private Storage tests, and a restore drill pass.** Supabase credentials alone are not a substitute for applying the migration and configuring the app role.

## Target architecture

```text
Learner/faculty browser --HTTPS--> Streamlit Community Cloud
                                      | Auth0 OIDC; server-side role checks
                                      | TLS PostgreSQL connection
                                      v
                               Supabase Free Postgres
                                      |
                                      +-- learner practice/progress
                                      +-- generated drafts
                                      +-- faculty roles and audit events
                                      +-- assessment review queue and history
                                      +-- source metadata and provenance
                                      |
                                      +-- private Supabase Storage bucket
                                           original source files
```

Keep Auth0 issuer-qualified subject identity as the stable application identity. Store roles in the database and enforce review rules server-side. Never trust user-editable profile metadata for authorization. Keep all database and Storage credentials server-side in Streamlit Secrets; never send them to the browser.

For Streamlit's persistent server process, use Supabase's shared pooler **session mode** (port 5432) if the hosting network is IPv4-only. Do not use transaction mode for this long-running DB-API connection. Require TLS. The migration creates a non-superuser `usiphu_app` role with only application-table privileges and `BYPASSRLS` because Auth0 is the identity provider and the app performs authorization server-side. Enable LOGIN and set its password from a trusted local `psql` session (use the interactive `\\password usiphu_app` command); do not put a password in a committed SQL file.

## Free-tier budget and limits

| Component | Free allowance / behavior | USIPHU implication |
|---|---|---|
| Streamlit Community Cloud | $0; hibernates after 12 hours without traffic | Cold wake-up; no uptime SLA |
| Supabase Free Postgres | 500 MB per project | Keep static curriculum/question banks in Git; mutable state in Postgres |
| Supabase Free Storage | 1 GB | Strict upload size and retention limits |
| Supabase Free egress | 5 GB uncached + 5 GB cached | Avoid repeatedly serving large files |
| Supabase inactivity | May pause after 7 days of low database activity | Manual resume; not always-on |
| Supabase backups | No automatic daily backups on Free | Operator-managed exports and restore drills |

Free-tier terms can change. No paid add-ons, custom domains, IPv4 add-ons, or over-quota usage are assumed. The $0 target holds only while usage stays within the published free allowances.

## Repository work required before first deployment

### 1. PostgreSQL persistence migration

The hosted connection layer now routes the existing learner storage functions, faculty review decisions/roles/audit events, and shared assessment review queue to Postgres. It retains SQLite when `USIPHU_DATABASE_URL` is absent, so local development and existing SQLite tests remain available.

Apply `supabase/migrations/20261105000100_initial_hosted_schema.sql` before enabling Postgres mode. It creates the application tables, indexes, constraints, RLS, the private Storage bucket, and the `usiphu_app` database role. After applying the migration, set the role password interactively from a trusted local `psql` connection and use that role in the app connection string.

The database adapter translates the SQLite placeholder and `INSERT OR IGNORE` patterns used by current modules. This compatibility layer needs full PostgreSQL integration coverage before it is treated as production-grade. The migration utility `scripts/migrate_sqlite_to_supabase.py` supports a non-destructive dry run by default and writes only when passed `--apply`; it never deletes the local SQLite database or source files.

Authorization invariants remain in the service layer: issuer-qualified Auth0 identity; admin-only role assignment; clinical approval before exam validation; distinct identities for clinical and exam decisions; server-side authorization; immutable review snapshots; approval invalidation after edits; and no direct promotion of unreviewed drafts.

### 2. Durable Source Inbox

The hosted path now stores original source bytes in the private `usiphu-source-inbox` bucket, source metadata in `source_documents`, and extraction JSON in `source_extractions`. The app reads originals through the server-side Storage API and retains filename, object key, SHA-256, upload time, title, specialty, exam year, notes, status, and page provenance.

The bucket is private and accessed only with the server-side Storage credential. File type and 50 MB size are validated before upload. The original content is never stored as base64 in Postgres. The app must continue to enforce Auth0 application permissions on every Source Inbox action.

### 3. Auth0 and Streamlit configuration

PR #10 adds a Streamlit Secrets-to-environment bridge for existing application settings. Keep that staging-readiness work in its own PR stack and merge it only after its own CI/review. Configure Streamlit Community Cloud secrets only after the PostgreSQL and Storage migrations are merged.

After the code and CI gates pass, configure these secrets in Community Cloud (values below are placeholders; never commit real values):

```toml
USIPHU_AUTH_REQUIRED = "true"
USIPHU_DATABASE_URL = "postgresql://usiphu_app.<PROJECT_REF>:<PASSWORD>@aws-<REGION>.pooler.supabase.com:5432/postgres?sslmode=require"
SUPABASE_URL = "https://<PROJECT_REF>.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "<server-side legacy service_role key>"
USIPHU_STORAGE_BUCKET = "usiphu-source-inbox"
USIPHU_ADMIN_SUBJECTS = "https://<AUTH0_DOMAIN>/:<AUTH0_ADMIN_SUBJECT>"

[auth]
redirect_uri = "https://<APP-SUBDOMAIN>.streamlit.app/oauth2callback"
cookie_secret = "<long-random-secret>"
client_id = "<AUTH0_CLIENT_ID>"
client_secret = "<AUTH0_CLIENT_SECRET>"
server_metadata_url = "https://<AUTH0_DOMAIN>/.well-known/openid-configuration"
```

Deployment sequence:
1. Back up the local SQLite database and Source Inbox directory before migrating.
2. Create the Supabase Free project; keep it on the free plan.
3. Apply the migration in `supabase/migrations` using the Supabase CLI linked to that project.
4. Enable LOGIN and set a password for `usiphu_app` interactively from trusted local `psql`; use its pooler session-mode connection string for `USIPHU_DATABASE_URL`.
5. Run `python scripts/migrate_sqlite_to_supabase.py` first to inspect the non-destructive migration report, then rerun with `--apply` only after checking the report and confirming the target project is correct.
4. Copy the project URL and server-side `service_role` key into Community Cloud Secrets. The Storage key is highly privileged and must never be exposed in browser code or logs.
5. Create the Streamlit app from the feature branch only after PRs are merged in order, entrypoint `app/Home.py`.
6. Add the actual `https://<app-subdomain>.streamlit.app/oauth2callback` callback URL to Auth0 Allowed Callback URLs and the app base URL to Allowed Logout URLs.
7. Confirm `USIPHU_AUTH_REQUIRED=true`.
8. Verify learner, admin, clinical reviewer and exam reviewer behavior using separate synthetic accounts.

Never commit credentials, tokens, connection strings or private keys. Never paste them into GitHub issues, PRs or chat.

### 4. Backup and recovery

Supabase Free does not include automatic daily backups. Before storing non-disposable data, implement scheduled PostgreSQL logical exports, private Storage object exports, encrypted off-provider copies, checksums, and periodic restore into a separate disposable PostgreSQL project or local instance. Measure recovery point and recovery time. A backup is not successful until database rows and sample source objects have been restored and verified.

## Acceptance gates

- [ ] Every mutable learner/faculty/source workflow has PostgreSQL integration coverage.
- [ ] The migration applies cleanly to a fresh Supabase Free project.
- [ ] The Auth0-backed database role has only required table privileges and no superuser rights.
- [ ] Authorization tests prove learner isolation and faculty stage separation against PostgreSQL.
- [ ] Source Inbox private upload/download, duplicate detection, extraction and review updates pass against Supabase.
- [ ] Source upload rollback and metadata/file consistency are verified.
- [ ] Existing SQLite data has a tested, non-destructive export/import path if needed.
- [ ] CI includes PostgreSQL integration tests.
- [ ] Auth0 login/logout and callback work on the actual Streamlit URL.
- [ ] Separate learner/admin/clinical/exam identities pass positive and negative authorization tests.
- [ ] Backup export and restore drill passes.
- [ ] Free-tier quotas, hibernation, pause behavior and operator responsibilities are accepted.
- [ ] Only synthetic data is used until institutional privacy/security approval is obtained.

## Manual deployment checklist (after code gates pass)

1. Create a Supabase Free project; do not enable paid add-ons.
2. Apply the repository's reviewed migrations.
3. Create the private Storage bucket and reviewed access policies.
4. Create a least-privilege database login.
5. Configure Streamlit Community Cloud from GitHub.
6. Enter secrets directly in the Community Cloud settings UI.
7. Add the actual Streamlit callback/logout URLs to Auth0.
8. Run the acceptance checklist using synthetic data.
9. Run and verify the first independent backup.
10. Share the URL only with intended pilot testers.

## Provider documentation

- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)
- [Streamlit Community Cloud secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
- [Streamlit Community Cloud hibernation](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app#app-hibernation)
- [Supabase Free pricing and quotas](https://supabase.com/pricing)
- [Supabase connection methods](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control)
- [Supabase Free project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)
- [Supabase Free-plan backup guidance](https://supabase.com/docs/guides/platform/backups)