# Production deployment (single-node pilot)

This deployment hardens the existing Streamlit + SQLite application for a **single application replica** behind Caddy-managed HTTPS. It is suitable as a controlled initial deployment once real OIDC credentials, domain/DNS, backups, and institutional approval are configured. It is not a horizontally scalable multi-tenant platform.

## Architecture

- Caddy reverse proxy: public ports 80/443, automatic TLS, websocket proxying to Streamlit.
- Usiphu app: private Docker network only; non-root image from Dockerfile; OIDC required.
- SQLite: persistent named volume, one writer/application replica.
- Backups: consistent SQLite online backup to a separate named volume using Python's SQLite backup API.

## Deploy

1. Point the chosen domain's DNS A/AAAA records to the host.
2. Copy `.env.production.example` to `.env` and set `USIPHU_DOMAIN` and `TZ`.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`; configure a real OIDC provider, strong cookie secret, and redirect URI `https://YOUR-DOMAIN/oauth2callback`.
4. Register the same exact redirect URI with the identity provider; enable MFA and restrict allowed users/groups where supported.
5. Start: `docker compose -f compose.production.yaml up -d --build`.
6. Verify `https://YOUR-DOMAIN/_stcore/health`, sign-in, sign-out, and learner isolation with two test identities.

Do not commit `.env` or `.streamlit/secrets.toml`. Use a host secret manager for production secrets where available. Keep the host and Docker engine patched.

## Backups and restore

Run a manual consistent backup:

```bash
docker compose -f compose.production.yaml run --rm backup
```

Backups are written to the `usiphu-backups` volume; the script retains the most recent 30 daily files. Configure the host scheduler (cron/systemd timer or platform scheduler) to run the command daily, and copy encrypted backups off-host. Periodically test restore into a separate staging volume. A local backup volume on the same host is not disaster recovery.

Restore procedure (maintenance window): stop the app, copy a selected backup to the data volume as `usiphu.sqlite3`, verify ownership/permissions, then restart. Never overwrite the live database while the app is running.

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
