# Production deployment (single-node pilot)

This deployment hardens the existing Streamlit + SQLite application for a **single application replica** behind Caddy-managed HTTPS. It is suitable as a controlled initial deployment once real OIDC credentials, domain/DNS, backups, and institutional approval are configured. It is not a horizontally scalable multi-tenant platform.

## Architecture

- Caddy reverse proxy: public ports 80/443, automatic TLS, websocket proxying to Streamlit.
- Usiphu app: private Docker network only; non-root image from Dockerfile; OIDC required.
- SQLite: persistent named volume at `/data`, one writer/application replica.
- Source Inbox: separate persistent named volume at `/source-inbox`, configured by `USIPHU_SOURCE_DIR`. It contains uploaded originals, `sources.json`, extraction JSON and review history.
- Backups: verified SQLite online backup plus a compressed archive of the complete Source Inbox, written to a separate named volume.

## Deploy

1. Point the chosen domain's DNS A/AAAA records to the host.
2. Copy `.env.production.example` to `.env` and set `USIPHU_DOMAIN`, `ACME_EMAIL` and `TZ`. Keep `USIPHU_SOURCE_DIR=/source-inbox` aligned with the Compose mount.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`; configure a real OIDC provider, strong cookie secret, and redirect URI `https://YOUR-DOMAIN/oauth2callback`.
4. Register the same exact redirect URI with the identity provider; enable MFA and restrict allowed users/groups where supported.
5. Validate configuration: `USIPHU_DOMAIN=learn.example.org ACME_EMAIL=admin@example.org docker compose -f compose.production.yaml config --quiet`.
6. Start: `docker compose -f compose.production.yaml up -d --build`.
7. Verify `https://YOUR-DOMAIN/_stcore/health`, sign-in, sign-out, and learner isolation with two test identities.

Do not commit `.env` or `.streamlit/secrets.toml`. Use a host secret manager for production secrets where available. Keep the host and Docker engine patched.

## Migrate an existing Source Inbox

The old default location inside the application container is `/app/data/source_inbox`; the new persistent volume is `/source-inbox`. **Do not remove the old container or its image until migration and verification are complete.** The migration utility copies rather than deletes the old files, verifies SHA-256 for every file, can be rerun safely, and refuses conflicting destination files or symlinks.

Perform this before switching the existing installation to the new Compose configuration:

```bash
# Stop writes and retain the old container for the copy operation.
docker compose stop app
OLD_CONTAINER=$(docker compose ps -aq app | head -n 1)
mkdir -p migration-source-inbox
docker cp "$OLD_CONTAINER:/app/data/source_inbox/." migration-source-inbox/

# Start a one-off container using the new image and the new persistent volume.
docker compose -f compose.production.yaml build app
docker compose -f compose.production.yaml run --rm --no-deps \
  -v "$PWD/migration-source-inbox:/migration-source:ro" app \
  python /app/scripts/migrate_source_inbox.py \
  --source /migration-source --destination /source-inbox

# Only after the copy report and app-level verification, start the new app.
docker compose -f compose.production.yaml up -d app
```

If the old container has no `/app/data/source_inbox` directory, there may be no legacy files to migrate; verify this on the retained container before skipping. Keep `migration-source-inbox/` and the old container until the restored Source Inbox list, original paper downloads, extraction JSON and review history have been checked. The migration utility never deletes the source copy.

## Backups

The backup job creates two coordinated artifacts:
- `usiphu-<timestamp>.sqlite3`: SQLite online backup, checked with `PRAGMA integrity_check`.
- `usiphu-sources-<timestamp>.tar.gz`: complete Source Inbox directory, including source PDFs/documents, manifest, extraction outputs and reviewer history, with a SHA-256 sidecar.

For a consistent database + Source Inbox point-in-time snapshot, briefly stop the app while the backup job runs (the SQLite online backup itself is safe while SQLite is open, but a coordinated snapshot across SQLite and uploaded files requires quiescing uploads/reviews):

```bash
set -e
docker compose -f compose.production.yaml stop app
trap 'docker compose -f compose.production.yaml start app' EXIT
docker compose -f compose.production.yaml run --rm backup
docker compose -f compose.production.yaml start app
trap - EXIT
```

