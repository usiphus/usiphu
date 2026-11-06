# USIPHU staging acceptance plan

This runbook is for a controlled, non-production staging deployment. It does not authorize public release or replace institutional security, privacy, or faculty approval.

## Release candidate

- Repository: `usiphus/usiphu`
- Candidate branch: `main`
- Require a green CI run on the exact commit being deployed.
- Keep staging isolated from production data. Use synthetic learner accounts and synthetic content only.
- Do not upload patient-identifiable information or real examination papers unless institutional permission and retention controls are in place.

## 1. Hosting and runtime gate

Before deployment, record the hosting provider, staging hostname, operator, deployment commit SHA, Python version, and rollback procedure.

The host must provide:
- HTTPS and a stable hostname.
- A persistent writable volume for the SQLite database and Source Inbox, with documented backup/restore.
- A supported way to set secrets without committing them to Git.
- Process restart and health monitoring.
- Outbound HTTPS for Auth0, PubMed/Europe PMC and any configured model endpoint.
- A plan for Ollama: either a reachable private model host with resource limits and authentication, or explicitly disable AI generation in staging.

Do not use an ephemeral filesystem for `USIPHU_DB_PATH` or `USIPHU_SOURCE_DIR`. The current application storage layer is SQLite/local-file based; do not horizontally scale multiple app replicas against one local SQLite file.

## 2. Staging environment variables and secrets

Set these through the hosting provider's secret/configuration interface, not in source control:
- `USIPHU_AUTH_REQUIRED=true`
- `USIPHU_DB_PATH` to an absolute path on persistent storage.
- `USIPHU_SOURCE_DIR` to an absolute path on persistent storage.
- `USIPHU_BACKUP_DIR` to a protected backup staging path.
- Auth0 issuer, audience/client configuration and exact callback/logout URLs required by the app.
- `USIPHU_ADMIN_SUBJECTS` with exact issuer-qualified `issuer:subject` values.
- Optional stage reviewer allowlists only when the institution has explicitly appointed those people.
- Ollama endpoint/model and PubMed contact/API settings only if those integrations are enabled.

Never put secrets, tokens, private keys, real user identifiers, or production data in GitHub Actions logs or test fixtures.

## 3. Auth0 and role-based access acceptance

Use at least four separate test identities: learner, admin, clinical reviewer A, and exam reviewer B. Use a fifth identity for negative/independence checks where practical.

- [ ] Learner can log in, refresh the session, and log out on the exact staging hostname.
- [ ] Callback and logout return to the expected staging URL; no localhost or production URL is used accidentally.
- [ ] Invalid issuer/audience/token is rejected.
- [ ] Learner cannot open faculty queue, assign roles, or submit clinical/exam decisions through UI or direct API calls.
- [ ] Admin can assign and revoke clinical/exam reviewer roles; role changes are visible in the audit history.
- [ ] Admin role is bootstrapped only from the configured issuer-qualified subject allowlist and cannot be granted through the UI.
- [ ] Clinical reviewer A can submit a clinical decision; exam-only reviewer B cannot.
- [ ] Exam reviewer B cannot approve before clinical approval.
- [ ] The same issuer-qualified identity cannot perform both stages, even if it holds both stage roles.
- [ ] Missing provenance, required evidence, attestations, or complete answer/rubric data blocks approval.
- [ ] Rejection/request-changes does not release an item to learners.
- [ ] Editing content after clinical approval invalidates prior approvals for the changed snapshot.
- [ ] Local/single-user mode cannot submit faculty decisions.

Record the test account pseudonyms, result, timestamp, tested commit and evidence link. Do not record passwords or tokens.

## 4. Database persistence and disaster recovery

Use synthetic data only.

