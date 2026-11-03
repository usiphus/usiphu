# Usiphu 2.0

A medical learning workspace for specialty-wide curriculum mapping, resource discovery, question practice, OSCE/viva cases, spaced repetition, and learner progress.

> **Curriculum status:** the starter blueprint is cross-referenced to the user-supplied Suez University Faculty of Medicine bylaw (جامعة السويس), not Suez Canal University. Course ILOs from the supplied Surgery I/II, Medicine I/II, Emergency/Medical Reporting and PHC/Obs documents are now catalogued with partial topic-level outcome references. Pediatrics currently has two external undergraduate benchmarks (Al-Azhar Damietta and Aswan University) only; it is not an official Suez University ILO source. This working crosswalk is not faculty-approved or exam-validated. Starter questions and cases remain editorial drafts.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Install and start [Ollama](https://ollama.com), then pull the default model:

```bash
ollama pull qwen2.5:7b
OLLAMA_BASE_URL=http://localhost:11434 streamlit run app/Home.py
```

Set `USIPHU_OLLAMA_MODEL` to another locally installed Ollama model if needed. No OpenAI API key or paid model API is required. The first model download requires internet access and several GB of disk space; inference speed depends on available RAM/VRAM and hardware.

## Docker Compose

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec ollama ollama pull qwen2.5:7b
```

The app connects to the Compose Ollama service on the private Compose network. The Ollama host port is bound to `127.0.0.1`, not exposed to the LAN. Pull the model once after starting the stack; the named volume retains model files. To use a different model, change `USIPHU_OLLAMA_MODEL` in `.env` and pull that exact model tag in the Ollama container. For host-run Usiphu, set `OLLAMA_BASE_URL=http://localhost:11434`; inside a container, `localhost` refers to that container, not the host.

## Curriculum target

See [Suez University bylaw crosswalk](docs/SUEZ_UNIVERSITY_CURRICULUM.md), [course outcome mapping and source limitations](docs/SUEZ_COURSE_OUTCOME_MAPPING.md), [institutional profile](data/suez_university_curriculum.json), and [machine-readable course ILO catalog](data/suez_course_ilos.json). The bylaw specifies a five-year degree with Phase I (years 1–2) and Phase II (years 3–5), course/module codes, semesters and broad assessment structure. The uploaded course specifications now support outcome-level mapping for several modules. The official Suez PHC/ped 2.3.1 ILO document is still missing; the online pediatric material is explicitly external benchmark content. Internship duration and rotations remain unspecified in the uploaded bylaw.

## Features

- Specialty → domain → topic → measurable learning objectives.
- Resource discovery across PubMed, PMC, NCBI Bookshelf, Cureus, AnkiWeb, DoctorDE search, guidelines, and medical challenge sites.
- MCQ and structured clinical-case practice with explicit editorial status.
- PubMed-grounded local Ollama card drafting with source traceability, Suez ILO safeguards, evidence-quality ranking, and isolated draft review storage.
- Learner-isolated SQLite flashcards, spaced repetition, topic progress, and analytics.
- Optional OIDC authentication; FastAPI curriculum, practice, resource, and generation endpoints.
- Docker image and hardened single-node production Compose deployment with Caddy HTTPS and SQLite backups.

## Evidence-grounded AI generation

The generator retrieves PubMed abstracts and uses a locally hosted Ollama model to author evidence-linked draft cards. No paid model API key is needed. See [generator setup and safety](docs/GENERATOR_PIPELINE.md). Generated cards remain isolated drafts pending clinical review.

## Card generation

See [generator pipeline](docs/GENERATOR_PIPELINE.md). The runtime retrieves PubMed abstracts, calls the configured local Ollama model, validates source-linked output, and stores accepted cards as isolated drafts. Passing automated validation never means clinical approval.

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
