# Usiphu 2.0

A local-first medical learning workspace spanning basic sciences, clinical specialties, question practice, OSCE/viva cases, spaced repetition, and learner progress.

> **Curriculum status:** the starter blueprint is cross-referenced to the user-supplied Suez University Faculty of Medicine bylaw (جامعة السويس), not Suez Canal University. Course ILOs from the supplied Surgery I/II, Medicine I/II, Emergency/Medical Reporting and PHC/Obs documents are catalogued with partial topic-level outcome references. Pediatrics currently has two external undergraduate benchmarks only; it is not an official Suez University ILO source. This working crosswalk is not faculty-approved or exam-validated. Starter questions and cases remain editorial drafts.

## Run USIPHU locally

USIPHU runs directly with Python. Docker, Docker Compose, a server and a domain are not required.

**Requirements:** Python 3.11 or newer.

### Windows (one-click setup)

1. Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/windows/). Keep the Python Launcher option enabled.
2. Extract/clone the USIPHU project folder to a location where you have write permission.
3. Double-click `setup_windows.bat`. It creates the local `.venv`, installs USIPHU and its dependencies, then launches the app.
4. Later, double-click `start_usiphu.bat` to open USIPHU without reinstalling dependencies.

Keep the launcher window open while using USIPHU; close it with Ctrl+C when finished. The app normally opens at http://localhost:8501. No PowerShell activation or Docker is required. The first setup needs internet access to download Python packages.

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
streamlit run app/Home.py
```

Open the local address printed by Streamlit (normally http://localhost:8501). Keep the terminal window open while using USIPHU; press Ctrl+C to stop it.

## Local AI (optional)

The core learning platform, question extraction, review editor, and open-access evidence retrieval can run without a local language model. To enable AI-assisted authoring and rubric review, install [Ollama](https://ollama.com), start it on your computer, and pull the default model:

```bash
ollama pull qwen2.5:7b
```

Set the model endpoint before launching USIPHU:

**Windows PowerShell**
```powershell
$env:OLLAMA_BASE_URL="http://localhost:11434"
$env:USIPHU_OLLAMA_MODEL="qwen2.5:7b"
streamlit run app/Home.py
```

**macOS / Linux**
```bash
OLLAMA_BASE_URL=http://localhost:11434 USIPHU_OLLAMA_MODEL=qwen2.5:7b streamlit run app/Home.py
```

No paid model API key is required for the local Ollama workflow. The first model download requires internet access and several GB of disk space; inference speed depends on available RAM/VRAM and hardware.

## Where your data is stored

- SQLite learner database: `usiphu_data.sqlite3` in the project directory by default.
- Uploaded examination papers, source metadata, extraction JSON and review history: `data/source_inbox/` by default.
- Local backup files: `data/backups/` when using the backup script defaults.
- OIDC secrets, if you later configure authentication: `.streamlit/secrets.toml` (never commit this file).

These files remain on the computer running USIPHU. Back them up regularly. Do not expose the local Streamlit port directly to the public internet. See [local setup, backup and restore](docs/DEPLOYMENT.md).

## Curriculum target

See [Suez University bylaw crosswalk](docs/SUEZ_UNIVERSITY_CURRICULUM.md), [course outcome mapping and source limitations](docs/SUEZ_COURSE_OUTCOME_MAPPING.md), [institutional profile](data/suez_university_curriculum.json), and [machine-readable course ILO catalog](data/suez_course_ilos.json). The bylaw specifies a five-year degree with Phase I (years 1–2) and Phase II (years 3–5), course/module codes, semesters and broad assessment structure. The uploaded course specifications support outcome-level mapping for several modules. The official Suez PHC/ped 2.3.1 ILO document is still missing; online pediatric material is explicitly external benchmark content. The working crosswalk remains partial and not faculty-verified.

## Medical curriculum coverage

The curriculum blueprint contains 27 medical disciplines, 174 topics and 291 learning objectives. The auditable [coverage register](data/curriculum_coverage.json) records 50 topics with direct course-outcome links, 6 partial links, 4 external-benchmark-only topics, 2 module-only topics and 112 topics without a verified outcome mapping. The current first-pass catalogue contains 73 grouped official Suez outcomes: 47 are linked to topics and 26 are not linked in the current crosswalk. These are topic-level links, not proof that individual objectives are mapped. Zero objectives have yet received individual faculty-verified mapping. The granular extraction workspace contains 616 page-cited outcome statements across seven supplied source files; each retains source, module, printed page and draft transcription status, and none is faculty-verified. See [specialty exam blueprints](data/specialty_exam_blueprints.json).

## Features

- Specialty → domain → topic → measurable learning objectives.
- Resource discovery across PubMed, PMC, NCBI Bookshelf, Cureus, AnkiWeb, DoctorDE search, guidelines, and medical challenge sites.
- A multi-file medical question-bank loader, specialty/topic/difficulty/editorial filters, answer explanations, learner-isolated attempt history and accuracy tracking; the current starter set contains 3 draft MCQs, not a complete exam bank.
- Source Inbox with automatic text extraction for readable PDF/DOCX/TXT uploads, page-cited draft question candidates, MEQ page capture and human-review gating; scanned/image sources require OCR/manual handling.
- Review Editor with AI-assisted transcription checks and open-access medical evidence comparison for each MCQ option (Europe PMC / PubMed Central), source links, publication metadata and human approval gates.
- Pilot Validation Dashboard tracking per-paper extraction candidates, human transcription confirmations/corrections, answer-key review outcomes, AI evidence verdicts and retrieved-source metadata. See [Pilot Validation](docs/PILOT_VALIDATION.md).
- MCQ and structured clinical-case practice with explicit editorial status.
- Specialty-aware PubMed-grounded local Ollama drafting with MCQ, short-answer, clinical-case, OSCE, viva and EMQ formats; source traceability, Suez ILO safeguards and isolated draft review storage.
- Learner-isolated SQLite flashcards, spaced repetition, topic progress, and analytics.
- Optional OIDC authentication; FastAPI curriculum, practice, resource, and generation endpoints.
- Local SQLite and Source Inbox storage with paired backup/restore utilities. The app runs directly under Python without a container runtime.

## Evidence-grounded AI generation

The generator retrieves PubMed abstracts and uses a locally hosted Ollama model to author evidence-linked draft cards. No paid model API key is needed. See [generator setup and safety](docs/GENERATOR_PIPELINE.md). Generated cards remain isolated drafts pending clinical review.

## Card generation

See [generator pipeline](docs/GENERATOR_PIPELINE.md). The runtime retrieves PubMed abstracts, calls the configured local Ollama model, validates source-linked output, and stores accepted cards as isolated drafts. Passing automated validation never means clinical approval. Every accepted draft stores a specialty- and format-specific human review packet with the card; see [the clinical/exam review rubric](data/clinical_exam_review_rubric.json).

## Hosting later

USIPHU is local-first at this stage; no remote server or public domain is configured. If you later want access from multiple devices or learners, choose a host with persistent disk or managed database/object storage, HTTPS and an authentication provider. Do not deploy this SQLite/local-file configuration to an ephemeral hosting filesystem or expose it publicly as-is. PostgreSQL is not yet connected to the application storage layer, so do not horizontally scale the app.

## Checks

```bash
ruff check .
pytest -q
python -m compileall -q usiphu app tests scripts
python -m usiphu.validation
```

## Release gates

- Obtain the official Suez University PHC/ped 2.3.1 course specification and any missing/current module specifications.
- Confirm the uploaded specification versions apply to the target cohort.
- Have departmental educators review the outcome crosswalk and all clinical content.
- Define authentication, backups, monitoring, privacy controls and a persistent hosting plan before inviting remote users.
- Complete security, accessibility, and user-acceptance testing.
