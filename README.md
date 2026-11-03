# Usiphu 2.0

A medical learning workspace for specialty-wide curriculum mapping, resource discovery, question practice, OSCE/viva cases, spaced repetition, and learner progress.

> **Curriculum status:** the starter blueprint is cross-referenced to the user-supplied Suez University Faculty of Medicine bylaw (جامعة السويس), not Suez Canal University. Course ILOs from the supplied Surgery I/II, Medicine I/II, Emergency/Medical Reporting and PHC/Obs documents are now catalogued with partial topic-level outcome references. Pediatrics currently has two external undergraduate benchmarks (Al-Azhar Damietta and Aswan University) only; it is not an official Suez University ILO source. This working crosswalk is not faculty-approved or exam-validated. Starter questions and cases remain editorial drafts.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
streamlit run app/Home.py
```

## Curriculum target

See [Suez University bylaw crosswalk](docs/SUEZ_UNIVERSITY_CURRICULUM.md), [course outcome mapping and source limitations](docs/SUEZ_COURSE_OUTCOME_MAPPING.md), [institutional profile](data/suez_university_curriculum.json), and [machine-readable course ILO catalog](data/suez_course_ilos.json). The bylaw specifies a five-year degree with Phase I (years 1–2) and Phase II (years 3–5), course/module codes, semesters and broad assessment structure. The uploaded course specifications now support outcome-level mapping for several modules. The official Suez PHC/ped 2.3.1 ILO document is still missing; the online pediatric material is explicitly external benchmark content. Internship duration and rotations remain unspecified in the uploaded bylaw.

## Features

- Specialty → domain → topic → measurable learning objectives.
- Resource discovery across PubMed, PMC, NCBI Bookshelf, Cureus, AnkiWeb, DoctorDE search, guidelines, and medical challenge sites.
- MCQ and structured clinical-case practice with explicit editorial status.
- PubMed-grounded OpenAI card drafting with source traceability, Suez ILO safeguards, evidence-quality ranking, and isolated draft review storage.
- Learner-isolated SQLite flashcards, spaced repetition, topic progress, and analytics.
- Optional OIDC authentication; FastAPI read-only content endpoints.
- Docker image and hardened single-node production Compose deployment with Caddy HTTPS and SQLite backups.

## Evidence-grounded AI generation

The generator can retrieve PubMed abstracts and use a server-configured OpenAI model to author evidence-linked draft cards. Configure `OPENAI_API_KEY` as a server secret; see [generator setup and safety](docs/GENERATOR_PIPELINE.md). Generated cards remain isolated drafts pending clinical review.

## Card generation

See [generator pipeline](docs/GENERATOR_PIPELINE.md). The runtime retrieves PubMed abstracts, calls a server-configured OpenAI model, validates source-linked output, and stores accepted cards as isolated drafts. Passing automated validation never means clinical approval.

## Production

See [production deployment](docs/DEPLOYMENT.md). The production Compose setup is a single-replica deployment using persistent SQLite, OIDC, Caddy TLS, and verified online backups. **PostgreSQL is not yet connected to the application storage layer**; do not horizontally scale until a PostgreSQL adapter and migrations are implemented and tested.

## Checks

```bash
ruff check .
pytest -q
python -m usiphu.validation
```

## Release gates

- Obtain the official Suez University PHC/ped 2.3.1 course specification and any missing/current module specifications.
- Confirm the uploaded specification versions apply to the target cohort.
- Have departmental educators review the outcome crosswalk and all clinical content.
- Configure real OIDC secrets, domain/DNS, backups, monitoring, and privacy controls.
- Complete security, accessibility, and user-acceptance testing.
