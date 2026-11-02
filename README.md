# Usiphu 2.0

A local-first medical learning workspace combining specialty-wide curriculum mapping, resource discovery, question practice, OSCE/viva cases, spaced repetition, and learner progress.

> **Foundation release.** The curriculum is a broad cross-specialty starter blueprint, not a claim that any national syllabus is complete. The included question and case banks are editorial drafts, not clinically validated assessment material. Verify clinical information against current guidelines and local protocols.

## Run locally (Python 3.11+)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
streamlit run app/Home.py
```

Optional read-only content API: `uvicorn usiphu.api:app --reload`

Checks: `ruff check . && pytest -q`

## Features

- Specialty → domain → topic → measurable learning objectives, with source and validation stages.
- Topic-aware discovery links for PubMed, PMC, NCBI Bookshelf, Cureus, AnkiWeb, DoctorDE web search, WHO, NICE, Cochrane, and MedEdPORTAL.
- Specialty guideline hubs including EAU, ESC, KDIGO, GINA, GOLD, IDSA, ACOG, AAP, AAO, SVS, ASA, AAN, AAD, and APA.
- MCQ and structured clinical-case practice with explicit draft/review status.
- Persistent flashcards with an SM-2-inspired scheduler.
- Learner-isolated SQLite flashcards, review events, and topic mastery.
- Optional OIDC authentication through Streamlit's native identity integration.
- FastAPI read endpoints, Streamlit UI, tests, Dockerfile, and Compose deployment.

## Accounts and deployment

The default local mode is for one learner on a trusted machine. To enable sign-in, configure an OIDC provider and set `USIPHU_AUTH_REQUIRED=true`. See [deployment instructions](docs/DEPLOYMENT.md) and copy the template at `.streamlit/secrets.toml.example` to your untracked `.streamlit/secrets.toml`.

Docker Compose requires OIDC and persists SQLite in a named volume. SQLite is a single-node pilot store; migrate to managed PostgreSQL before multi-replica production use. Do not expose the app publicly without HTTPS, OIDC, and operational controls.

## Project map

`app/` UI · `usiphu/` domain logic/API/storage · `data/` versioned learning content · `tests/` automated checks · `docs/` product, source, and deployment governance.

## Source and safety policy

The app links to external discovery services; it does not scrape, reproduce, or redistribute third-party decks or articles. Check licensing, authorship, publication date, and clinical applicability. PubMed is a citation/abstract index; PMC provides full text where available. AnkiWeb decks are community-contributed. DoctorDE is linked through a web-search route because a stable official endpoint has not been verified.

## Release gates still requiring human sign-off

- Map each specialty to a named Egyptian, institutional, or other target syllabus and review every learning objective for completeness.
- Clinically review and exam-validate the authored MCQ and OSCE banks with qualified educators.
- Perform a privacy/security review and configure a production identity provider, PostgreSQL, backups, and monitoring.
- Conduct accessibility and user-acceptance testing on the intended deployment environment.
