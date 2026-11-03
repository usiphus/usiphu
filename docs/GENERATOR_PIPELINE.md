# Evidence-grounded exam-card generation

## End-to-end workflow

The generator uses a local Ollama authoring path:

1. Compile one brief per Suez curriculum learning objective, retaining specialty, topic, objective level, exam weight, and ILO mapping provenance.
2. Search PubMed E-utilities for relevant records and retrieve citation metadata, publication types, dates, and abstracts.
3. Send the objective and bounded evidence packet to the configured local Ollama model.
4. Require claim-level PMID references and normalize all source URLs/titles/dates from retrieved records; model-invented URLs are not accepted.
5. Run the generated card through the structural, ILO, evidence-source, and duplicate validation gates.
6. Store accepted cards only in the learner-isolated `generated_drafts` table. They are not placed in the flashcard review queue and cannot self-approve.

## Local setup

Install [Ollama](https://ollama.com), start its service, and pull a model:

```bash
ollama pull qwen2.5:7b
```

Configure the app process:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export USIPHU_OLLAMA_MODEL=qwen2.5:7b
streamlit run app/Home.py
```

The default model is `qwen2.5:7b`. Choose another model only after pulling it locally and setting `USIPHU_OLLAMA_MODEL` to its exact Ollama tag. No OpenAI SDK, API key, or paid model API is used. The first pull requires internet access and several GB of storage. Model loading and generation can be slow on CPU-only or low-memory devices.

## Docker Compose

1. Copy `.env.example` to `.env`.
2. Optionally change `USIPHU_OLLAMA_MODEL` in `.env`.
3. Start the stack: `docker compose up --build -d`.
4. Pull the configured model into the persistent Ollama volume:
   `docker compose exec ollama ollama pull qwen2.5:7b`
5. Open the Usiphu Streamlit app on port 8501.

Compose connects the app to Ollama at `http://ollama:11434` on its private network. Ollama's host port is bound to `127.0.0.1:11434`, not exposed to other LAN devices. The model volume persists across container restarts. The model is not downloaded automatically when the stack starts. If you change the model tag, pull that exact tag in the Ollama container. When running the app inside a container but Ollama on the host, do not use `localhost`; configure a host-reachable address (for example, `host.docker.internal` where supported).

For production, operate Ollama on a protected private network or the same host. Do not expose its unauthenticated API directly to the public internet. Use suitable CPU/GPU resources and monitor disk usage.

Optional `NCBI_EMAIL` and `NCBI_API_KEY` settings support PubMed E-utilities contact and higher request limits. PubMed retrieval requires outbound HTTPS to `eutils.ncbi.nlm.nih.gov`.

## Runtime/API

- `GET /generator/status` reports configured provider, endpoint, and selected model without making a live health check. A configured endpoint does not guarantee Ollama is running or that the model is present.
- `GET /generator/briefs?specialty=urology&topic=pujo` returns deterministic objective-level briefs without calling a model.
- `POST /generator/generate` accepts
  `{"specialty_id":"urology","topic_id":"pujo","evidence_limit":5}`.
  It retrieves PubMed records and returns generated draft cards plus evidence-gated or quality-rejected objective results.
- `POST /generator/validate` validates externally authored cards against briefs.

The Streamlit Generator tab offers the same flow and can persist accepted outputs as drafts. The app labels them as drafts and keeps them outside the approved flashcard queue.

## Evidence handling

- PubMed is the first retrieval adapter. Records without an abstract are excluded.
- Each evidence record retains PMID, stable PubMed URL, title, journal, publication date, DOI when available, publication types, and a conservative article-type tier.
- The model receives abstracts, not verified full text. It must not infer details unavailable in the abstract.
- Each generated claim must cite a source ID from the retrieved packet. Source titles, dates, and URLs are copied from the retrieved record, not model output.
- No-result retrieval returns `needs_evidence_review`; it does not fabricate a card.
- A PubMed record is not automatically a high-quality or current guideline. Check publication status, methods, population, full text, currency, and applicability.

## Curriculum alignment

- Official Suez outcomes and external pediatric benchmarks remain separate.
- External-only pediatric topics cannot claim official Suez alignment.
- Topics with partial or module-only mappings retain those statuses.
- The supplied ILO extraction is grouped and non-exhaustive. Generated cards must not imply the catalog is a complete transcription of the official course files.

## Review and safety

All generated content is stored as `draft`. The automated validator checks format, source traceability, allowed ILO references, MCQ option/answer-key consistency, and duplicate prompts. It does **not** establish clinical truth, guideline currency, safe prescribing, or exam validity.

A qualified clinical educator must verify every clinical claim against the full primary source/current guideline and local Suez/Egypt protocols before a card is promoted into the learner flashcard bank. This PR does not implement automated approval or a faculty sign-off workflow.

## Known limitations / next quality gates

1. PubMed abstracts only; add licensed/open full-text retrieval with license-aware storage and source extraction where permitted.
2. Add guideline-first retrieval and version/effective-date tracking for each specialty, with local Egyptian protocol overrides.
3. Add specialty-specific checks for medication doses, contraindications, red flags, investigation thresholds, and emergency pathways.
4. Add educator review queue, audit trail, and explicit role-based approval before any generated draft is promoted to active learner content.
5. Complete line-by-line official Suez ILO extraction and obtain the official PHC/ped 2.3.1 Pediatrics outcomes.
