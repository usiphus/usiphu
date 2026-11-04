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
5. Start: `docker compose -f compose.production.yaml up -d --build`.
6. Verify `https://YOUR-DOMAIN/_stcore/health`, sign-in, sign-out, and learner isolation with two test identities.

Do not commit `.env` or `.streamlit/secrets.toml`. Use a host secret manager for production secrets where available. Keep the host and Docker engine patched.

## Backups

The backup job creates two coordinated artifacts:
- `usiphu-<timestamp>.sqlite3`: SQLite online backup, checked with `PRAGMA integrity_check`.
- `usiphu-sources-<timestamp>.tar.gz`: complete Source Inbox directory, including source PDFs/documents, manifest, extraction outputs and reviewer history, with a SHA-256 sidecar.

For a consistent database + Source Inbox point-in-time snapshot, briefly stop the app while the backup job runs (the SQLite online backup itself is safe while SQLite is open, but a coordinated snapshot across SQLite and uploaded files requires quiescing uploads/reviews):

```bash
docker compose -f compose.production.yaml stop app
docker compose -f compose.production.yaml run --rm backup
docker compose -f compose.production.yaml start app
```

Run this sequence from a protected host scheduler daily. The job retains the most recent 30 days of each artifact. Copy both database and source archive, plus the checksum sidecar, encrypted off-host. A local backup volume on the same host is not disaster recovery. Do not run the backup job without the stop/start wrapper if a coordinated point-in-time snapshot is required.

## Restore

Restore only during a maintenance window. Stop the app and proxy first. Select a matching timestamp for the database and source archive; verify the source archive checksum with `sha256sum -c usiphu-sources-<timestamp>.tar.gz.sha256`. Restore the SQLite file to the `usiphu-data` volume as `usiphu.sqlite3`. Extract the source archive into the `usiphu-sources` volume so that its contents are directly under `/source-inbox` (the archive's top-level folder is `source_inbox/`). Preserve the app container's ownership/permissions; the image runs as UID 10001. Restart the app and verify the Source Inbox list, source downloads, extraction records and learner data before reopening access. Never overwrite the live database or source files while the app is running.

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
