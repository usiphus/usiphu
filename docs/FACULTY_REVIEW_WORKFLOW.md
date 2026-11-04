# USIPHU pilot faculty-review workflow

## Release sequence

Each pilot MCQ requires two sequential, independent faculty decisions.

1. **Clinical approval** — a clinician checks source transcription and provenance, the best answer, rationale, supporting evidence, exceptions and patient-safety implications.
2. **Examination validation** — a different authenticated faculty member checks single-best-answer construction, stem clarity, distractor quality, curriculum/blueprint alignment and difficulty.

A question is eligible for trusted scored practice only after both approvals. Clinical approval alone leaves it in provisional practice mode.

## Identity and permissions

Use Google as the default Streamlit OIDC provider. Follow [Google OIDC setup](GOOGLE_OIDC_SETUP.md) to create the OAuth client, configure the callback and collect each reviewer's stable identity. Then set:

- `USIPHU_AUTH_REQUIRED=true` (required for real sign-offs; local mode remains preview-only)
- `USIPHU_REVIEWER_SUBJECTS` to a comma-separated allowlist of authenticated OIDC identities in `issuer:sub` form. Include the exact issuer URL and stable `sub` claim for each approved faculty account.

Only allowlisted accounts can submit decisions. The reviewer identity stored in the audit log is the authenticated issuer/subject pair; the displayed faculty name is an additional label, not the security identity.

Do not use local single-user mode for real faculty sign-off. Local mode permits queue inspection but disables faculty submissions because typed names do not establish identity or independent reviewers.

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

- [ ] OIDC provider configured and callback tested.
- [ ] Clinical faculty accounts added to `USIPHU_REVIEWER_SUBJECTS`.
- [ ] Examination faculty accounts added to `USIPHU_REVIEWER_SUBJECTS`.
- [ ] Clinical and examination reviewers are distinct for every question.
- [ ] Source-paper page and answer transcription rechecked by faculty.
- [ ] Every clinical approval includes all four clinical attestations.
- [ ] Every examination approval includes all five exam attestations.
- [ ] CI passes before deployment.
- [ ] SQLite audit database is backed up before and after the review cycle.

## Operational limitation

The app records authenticated attestations and audit history; it cannot independently establish a faculty member's professional registration, specialty competence, institutional appointment or delegated authority. The institution must verify reviewer eligibility and maintain the allowlist. Formal institutional approval and local syllabus validation remain human responsibilities.
