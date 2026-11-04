# Auth0 sign-in setup for USIPHU

USIPHU uses **Auth0 as its OpenID Connect (OIDC) identity provider**. Auth0 authenticates an account; USIPHU separately authorizes faculty reviewers. Authentication alone never grants reviewer privileges.

**Do not enable real faculty sign-offs until all setup and identity-verification gates below are complete.** The pilot remains preview-only until then.

## 1. Create an Auth0 tenant and application

1. Create or sign in to an Auth0 account at [Auth0](https://auth0.com/).
2. In the Auth0 Dashboard, create a tenant. Record its exact domain, for example `your-tenant.region.auth0.com`. Use the domain shown by Auth0; do not copy the example.
3. Go to **Applications → Applications → Create Application**.
4. Name it `USIPHU` and select **Regular Web Application**.
5. Open the application's **Settings** and configure the allowed URLs:
   - Local callback: `http://localhost:8501/oauth2callback`
   - Hosted callback: `https://YOUR-REAL-HOSTNAME/oauth2callback` (replace with the exact deployed hostname)
   - Local logout URL: `http://localhost:8501`
   - Hosted logout URL: `https://YOUR-REAL-HOSTNAME`
   - Add the matching local/hosted origins under **Allowed Web Origins** if your deployment requires them.
6. Save changes. Copy the **Domain**, **Client ID**, and **Client Secret**. Treat the client secret as confidential.
7. Under **Authentication → Database** (or the intended institution-managed connection), enable only the sign-in connections appropriate for the pilot. Restrict access to intended test users where possible and enable suitable account-security controls.

Auth0 callback URLs are matched against the application's configured allowed callback list. Register the exact URL, including scheme, hostname, port and path; do not use a wildcard callback.

## 2. Configure USIPHU locally

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`. The latter is ignored by Git. Replace all placeholders with values from your Auth0 tenant/application:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "PASTE_A_LONG_RANDOM_SECRET_HERE"
client_id = "PASTE_AUTH0_CLIENT_ID_HERE"
client_secret = "PASTE_AUTH0_CLIENT_SECRET_HERE"
server_metadata_url = "https://YOUR-AUTH0-DOMAIN/.well-known/openid-configuration"
```

Use the tenant's exact domain in the metadata URL, including `https://`. For example, if the dashboard shows `your-tenant.eu.auth0.com`, the metadata URL is `https://your-tenant.eu.auth0.com/.well-known/openid-configuration`.

Generate a strong cookie secret locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Never commit `secrets.toml`, publish the client secret, or send secrets in chat, screenshots or issue comments.

## 3. Start authenticated preview

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

Use **Continue with Auth0**. After successful login, the app sidebar displays the authenticated identity in `issuer:sub` form. Each proposed reviewer should share that exact identity with the pilot administrator through an approved secure channel.

## 4. Verify and authorize two independent faculty reviewers

1. Have each proposed reviewer authenticate using their own Auth0 account.
2. Independently verify each person's faculty appointment, specialty/role, and delegated authority with the institution. An Auth0 account, email address, or successful login is not evidence of professional registration or faculty authority.
3. Collect the exact `issuer:sub` value displayed by USIPHU for each verified reviewer.
4. Add only institution-verified identities to `USIPHU_REVIEWER_SUBJECTS`, separated by commas. Use the exact issuer and subject values; do not substitute email addresses or display names.

Illustrative format only — these placeholders are not real reviewer identities:

```text
USIPHU_REVIEWER_SUBJECTS=https://YOUR-AUTH0-DOMAIN/:AUTH0_SUBJECT_1,https://YOUR-AUTH0-DOMAIN/:AUTH0_SUBJECT_2
```

Restart the application after changing environment variables. For every question, USIPHU continues to require:
- clinical approval with its required source, evidence and safety attestations;
- a separate examination validation with its required exam-quality attestations;
- two different authenticated `issuer:sub` identities;
- required comments and append-only review events; and
- renewed review after a material content edit invalidates previous approvals.

Only `exam_validated` questions are eligible for scored practice. Clinical approval alone remains provisional.

## 5. Hosted deployment

Before inviting reviewers:
- deploy behind HTTPS and register the exact hosted callback/logout URLs in Auth0;
- set the matching hosted `redirect_uri` and Auth0 metadata URL in the deployment's Streamlit secrets;
- store the Auth0 client secret and cookie secret in the hosting platform's secret manager, never in the repository;
- set `USIPHU_AUTH_REQUIRED=true` and the institution-verified `USIPHU_REVIEWER_SUBJECTS` allowlist;
- confirm persistent storage, access controls and backups for the SQLite review/audit database; and
- test login, logout, reviewer authorization, separation of duties and audit history before real sign-off is enabled.

Do not expose the local Streamlit port directly to the public internet.

## 6. Preview-only release gate

The pilot remains preview-only if any of the following is missing: an Auth0 tenant/application, valid client credentials, a tested exact callback, HTTPS for hosted use, verified faculty roles, or two distinct allowlisted reviewer identities. Do not add placeholder identities to the allowlist. Do not manually alter database state to simulate approvals.

The existing pilot remains **17 questions (9 Urology and 8 General Surgery)**. This provider change does not expand the question bank or approve any question.

## Official references

- [Auth0: Create applications](https://auth0.com/docs/get-started/applications)
- [Auth0: Application settings and allowed callback URLs](https://auth0.com/docs/get-started/applications/application-settings)
- [Auth0: OpenID Connect protocol](https://auth0.com/docs/authenticate/protocols/openid-connect-protocol)
- [Streamlit authentication and OIDC configuration](https://docs.streamlit.io/develop/concepts/connections/authentication)
