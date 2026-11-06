# Free staging deployment: Streamlit Community Cloud

## Decision

Use [Streamlit Community Cloud](https://share.streamlit.io/) for a zero-cost, temporary USIPHU preview. It is the simplest fit because USIPHU is already a Streamlit application and Community Cloud deploys directly from GitHub, including private repositories.

This is a **demo/staging host only**, not a durable multi-user environment or production host. Community Cloud apps hibernate after 12 hours without traffic, and the app's current SQLite database and Source Inbox live on the app filesystem. Do not store real learner records, faculty decisions, patient information, or original examination papers here. Treat all test data as disposable and synthetic. See the current [Community Cloud resource and hibernation limits](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app#app-hibernation).

## Why this is the free choice

- $0 hosting for Streamlit apps.
- Deploys from the existing GitHub repository; private repositories are supported.
- Streamlit handles the runtime and HTTPS app URL.
- Supports app secrets for OIDC configuration.
- It sleeps after 12 hours without traffic and has shared resource limits.

Official docs: [Community Cloud overview](https://docs.streamlit.io/deploy/streamlit-community-cloud), [deployment steps](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app), and [secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## Before deploying

1. Merge the staging-readiness PR only after its CI passes.
2. In GitHub, keep the repository private unless you deliberately want the source public.
3. Sign in at https://share.streamlit.io/ using the GitHub account that can access `usiphus/usiphu`.
4. Create an app from repository `usiphus/usiphu`, branch `main`, entrypoint `app/Home.py`.
5. Wait for the initial build. Do not share the URL until authentication is configured.

## Streamlit Community Cloud secrets

In the deployed app's **Settings → Secrets**, configure the following TOML. Replace every placeholder; never commit actual secrets to Git.

```toml
USIPHU_AUTH_REQUIRED = "true"
USIPHU_DB_PATH = "usiphu_data.sqlite3"
USIPHU_SOURCE_DIR = "data/source_inbox"
USIPHU_ADMIN_SUBJECTS = "https://YOUR_AUTH0_DOMAIN/:AUTH0_ADMIN_SUBJECT"
# Optional; use exact issuer-qualified issuer:subject values.
USIPHU_CLINICAL_REVIEWER_SUBJECTS = ""
USIPHU_EXAM_REVIEWER_SUBJECTS = ""

[auth]
redirect_uri = "https://YOUR-APP-NAME.streamlit.app/oauth2callback"
cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
client_id = "YOUR_AUTH0_CLIENT_ID"
client_secret = "YOUR_AUTH0_CLIENT_SECRET"
server_metadata_url = "https://YOUR_AUTH0_DOMAIN/.well-known/openid-configuration"
```

The app now bridges the non-OIDC values from `st.secrets` into the environment before importing the existing SQLite and reviewer-role modules. Streamlit itself reads the `[auth]` section for `st.login()`.

Use the exact Auth0 issuer value returned in the ID token for the issuer-qualified subject. Do not paste an access token, ID token, client secret, or password into GitHub issues or chat.

## Auth0 callback setup

In the Auth0 application's allowed callback URLs, add:

`https://YOUR-APP-NAME.streamlit.app/oauth2callback`

In allowed logout URLs, add the app's base URL:

`https://YOUR-APP-NAME.streamlit.app`

Use the actual app subdomain assigned by Community Cloud. Keep local callback URLs only if you still need local development. Verify the issuer/metadata URL against the Auth0 tenant's actual domain and region.

## Smoke-test sequence

Use synthetic accounts and records only:

1. Open the deployed app and confirm it wakes and loads.
2. Sign in as the learner test account; verify the issuer-qualified subject is present and the faculty pages/actions are unavailable.
3. Sign in separately as the configured admin; verify role assignment and audit history.
4. Use different clinical and exam reviewer accounts; verify the exam stage is blocked until clinical approval and that the same identity cannot perform both stages.
5. Generate one small test batch; confirm results remain drafts and duplicate prompts are flagged.
6. Restart/redeploy the app and verify expected behavior. Because storage is ephemeral, assume local SQLite and uploaded files may disappear; this is a limitation to record, not a persistence pass.
7. Confirm no real data was entered and remove test records when finished.

## What this host does not solve

The current app uses SQLite and local filesystem storage. Community Cloud does not provide a durable persistent disk for this app's local database/source folder. A proper multi-user pilot needs a database-backed storage migration (for example, PostgreSQL) and durable object storage, plus tested backups and restore. A free Supabase project offers PostgreSQL but may pause after a week of low activity and has no automatic backups on the free plan; it is a separate integration task, not a plug-in replacement for the existing SQLite layer.

Until durable storage is implemented and tested, use Community Cloud only for a disposable preview and UI/authentication checks. Do not treat it as faculty approval or learner-data staging.
