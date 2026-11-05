# USIPHU release-readiness checklist

This checklist is a deployment gate, not a statement that the current repository is production-ready.

## 1. Pull requests and automated validation

- [ ] PR #6 generator quality gate is merged to `main` only after Ruff, compileall, curriculum validation, JSON parsing and pytest all pass.
- [ ] PR #7 faculty roles is retargeted to `main` after PR #6 merges; obtain faculty/security review and require the full CI suite.
- [ ] The shared generated/extracted assessment queue change is reviewed and tested in its own PR before deployment.
- [ ] Review all changed files and migration behavior; do not use a passing CI run as clinical approval.
- [ ] Confirm no unresolved high-severity dependency or security alerts.

## 2. Authentication and authorization

- [ ] Set `USIPHU_AUTH_REQUIRED=true` in every shared deployment.
- [ ] Configure Auth0 issuer/audience/callback/logout URLs for the deployed hostname.
- [ ] Set `USIPHU_ADMIN_SUBJECTS` to exact issuer-qualified `issuer:subject` values in deployment secrets.
- [ ] Grant clinical and examination roles only to named, qualified faculty; use different people for the two approvals.
- [ ] Verify learner accounts cannot view or mutate faculty decisions or reviewer assignments.
- [ ] Verify local single-user mode cannot submit faculty decisions.
- [ ] Rotate credentials and document an administrator offboarding procedure.

## 3. Database and persistence

- [ ] Set a durable `USIPHU_DB_PATH` on persistent storage; do not rely on an ephemeral container filesystem.
- [ ] Back up the SQLite database before deployment and before schema changes.
- [ ] Test restore from backup, including faculty role assignments and append-only review events.
- [ ] Confirm the app process has least-privilege read/write access to the database and source inbox.
- [ ] Confirm generated drafts remain learner-isolated and the shared review queue stores only reviewable content/provenance.

## 4. AI and evidence configuration

- [ ] Confirm Ollama is reachable from the app host and the exact configured model tag is installed.
- [ ] Set bounded inference timeout and monitor CPU/RAM/disk usage.
- [ ] Configure PubMed contact details and API key where appropriate; verify outbound HTTPS.
- [ ] Confirm the interface clearly labels abstract-only evidence and generated content as drafts.
- [ ] Verify no model output can self-approve or enter the trusted learner queue.
- [ ] Establish a guideline-first retrieval and local Egypt/Suez protocol review process before clinical deployment.

## 5. Faculty workflow acceptance tests

- [ ] Admin can grant/revoke stage-specific reviewer roles; all changes are audited.
- [ ] Clinical reviewer can submit clinical review; examination-only reviewer cannot.
- [ ] Examination review is blocked until clinical approval.
- [ ] The same identity cannot complete both stages.
- [ ] Missing source provenance, evidence, or attestations blocks approval.
- [ ] Content changes invalidate prior approvals and require review of the new snapshot.
- [ ] Generated MCQ, OSCE, viva, EMQ and short-answer items appear in the shared faculty queue.
- [ ] Extracted source candidates retain source ID, filename and page provenance.
- [ ] A reviewer can request changes or reject; neither outcome releases content.
- [ ] Only the exact exam-validated snapshot may be promoted to learner-facing content.

## 6. Production smoke tests and operations

- [ ] Test Auth0 login/logout on the deployed hostname using learner, faculty and admin accounts.
- [ ] Test generator health, one quick-run generation, batch validation, saving drafts and queue visibility.
- [ ] Test learner isolation with two separate accounts.
- [ ] Test backup/restore, database locking/restart behavior and recovery from Ollama/PubMed outages.
- [ ] Configure error monitoring, uptime checks, audit-log retention and incident contacts.
- [ ] Publish a privacy notice and define retention/deletion rules for uploaded past papers and learner data.
- [ ] Obtain faculty sign-off on the content governance process before enabling learner release.

## Current known boundaries

- The current pilot MCQ workflow and the shared generated/extracted review queue are separate review surfaces. The shared queue records staged decisions but does not yet automatically promote every approved assessment format into the learner practice bank.
- Extracted candidates are transcriptions, not verified questions or answer keys. OCR/scanned-PDF extraction, official paper provenance and clinical answer verification require human review.
- PubMed abstracts are not full-text guideline review. Clinical safety, local protocol applicability, and exam validity remain human responsibilities.
- This checklist does not replace institutional security, privacy, clinical governance or educational quality approval.
