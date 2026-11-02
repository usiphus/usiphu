# Usiphu 2.0

A local-first medical learning platform combining specialty-wide curriculum mapping, source discovery, question practice, OSCE/viva cases, spaced repetition, and learner analytics.

> **Foundation release.** The curriculum is an extensible blueprint, not a claim that every national syllabus is complete. Educational content is not a substitute for clinical supervision, current guidelines, or local protocols.

## Run locally (Python 3.11+)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
streamlit run app/Home.py
```

Optional API: `uvicorn usiphu.api:app --reload`

Checks: `pytest && ruff check .`

## Features
- Specialty → domain → topic → measurable learning objectives, with coverage metrics.
- Topic-aware discovery links for PubMed, PMC, Cureus, AnkiWeb, DoctorDE search, WHO, NICE, and Cochrane.
- MCQ and structured clinical-case practice.
- Persistent flashcards with an SM-2-inspired scheduler.
- SQLite learner progress, due reviews, and activity metrics.
- FastAPI read endpoints and a Streamlit interface.

## Project map
`app/` UI · `usiphu/` domain logic/API/storage · `data/` versioned learning content · `tests/` automated checks · `docs/` governance.

## Source and safety policy
The app links to external discovery services; it does not scrape, reproduce, or redistribute third-party decks or articles. Check licensing, authorship, publication date, and clinical applicability. PubMed is an index; PMC provides full text when available. AnkiWeb shared decks are third-party content. DoctorDE is linked via a search route pending verification of a stable official search endpoint. Local protocols and current specialty guidelines take precedence.

## Next release gates
Editorially validate each specialty against a named syllabus; add source provenance and review dates to every authored question; add authentication/sync only after privacy and security review; run accessibility, dependency, and deployment checks before production.