- [ ] Create a learner, save a draft, record a practice attempt, add a source file, and create a review-queue item.
- [ ] Restart the app process and confirm the records remain.
- [ ] Restart the host if permitted and confirm the records remain.
- [ ] Stop the app and create a paired SQLite + Source Inbox backup using `python scripts/backup_sqlite.py`.
- [ ] Copy backup files and checksum to a separate protected location.
- [ ] Restore into a new empty directory using `python scripts/restore_backup.py`; never restore over the live database.
- [ ] Verify SQLite integrity, source archive checksum, source manifest, original uploaded file, extracted candidate, learner activity, reviewer role assignments, and audit events.
- [ ] Document recovery point and recovery time achieved.
- [ ] Confirm backup retention, encryption, access restriction and deletion policy.

The repository's local persistence/recovery workflow should also pass on the exact candidate commit.

## 5. Generator acceptance

Use a small, controlled test brief and a fixed test topic.

- [ ] Generator page loads for an authorized user without a traceback.
- [ ] Validate required-field errors and unsupported/invalid option combinations.
- [ ] Run one quick generation and one small batch.
- [ ] Confirm progress/status updates and bounded timeout behavior.
- [ ] Confirm duplicate prompts within a batch are rejected or clearly flagged.
- [ ] Confirm objective coverage summary and percentage are consistent with the brief.
- [ ] Confirm successful drafts retain their brief identifier and source/provenance packet.
- [ ] Confirm a failed/partial model or PubMed request produces a recoverable, understandable error and does not create a falsely complete item.
- [ ] Confirm generated content is stored as a draft, not released directly to learner practice.
- [ ] Measure wall-clock duration and record host CPU/RAM, model tag, PubMed response status and any timeout.

Do not treat a fluent generated answer or an automated evidence match as clinical validation.

## 6. Faculty review and assessment queue acceptance

Use synthetic assessment items only.

- [ ] Generated MCQ and written/OSCE/viva/EMQ candidates appear in the expected shared review queue.
- [ ] Extracted candidates retain source identifier, filename and page provenance.
- [ ] Incomplete extraction candidates cannot receive clinical approval.
- [ ] Clinical approval requires its required attestations and complete review packet.
- [ ] Exam approval requires prior clinical approval and a different identity.
- [ ] Role restrictions are enforced server-side, not only by hidden UI controls.
- [ ] Review decisions and role changes are present in the audit trail.
- [ ] A content edit changes the snapshot and invalidates earlier approvals.
- [ ] No staged/approved item is assumed to be learner-visible unless a separately tested promotion mechanism explicitly publishes it.

Known boundary: the shared review queue does not yet automatically promote every approved assessment format into learner-facing practice banks. Treat approval and learner publication as separate operations until that workflow is implemented and tested.

## 7. Operational and privacy checks

- [ ] Health endpoint and app login work after deploy and after restart.
- [ ] Logs do not contain secrets, tokens, passwords, or unnecessary personal data.
- [ ] Error monitoring and uptime alerts reach a named operator.
- [ ] Database and Source Inbox backup jobs have a named owner and tested restore cadence.
- [ ] Incident contact, rollback commit and rollback procedure are documented.
- [ ] Privacy notice, data retention/deletion rules and institutional approval are in place.
- [ ] No real patient data is used in staging without formal approval and controls.

## 8. Sign-off record

Complete before enabling any learner cohort:

| Gate | Owner | Result | Evidence / date |
|---|---|---|---|
| CI on deployment SHA | Engineering | Pending | |
| Hosting and persistence | Engineering/operations | Pending | |
| Auth0 and role authorization | Engineering/security | Pending | |
| Backup and restore drill | Operations | Pending | |
| Generator acceptance | Product/engineering | Pending | |
| Faculty workflow acceptance | Faculty lead | Pending | |
| Clinical content and curriculum review | Department faculty | Pending | |
| Privacy/security approval | Institution | Pending | |
| Rollback and incident readiness | Operations | Pending | |

A passing CI suite is necessary but does not establish clinical, educational, privacy, or production readiness.
