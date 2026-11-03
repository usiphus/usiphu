# Evidence-grounded exam-card generation

## End-to-end workflow

The generator now has a configurable authoring path:

1. Compile one brief per Suez curriculum learning objective, retaining specialty,
   topic, objective level, exam weight, and ILO mapping provenance.
2. Search PubMed E-utilities for relevant records and retrieve citation metadata,
   publication types, dates, and abstracts.
3. Send the objective and bounded evidence packet to the configured OpenAI model.
4. Require claim-level PMID references and normalize all source URLs/titles/dates
   from retrieved records; model-invented URLs are not accepted.
5. Run the generated card through the structural, ILO, evidence-source, and
   duplicate validation gates.
6. Store accepted cards only in the learner-isolated `generated_drafts` table.
   They are not placed in the flashcard review queue and cannot self-approve.

## Configuration

The OpenAI key is a server-side secret. Never paste it into the Streamlit UI, a
source file, a Docker image, or a committed `.env` file.

For local Docker Compose:

1. Copy `.env.example` to `.env`.
2. Set `OPENAI_API_KEY` in `.env`.
3. Optionally set `USIPHU_OPENAI_MODEL` (defaults to `gpt-4.1-mini`).
4. Optionally set `NCBI_EMAIL` and `NCBI_API_KEY` for PubMed E-utilities contact
   and higher NCBI request limits.
5. Start or rebuild with `docker compose up --build -d`.

For production, inject `OPENAI_API_KEY` and optional NCBI settings using the
deployment platform's secret manager/environment configuration. Do not mount
the key into the browser or expose it through Streamlit configuration.

The OpenAI SDK is installed with the application dependencies. PubMed retrieval
uses Python's standard library and requires outbound HTTPS access to
`eutils.ncbi.nlm.nih.gov`.

## Runtime/API

- `GET /generator/status` reports whether the key is configured and which model
  name is selected; it never returns the key.
- `GET /generator/briefs?specialty=urology&topic=pujo` returns deterministic
  objective-level briefs without calling a model.
- `POST /generator/generate` accepts
  `{"specialty_id":"urology","topic_id":"pujo","evidence_limit":5}`.
  It retrieves PubMed records and returns generated draft cards plus evidence-gated
  or quality-rejected objective results.
- `POST /generator/validate` validates externally authored cards against briefs.

The Streamlit Generator tab offers the same flow and can persist accepted outputs
as drafts. The app labels them as drafts and keeps them outside the approved
flashcard queue.

## Evidence handling

- PubMed is the first retrieval adapter. Records without an abstract are excluded.
- Each evidence record retains PMID, stable PubMed URL, title, journal, publication
  date, DOI when available, publication types, and a conservative article-type tier.
- The model receives abstracts, not verified full text. It must not infer details
  unavailable in the abstract.
- Each generated claim must cite a source ID from the retrieved packet. Source
  titles, dates, and URLs are copied from the retrieved record, not model output.
- No-result retrieval returns `needs_evidence_review`; it does not fabricate a card.
- A PubMed record is not automatically a high-quality or current guideline. Check
  publication status, methods, population, full text, currency, and applicability.

## Curriculum alignment

- Official Suez outcomes and external pediatric benchmarks remain separate.
- External-only pediatric topics cannot claim official Suez alignment.
- Topics with partial or module-only mappings retain those statuses.
- The supplied ILO extraction is grouped and non-exhaustive. Generated cards must
  not imply the catalog is a complete transcription of the official course files.

## Review and safety

All generated content is stored as `draft`. The automated validator checks format,
source traceability, allowed ILO references, MCQ option/answer-key consistency,
and duplicate prompts. It does **not** establish clinical truth, guideline
currency, safe prescribing, or exam validity.

A qualified clinical educator must verify every clinical claim against the full
primary source/current guideline and local Suez/Egypt protocols before a card is
promoted into the learner flashcard bank. This PR does not implement automated
approval or a faculty sign-off workflow.

## Known limitations / next quality gates

1. PubMed abstracts only; add licensed/open full-text retrieval with license-aware
   storage and source extraction where permitted.
2. Add guideline-first retrieval and version/effective-date tracking for each
   specialty, with local Egyptian protocol overrides.
3. Add specialty-specific checks for medication doses, contraindications,
   red flags, investigation thresholds, and emergency pathways.
4. Add educator review queue, audit trail, and explicit role-based approval before
   any generated draft is promoted to active learner content.
5. Complete line-by-line official Suez ILO extraction and obtain the official
   PHC/ped 2.3.1 Pediatrics outcomes.
