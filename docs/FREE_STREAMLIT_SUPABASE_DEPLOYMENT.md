# $0 Streamlit + Supabase deployment plan

## Decision

Use Streamlit Community Cloud for the Streamlit runtime and Supabase Free for PostgreSQL plus private object storage. Keep Auth0 as the identity provider. Do not introduce Supabase Auth or change the existing issuer-qualified Auth0 subject model.

This is a $0 pilot target only, not an uptime-guaranteed or institutionally approved production environment.

## Repository status (2026-11-05)

- PR #14 adds a driver-neutral database seam while keeping SQLite as the default.
- PR #15 adds an opt-in PostgreSQL backend and the initial learner/faculty schema migration; its PostgreSQL integration workflow must be green before merging.
- PR #16 adds private Supabase Storage for Source Inbox originals and extraction JSON, plus PostgreSQL source metadata.
- The follow-up storage work adds durable document pointers for promoted banks and pilot reports, plus a dry-run-first importer; these changes remain unmerged until their stacked CI passes.
- These PRs are stacked, open and unmerged. No Supabase project, bucket, Streamlit app or deployment has been provisioned.
- Bank and pilot-report cloud persistence is implemented in the pending follow-up stack, but existing local files still require an operator-reviewed import. Backup/export and restore drills remain outstanding.

## Deployment blocker: incomplete cloud persistence

USIPHU is not cloud-persistence-ready today. The runtime still defaults to SQLite until explicitly configured; PR #15's PostgreSQL backend is opt-in. PR #16 moves original Source Inbox files and extraction candidate JSON to private Supabase Storage when enabled. The pending durable-document follow-up routes promoted banks and pilot validation reports through private Storage with PostgreSQL pointers; existing local files are not automatically migrated. Streamlit Community Cloud hibernates apps after 12 hours without traffic, and its local filesystem must not be treated as durable storage.

**Do not deploy with real learner, faculty, patient, or examination-source data until every persistent path is migrated, the current-head CI passes, and the restore drill succeeds.** Supabase credentials alone do not migrate SQLite or make local uploads durable.

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

For a persistent Streamlit server, use Supabase shared pooler session mode when the host network is IPv4-only. Require TLS and use a restricted database login, not the dashboard owner account.

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

Implement and test a PostgreSQL backend for every SQLite-backed path:
- flashcards, generated drafts, review states/events, question attempts and topic progress;
- faculty question decisions, immutable snapshots, reviewer roles and role audit events;
- shared assessment review queue, decisions and history.

Preserve the existing authorization invariants: issuer-qualified Auth0 identity; admin-only role assignment; clinical approval before exam validation; distinct identities for clinical and exam decisions; server-side authorization; immutable review snapshots; approval invalidation after edits; and no direct promotion of unreviewed drafts.

Use versioned SQL migrations, parameterized SQL, explicit transactions, foreign keys, check constraints, indexes, least-privilege database roles and PostgreSQL integration tests for every persistence method. SQLite-only tests are not sufficient.

### 2. Durable Source Inbox migration

PR #16 implements private-bucket storage for original file bytes and extraction candidate JSON, plus PostgreSQL source metadata (including SHA-256 duplicate detection and uploader provenance). The pending follow-ups implement durable storage for promoted/reviewed question-bank and assessment-bank JSON and pilot-validation reports, plus dry-run-first importers for banks/reports and legacy Source Inbox originals/manifests/extractions. These imports are operator-run and have not been executed. Upload/download/restore must still be verified against a real private bucket. Preserve original filename, opaque object key, upload time, title, specialty, exam year, notes, status and page provenance.

Do not create a public bucket or store file bytes as base64 in Postgres. Validate extension and size server-side. Check the caller's application role before upload, download, replacement or deletion.

### 3. Auth0 and Streamlit configuration

PR #10 adds a Streamlit Secrets-to-environment bridge for existing application settings. Keep that staging-readiness work in its own PR stack and merge it only after its own CI/review. Configure Streamlit Community Cloud secrets only after the PostgreSQL and Storage migrations are merged.

At deployment time:
1. Create the app from `usiphus/usiphu`, branch `main`, entrypoint `app/Home.py`.
2. Choose a supported Python version compatible with `pyproject.toml`.
3. Add the existing Auth0 OIDC configuration in Community Cloud Secrets.
4. Add the Supabase PostgreSQL connection string and private Storage server credential in Secrets.
5. Add the actual `https://<app-subdomain>.streamlit.app/oauth2callback` callback URL to Auth0 Allowed Callback URLs and the app base URL to Allowed Logout URLs.
6. Confirm `USIPHU_AUTH_REQUIRED=true`.
7. Verify learner, admin, clinical reviewer and exam reviewer behavior using separate synthetic accounts.

Never commit credentials, tokens, connection strings or private keys. Never paste them into GitHub issues, PRs or chat.

### 4. Backup and recovery

Supabase Free does not include automatic daily backups. Before storing non-disposable data, implement scheduled PostgreSQL logical exports, private Storage object exports, encrypted off-provider copies, checksums, and periodic restore into a separate disposable PostgreSQL project or local instance. Measure recovery point and recovery time. A backup is not successful until database rows and sample source objects have been restored and verified.

## Acceptance gates

- [ ] PostgreSQL replaces every production SQLite persistence path.
- [ ] Mutable tables have reviewed migrations, constraints and indexes.
- [ ] Authorization tests prove learner isolation and faculty stage separation against PostgreSQL.
- [ ] Source Inbox uses private Storage and database-backed metadata.
- [ ] Promoted question and assessment banks and pilot reports use private Storage and PostgreSQL pointers.
- [ ] Existing local banks/reports are imported with reviewed checksums and backups.
- [ ] Existing local Source Inbox originals, manifests and extraction candidates are imported with preserved IDs/provenance and backups.
- [ ] Upload, download, duplicate detection, extraction and restore tests pass.
- [ ] Existing SQLite data has a tested, non-destructive export/import path if needed.
- [ ] CI includes PostgreSQL integration tests.
- [ ] Auth0 login/logout and callback work on the actual Streamlit URL.
- [ ] Separate learner/admin/clinical/exam identities pass positive and negative authorization tests.
- [ ] Backup export and restore drill passes.
- [ ] Free-tier quotas, hibernation, pause behavior and operator responsibilities are accepted.
- [ ] Only synthetic data is used until institutional privacy/security approval is obtained.

## Backup and recovery

The pending encrypted backup/restore tooling is documented in [BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md). It requires operator-installed PostgreSQL client tools and age, off-provider retention, and a restore drill in a separate disposable Supabase project. Code availability does not count as a passed restore drill.

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