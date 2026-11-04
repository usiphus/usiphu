# Evidence-grounded exam-card generation

## End-to-end workflow

The generator uses a local Ollama authoring path:

1. Compile one brief per medical curriculum learning objective, retaining specialty, topic, objective level, exam weight, ILO mapping provenance and the selected exam format.
2. Load the specialty-specific assessment blueprint from `data/specialty_exam_blueprints.json`; the blueprint steers question style and safety checks but is not an approved faculty exam blueprint.
3. Search PubMed E-utilities for relevant records and retrieve citation metadata, publication types, dates, and abstracts.
4. Send the objective and bounded evidence packet to the configured local Ollama model.
5. Require claim-level PMID references and normalize all source URLs/titles/dates from retrieved records; model-invented URLs are not accepted.
6. Run the generated card through the structural, ILO, evidence-source, and duplicate validation gates.
7. Store accepted cards only in the learner-isolated `generated_drafts` table. They are not placed in the flashcard review queue and cannot self-approve.

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

- `GET /curriculum/coverage` reports topic/objective mapping status and current official outcome crosswalk coverage. `GET /content/validation` also checks that the coverage register still matches the curriculum and ILO source files.\n- `GET /generator/status` reports configured provider, endpoint, and selected model without making a live health check. A configured endpoint does not guarantee Ollama is running or that the model is present.
- `GET /generator/briefs?specialty=urology&topic=pujo` returns deterministic objective-level briefs without calling a model.
- `POST /generator/generate` accepts
  `{"specialty_id":"urology","topic_id":"pujo","evidence_limit":5,"exam_format":"osce"}`. Supported formats are `mixed`, `mcq`, `short_answer`, `clinical_case`, `osce`, `viva` and `emq`. The same `exam_format` query parameter is available on `/generator/briefs`.
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

All generated content is stored as `draft`. The automated validator requires claim-level source IDs from the retrieved evidence packet, checks permitted curriculum references, format-specific structure (including OSCE tasks/marking criteria, viva question sets and EMQ option/stem keys), MCQ option/answer-key consistency, distinct options and duplicate prompts. Every result includes a human review packet assembled from `data/clinical_exam_review_rubric.json` and the specialty safety checks. The packet is stored inside the generated draft payload and displayed in the Generator and saved-drafts views. It does **not** establish clinical truth, guideline currency, safe prescribing, distractor quality, or exam validity.

A qualified clinical educator must verify every clinical claim against the full primary source/current guideline and local Suez/Egypt protocols before a card is promoted into the learner flashcard bank. The review packet specifies general checks, assessment-format checks, specialty safety checks and required reviewer metadata. The approval gates distinguish `draft`, `needs_revision`, `clinically_reviewed` and `exam_validated`; no automated promotion is permitted. This PR does not yet implement a role-based faculty sign-off workflow.

## Curriculum coverage status

The expanded blueprint includes 27 medical disciplines, 174 topics and 291 learning objectives. The versioned coverage register has one row per topic and objective, and one row per outcome in the current 73-record official Suez course ILO catalogue. Current status: 50 direct topic links, 6 partial links, 4 external benchmark-only topics, 2 module-only topics and 112 topics without verified course-outcome mapping. Of the 73 catalogued official outcomes, 47 have topic-level links and 26 are not linked in the current crosswalk. Objective-level status is separately reported: 55 objectives have a direct topic-level link only, 6 have a partial topic-level link only, 4 are external-benchmark-only, 2 have module-only alignment and 224 have no verified mapping. No objective-level mapping has yet been individually faculty-verified. The 73-outcome extraction is first-pass and non-exhaustive; the new topics are not official Suez ILOs. The coverage validator detects missing topics/objectives, duplicate keys and invalid source references.

## Known limitations / next quality gates

1. PubMed abstracts only; add licensed/open full-text retrieval with license-aware storage and source extraction where permitted.
2. Add guideline-first retrieval and version/effective-date tracking for each specialty, with local Egyptian protocol overrides.
3. Add specialty-specific checks for medication doses, contraindications, red flags, investigation thresholds, and emergency pathways.
4. Add educator review queue, audit trail, and explicit role-based approval before any generated draft is promoted to active learner content.
5. Complete line-by-line official Suez ILO extraction, map every individual objective to specific course outcomes, and obtain the official PHC/ped 2.3.1 Pediatrics outcomes.\n6. Add a role-based faculty review queue, audit trail and controlled approval/promotion workflow.
