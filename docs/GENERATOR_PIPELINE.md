# Exam-card generation pipeline

## Current integration boundary

The repository now includes a deterministic generation-brief builder and a strict
card-output validator. This is **not an autonomous clinical authoring model**:
no LLM/provider credentials or model adapter are configured in this project. The
runtime compiles traceable jobs that a future provider can consume and validates
its proposed output before editorial review.

## Runtime

- `usiphu.generator.build_generation_briefs()` creates one brief per curriculum
  learning objective.
- Each brief includes specialty/domain/topic IDs, objective text and level,
  exam weight, Suez course-outcome mapping status, and the matching outcome text.
- Official Suez outcomes and external pediatric benchmarks are separate fields.
  External-only pediatric mappings cannot be promoted to official Suez alignment.
- `validate_generated_card()` checks required fields, five-option MCQ structure,
  answer-key integrity, evidence claims, HTTP(S) source URLs, allowed outcome IDs,
  draft-only status, and duplicate prompts.
- `validate_generation_batch()` checks a batch and duplicates against the
  supplied existing bank.
- FastAPI exposes `GET /generator/briefs` and `POST /generator/validate`.

## API examples

```http
GET /generator/briefs?specialty=urology&topic=pujo
```

```json
{
  "cards": [
    {
      "brief_id": "urology:pujo:pujo-1",
      "id": "uro-pujo-001",
      "card_type": "mcq",
      "specialty_id": "urology",
      "topic_id": "pujo",
      "prompt": "...",
      "answer": "...",
      "options": [
        {"id": "a", "text": "..."},
        {"id": "b", "text": "..."},
        {"id": "c", "text": "..."},
        {"id": "d", "text": "..."},
        {"id": "e", "text": "..."}
      ],
      "correct_option_id": "b",
      "source_title": "...",
      "source_url": "https://...",
      "source_date": "YYYY-MM-DD",
      "course_outcome_refs": ["SI-URO-01"],
      "evidence_claims": [
        {"claim": "...", "source_url": "https://..."}
      ],
      "review_status": "draft"
    }
  ]
}
```

Submit that object to `POST /generator/validate`. The response reports accepted
drafts and rejected outputs; it never grants clinical approval or exam validation.

## Quality and safety gates

- Unknown topic/ILO references fail closed.
- Each generated card must match its originating brief's specialty and topic.
- Each card must cite a named, dated source and provide claim-level evidence links.
- MCQs require exactly five options with unique IDs and a valid correct-option ID.
- Duplicate normalized prompts are rejected within the batch and against supplied
  existing cards.
- External benchmark-only topics retain that status and cannot claim official
  Suez outcome alignment.
- No generated content can self-assign a clinically reviewed or exam-validated
  status. Those statuses require the existing editorial workflow and metadata.

## Known limitations / next engineering gate

1. Connect a selected LLM provider through a separately configured adapter; do not
   embed API keys in source code or commit them.
2. Add evidence retrieval and source-quality ranking before model generation.
3. Add specialty-specific clinical validation rules, guideline-version checks,
   contraindication/dose checks, and educator sign-off workflows.
4. The current validator checks provenance structure, not the truth of clinical
   claims. Passing validation is not proof of clinical correctness.
5. Current Suez ILO extraction is grouped and non-exhaustive; pediatric outcomes
   are external benchmarks only. Keep those limitations visible in generated cards.
