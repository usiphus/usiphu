# Installable question banks

Usiphu loads the three starter questions from `data/questions.json`, then merges every `.json` file in this directory. Each question ID must be unique across all banks.

A bank file can be a JSON array of MCQ objects, or an object with this shape:

```json
{
  "bank_id": "urology-department-bank",
  "title": "Urology Department Question Bank",
  "questions": [
    {
      "id": "uro-dept-0001",
      "specialty_id": "urology",
      "topic_id": "retention",
      "stem": "Question stem",
      "options": [
        {"id": "a", "text": "Option A"},
        {"id": "b", "text": "Option B"}
      ],
      "correct_option_id": "a",
      "explanation": "Why the answer is correct and why key alternatives are less suitable.",
      "difficulty": "moderate",
      "question_type": "single_best_answer",
      "tags": ["emergency", "urology"],
      "source_url": "https://example.org/source",
      "source_title": "Source title",
      "jurisdiction": "Egypt",
      "review_status": "draft"
    }
  ]
}
```

Items default to editorial draft status. Do not mark questions clinically reviewed or exam validated without an identified qualified reviewer, review date, evidence source and appropriate departmental sign-off. Preserve source attribution and licence conditions; do not upload commercial question-bank dumps without permission.

See `data/question_bank_manifest.json` for the supported item types, validation requirements and current bank status.


## Uploading source papers from the USIPHU app

Open **Question Bank → Add examination papers and question sources** to add papers as you find them. The upload inbox accepts PDF, DOCX, DOC, TXT, PNG and JPG files (up to 50 MB each), records their original filename, title, specialty, exam year, notes, upload date and SHA-256 fingerprint, and rejects duplicate files.

Uploads are stored separately from the question JSON banks in `data/source_inbox/` by default. Set `USIPHU_SOURCE_DIR` to a persistent mounted directory in hosted deployments; otherwise files may be lost when an ephemeral app container is rebuilt. Uploaded documents remain in `awaiting_extraction` status: saving a paper does not automatically create questions or approve any answer. Extracted questions must retain source/page provenance and remain drafts until human review.
