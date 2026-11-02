# Deployment and identity setup

## Local development

Install the project and run:

```bash
pip install -e ".[dev]"
streamlit run app/Home.py
```

Without OIDC configuration, the app uses the local learner namespace. This mode is intended for one learner on a trusted machine only.

## Enable accounts with OpenID Connect

Usiphu delegates sign-in to an OIDC provider (Google, Microsoft Entra ID, Okta, Auth0, or another standards-compliant provider). It does not store user passwords.

1. Register the app with your identity provider.
2. Set the redirect URI to `https://YOUR-DOMAIN/oauth2callback`.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
4. Set `redirect_uri`, a strong random `cookie_secret`, `client_id`, `client_secret`, and `server_metadata_url`.
5. Set `USIPHU_AUTH_REQUIRED=true`.
6. Ensure the identity provider emits a stable OIDC `sub` claim. Learner records are scoped by this subject, not by display name or email.
7. Keep secrets out of Git and backups; rotate credentials if exposed.

The example file is a template only. Never commit real credentials. Existing data from the original single-user database is migrated into the `local` namespace; it is not automatically assigned to an OIDC account. Export or migrate it deliberately after verifying the account identity.

## Docker Compose

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit the file with your provider's real credentials and production redirect URI.
docker compose up --build -d
docker compose logs -f usiphu
```

The compose service mounts a persistent named volume at `/data` and requires OIDC. Put the app behind a TLS-terminating reverse proxy; do not expose an unauthenticated Streamlit port directly to the public internet.

## Data and scale limits

- SQLite is suitable for a single-node pilot and is persisted in the named Docker volume.
- Learner records are isolated by OIDC subject in the application data layer.
- Before running multiple replicas or offering a multi-institution service, migrate storage to managed PostgreSQL, configure encrypted backups, retention/deletion policies, monitoring, and a documented incident-response process.
- The optional FastAPI endpoints currently expose curriculum and practice content only. They do not expose learner records.
- OIDC authenticates the learner; it does not by itself provide staff roles, institution-level authorization, or administrator permissions.

## Operational checks before production

- Configure HTTPS and trusted proxy headers.
- Restrict identity-provider redirect URIs and enable MFA where available.
- Set database volume permissions and backup/restore procedures.
- Pin dependencies and review automated vulnerability reports.
- Review privacy notices, data retention, deletion, and applicable local law.
- Have clinical educators validate learning content before it is used for assessment.
