# Google sign-in setup for USIPHU

Use Google as the default OpenID Connect (OIDC) provider. Google authenticates accounts; USIPHU separately authorizes faculty reviewers.

**Signing in does not make someone a faculty reviewer.** The pilot owner must verify each person's faculty role and add only approved identities to the reviewer allowlist. Until then, the app remains preview-only.

## Create a Google OAuth client

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. Open Google Auth Platform and configure branding and audience. For a Workspace institution, consider an internal audience. Otherwise use an external audience and keep the app in Testing during the pilot; add only intended faculty accounts as test users.
3. Open Clients, choose Create client, and select Web application.
4. Add this authorized redirect URI for local development: `http://localhost:8501/oauth2callback`.
5. For a hosted app, add the exact public callback URI: `https://YOUR-REAL-HOSTNAME/oauth2callback`.
6. Create the client and copy its Client ID and Client secret. Keep both private.

The public Google OIDC discovery URL is already included in the example configuration: `https://accounts.google.com/.well-known/openid-configuration`.

## Configure USIPHU locally

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`. The latter is ignored by Git. Set these values, replacing the placeholders:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "PASTE_A_LONG_RANDOM_SECRET_HERE"
client_id = "PASTE_GOOGLE_CLIENT_ID_HERE"
client_secret = "PASTE_GOOGLE_CLIENT_SECRET_HERE"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

Generate a strong cookie secret locally with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Never commit `secrets.toml` or share the OAuth client secret in chat, screenshots, or issue comments.

## Start authenticated preview

Set `USIPHU_AUTH_REQUIRED=true` before starting Streamlit.

Windows PowerShell:

```powershell
$env:USIPHU_AUTH_REQUIRED="true"
streamlit run app/Home.py
```

macOS / Linux:

```bash
USIPHU_AUTH_REQUIRED=true streamlit run app/Home.py
```

Sign in using **Continue with Google**. During testing, Google may show a testing/unverified warning; only accounts added as test users can sign in.

The app sidebar displays the signed-in account's exact `issuer:sub` identity. Each proposed reviewer can copy their own identity and share it with the pilot administrator through an appropriate secure channel.

## Authorize two independent reviewers

1. Have each proposed reviewer sign in with their own Google account.
2. Independently verify their faculty appointment, specialty/role and authority.
3. Collect each exact sidebar identity.
4. Add only those verified identities to `USIPHU_REVIEWER_SUBJECTS`, separated by commas.

Illustrative format only (do not use these placeholders as real identities):

```text
USIPHU_REVIEWER_SUBJECTS=https://accounts.google.com:GOOGLE_SUBJECT_1,https://accounts.google.com:GOOGLE_SUBJECT_2
```

Restart the app after changing environment variables. The workflow still requires different authenticated identities for clinical approval and examination validation. Google proves control of an account; it does not prove professional registration, specialty competence or institutional authority.

## Hosted deployment

Before inviting remote reviewers, use HTTPS, add the exact hosted callback URI to the Google OAuth client, set the matching `redirect_uri` in the deployment's Streamlit secrets, and store both OAuth and cookie secrets in the host's secret manager. Set `USIPHU_AUTH_REQUIRED=true` and the verified reviewer allowlist in the deployment environment. Confirm persistent storage and backups for the SQLite audit database. Do not expose the local Streamlit port directly to the public internet.

## Still provisional

Until the OAuth client exists, credentials are configured, and two distinct faculty identities are verified and allowlisted, the pilot remains preview-only. Sign-in alone does not approve questions, and no question count expansion is part of this setup.

## Official references

- [Streamlit authentication and OIDC configuration](https://docs.streamlit.io/develop/concepts/connections/authentication)
- [Streamlit Google Auth Platform setup tutorial](https://docs.streamlit.io/develop/tutorials/authentication/google)