Run this sequence from a protected host scheduler daily. The job retains the most recent 30 days of each artifact. Copy both database and source archive, plus the checksum sidecar, encrypted off-host. A local backup volume on the same host is not disaster recovery. Do not run the backup job without the stop/start wrapper if a coordinated point-in-time snapshot is required.

## Perform a real restore drill

A successful backup is not proof of recoverability. Test restoration into a **new, separate host directory**, never into live volumes:

```bash
STAMP=YYYYMMDDTHHMMSSZ  # Use the same timestamp for all three artifacts.
mkdir -p restore-drill
docker compose -f compose.production.yaml run --rm --no-deps \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/restore-drill:/restore" \
  --entrypoint python backup \
  /scripts/restore_backup.py \
  --database-backup "/backups/usiphu-$STAMP.sqlite3" \
  --source-archive "/backups/usiphu-sources-$STAMP.tar.gz" \
  --checksum "/backups/usiphu-sources-$STAMP.tar.gz.sha256" \
  --database-target /restore/usiphu.sqlite3 \
  --source-target /restore/source-inbox

python -c "import sqlite3; c=sqlite3.connect('restore-drill/usiphu.sqlite3'); print(c.execute('PRAGMA integrity_check').fetchone()[0])"
test -f restore-drill/source-inbox/sources.json
find restore-drill/source-inbox -type f -maxdepth 3 -print
```

The restore utility verifies the SQLite integrity, verifies the archive SHA-256, rejects path traversal and symlink archive entries, and refuses to overwrite a database or non-empty Source Inbox target. Confirm that the restored manifest references existing original files, inspect representative extracted candidate JSON and review history, and open representative PDFs. Record the drill date, artifact timestamp, result and restore duration. Delete the local drill copy securely after review. Never use the live `restore` profile service against populated volumes; it is intended only for a deliberately empty target.

## Staging deployment checklist

Use a separate checkout/working directory with its own `.env`, `.streamlit/secrets.toml`, staging OIDC client and staging domain. Use a unique Compose project name so staging receives separate named volumes and does not share production data:

```bash
USIPHU_DOMAIN=staging.example.org ACME_EMAIL=ops@example.org \
  docker compose -p usiphu-staging -f compose.production.yaml config --quiet
USIPHU_DOMAIN=staging.example.org ACME_EMAIL=ops@example.org \
  docker compose -p usiphu-staging -f compose.production.yaml up -d --build
```

Before inviting pilot users, verify:
- HTTPS, certificate renewal, OIDC login/logout, MFA and authorized-user restrictions.
- Two test learners cannot see each other's attempts, flashcards or progress.
- Upload, download, extraction, transcription correction, answer-key review and approval work end to end.
- Backup succeeds while the app is stopped; restore drill succeeds into the isolated host directory above.
- Disk capacity, restart behavior, logs, access controls and off-host encrypted backup copy are monitored.

Use synthetic or de-identified test material only in staging. Do not use patient-identifiable information or real learner records until institutional privacy, retention and access approvals are complete. Staging instructions do not deploy anything automatically.

## Operational controls

- One app replica only while using SQLite. Do not scale the service horizontally or mount the same SQLite file across hosts.
- Restrict host firewall to 80/443 and administrative SSH from trusted IPs. The app port is not published.
- Enable host-level disk, CPU, memory, certificate-expiry, and container-restart monitoring.
- Set log retention/rotation at the host/container runtime; avoid logging patient-identifiable data.
- Define privacy notice, lawful basis, retention/deletion, incident response, access review, and backup retention before real learner data is collected.
- Run dependency/security scanning and a restore drill before launch.
- Clinical content must be reviewed by qualified educators; infrastructure readiness does not confer clinical validation.

## Multi-replica / institutional scale

The current learner storage module is SQLite-specific. PostgreSQL is **not yet wired into the application data layer**. Before multi-replica deployment, implement and test a PostgreSQL storage adapter/migrations, use managed PostgreSQL with TLS and least-privilege credentials, add schema migration automation, connection pooling, encrypted backups/PITR, and test concurrent learner writes. Do not merely add a PostgreSQL container and assume the application is using it.
