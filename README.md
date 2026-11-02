# Usiphu 2.0

A medical learning workspace for specialty-wide curriculum mapping, resource discovery, question practice, OSCE/viva cases, spaced repetition, and learner progress.

> **Curriculum status:** the starter blueprint is cross-referenced to the user-supplied Suez University Faculty of Medicine bylaw (جامعة السويس), not Suez Canal University. The repository now contains a bylaw-based module-level crosswalk; individual course outcomes and internship rotations remain unverified. It is not faculty-approved or exam-validated. Starter questions and cases remain editorial drafts.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
streamlit run app/Home.py
```

## Curriculum target

See [Suez University crosswalk](docs/SUEZ_UNIVERSITY_CURRICULUM.md) and machine-readable [institutional profile](data/suez_university_curriculum.json). The uploaded bylaw specifies a five-year degree with Phase I (years 1–2) and Phase II (years 3–5), course/module codes, semesters and broad assessment structure. It does not specify internship duration or detailed module-level learning outcomes; obtain current course specifications and confirm the bylaw's applicability to the learner's cohort.

## Features

- Specialty → domain → topic → measurable learning objectives.
- Resource discovery across PubMed, PMC, NCBI Bookshelf, Cureus, AnkiWeb, DoctorDE search, guidelines, and medical challenge sites.
- MCQ and structured clinical-case practice with explicit editorial status.
- Learner-isolated SQLite flashcards, spaced repetition, topic progress, and analytics.
- Optional OIDC authentication; FastAPI read-only content endpoints.
- Docker image and hardened single-node production Compose deployment with Caddy HTTPS and SQLite backups.

## Production

See [production deployment](docs/DEPLOYMENT.md). The production Compose setup is a single-replica deployment using persistent SQLite, OIDC, Caddy TLS, and verified online backups. **PostgreSQL is not yet connected to the application storage layer**; do not horizontally scale until a PostgreSQL adapter and migrations are implemented and tested.

## Checks

```bash
ruff check .
pytest -q
python -m usiphu.validation
```

## Release gates

- Obtain and map the complete Suez University bylaw/course specifications.
- Have departmental educators review the outcome crosswalk and all clinical content.
- Configure real OIDC secrets, domain/DNS, backups, monitoring, and privacy controls.
- Complete security, accessibility, and user-acceptance testing.
