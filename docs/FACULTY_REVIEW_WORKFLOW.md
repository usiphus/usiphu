# USIPHU pilot faculty-review workflow

## Release sequence

Each pilot MCQ requires two sequential, independent faculty decisions.

1. **Clinical approval** — a clinician checks source transcription and provenance, the best answer, rationale, supporting evidence, exceptions and patient-safety implications.
2. **Examination validation** — a different authenticated faculty member checks single-best-answer construction, stem clarity, distractor quality, curriculum/blueprint alignment and difficulty.

A question is eligible for trusted scored practice only after both approvals. Clinical approval alone leaves it in provisional practice mode.

## Identity and permissions

USIPHU uses **Auth0 as its OIDC identity provider**. Follow [Auth0 sign-in setup](GOOGLE_OIDC_SETUP.md) (the file is retained for compatibility with the existing PR path) to create the Auth0 application, configure its exact callback, and collect each reviewer's stable identity.

Required deployment configuration:

- `USIPHU_AUTH_REQUIRED=true` — required for real sign-offs; local/non-authenticated mode is preview-only and blocks faculty submissions.
- `USIPHU_REVIEWER_SUBJECTS` — comma-separated allowlist of institution-verified OIDC identities in exact `issuer:sub` form.

Only allowlisted authenticated accounts can submit decisions. The reviewer identity stored in the audit log is the authenticated issuer/subject pair; a displayed faculty name is an additional label, not the security identity. The institution must independently verify each reviewer's faculty role, specialty competence and authority before adding the identity to the allowlist.

Do not use local single-user mode for real faculty sign-off. Typed names do not establish identity or independent reviewers. Auth0 login alone does not establish faculty authority.

## Audit and invalidation rules

- Each decision appends an event containing the stage, decision, authenticated reviewer, faculty name, timestamp, comment, content snapshot and checked attestations.
- The event table is append-only through the application workflow.
- The latest state is maintained separately for fast queue rendering.
- Clinical and examination approvers must have different authenticated identities.
- Any material change to the stem, options, answer, rationale, curriculum topic or difficulty invalidates both approvals. The edited version must pass clinical approval again before examination validation.
- Request-changes and rejection decisions remain visible in history and do not enable trusted scoring.
- Authored JSON remains the immutable source bank; the current approval state is overlaid from SQLite when questions are loaded.
- Back up the SQLite database alongside the authored question-bank files. The audit trail is stored in that database.

## Pilot release checklist

- [ ] Auth0 tenant and Regular Web Application configured.
- [ ] Auth0 client credentials stored securely outside version control.
- [ ] Exact local/hosted callback tested; hosted deployment uses HTTPS.
- [ ] `USIPHU_AUTH_REQUIRED=true` enabled in the intended deployment.
- [ ] Clinical faculty accounts independently verified and added to `USIPHU_REVIEWER_SUBJECTS`.
- [ ] Examination faculty accounts independently verified and added to `USIPHU_REVIEWER_SUBJECTS`.
- [ ] Clinical and examination reviewers are distinct for every question.
- [ ] Source-paper page and answer transcription rechecked by faculty.
- [ ] Every clinical approval includes all four clinical attestations.
- [ ] Every examination approval includes all five exam attestations.
- [ ] CI passes before deployment.
- [ ] SQLite audit database is backed up before and after the review cycle.

## Operational limitation and release gate

The app records authenticated attestations and audit history; it cannot independently establish a faculty member's professional registration, specialty competence, institutional appointment or delegated authority. The institution must verify reviewer eligibility and maintain the allowlist. Formal institutional approval and local syllabus validation remain human responsibilities.

Until Auth0 credentials are configured and tested and two distinct faculty identities are institutionally verified and allowlisted, the pilot remains preview-only. Only `exam_validated` items are eligible for scored practice. The pilot bank remains fixed at 17 questions (9 Urology and 8 General Surgery); no expansion is part of this workflow.
