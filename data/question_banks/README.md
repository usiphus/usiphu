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

Uploads are stored separately from the question JSON banks in `data/source_inbox/` by default. Set `USIPHU_SOURCE_DIR` to a persistent mounted directory in hosted deployments; otherwise files may be lost when an ephemeral app container is rebuilt. On upload, USIPHU automatically extracts selectable text from PDF, DOCX and TXT files and segments likely MCQ/MEQ candidates into `data/source_inbox/extractions/<source_id>.json`. The app also provides a retry action and a JSON download for review. Scanned PDFs and image files need OCR/manual extraction; legacy DOC files are stored but are not automatically parsed. Extraction is a first-pass transcription only: it does not infer answer keys or explanations, does not guarantee perfect question boundaries, and does not add candidates to the practice bank until a human has checked and curated them. All extracted candidates remain unreviewed; clinical review and local faculty/exam validation are required before promotion.


## Reviewing and promoting extracted questions

The Question Bank workspace includes a **Review and approve extracted questions** section. It lists complete single-best-answer MCQ candidates from the source inbox. Reviewers can correct the stem and options, assign a curriculum specialty and topic, set difficulty, select a verified answer, add a rationale and identify themselves.

Saving review edits does not add a question to the practice bank. Promotion requires a reviewer identifier, a selected answer, an explanation and an explicit attestation that the answer was independently checked against the source or a reliable reference. Promoted questions are written to `data/question_banks/past_papers_reviewed.json`, which is loaded automatically by the question-bank loader. The source page and source ID are retained.

**Promotion is not clinical approval.** Imported questions remain `review_status: "draft"` until a qualified clinical reviewer performs the appropriate review and sign-off. The UI does not automatically set `clinically_reviewed` or `exam_validated`. Incomplete MCQs, short-answer candidates and MEQ pages are not yet supported by this MCQ approval flow and remain in the extraction files for a later dedicated editor.


When OIDC authentication is enabled, only identities whose OIDC `sub` value appears in the comma-separated `USIPHU_REVIEWER_SUBJECTS` environment variable can save review edits or promote questions. In local single-learner mode, review is available to the local operator. Configure this allowlist before enabling shared question review in a multi-user deployment.
