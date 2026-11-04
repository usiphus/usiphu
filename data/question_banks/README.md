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

Uploads are stored separately from the question JSON banks in `data/source_inbox/` by default. The inbox is stored on the computer running USIPHU. Set `USIPHU_SOURCE_DIR` to another persistent local directory if you want to move it away from the default project folder. Back it up regularly. On upload, USIPHU automatically extracts selectable text from PDF, DOCX and TXT files and segments likely MCQ/MEQ candidates into `data/source_inbox/extractions/<source_id>.json`. The app also provides a retry action and a JSON download for review. Scanned PDFs and image files need OCR/manual extraction; legacy DOC files are stored but are not automatically parsed. Extraction is a first-pass transcription only: it does not infer answer keys or explanations, does not guarantee perfect question boundaries, and does not add candidates to the practice bank until a human has checked and curated them. All extracted candidates remain unreviewed; clinical review and local faculty/exam validation are required before promotion.


## Reviewing and promoting extracted questions

The Question Bank workspace includes a **Review and approve extracted questions** section. It lists complete single-best-answer MCQ candidates from the source inbox. Reviewers can correct the stem and options, assign a curriculum specialty and topic, set difficulty, select a verified answer, add a rationale and identify themselves.

Saving review edits does not add a question to the practice bank. Promotion requires a reviewer identifier, a selected answer, an explanation and an explicit attestation that the answer was independently checked against the source or a reliable reference. Promoted questions are written to `data/question_banks/past_papers_reviewed.json`, which is loaded automatically by the question-bank loader. The source page and source ID are retained.

**Promotion is not clinical approval.** Imported questions remain `review_status: "draft"` until a qualified clinical reviewer performs the appropriate review and sign-off. The UI does not automatically set `clinically_reviewed` or `exam_validated`. Incomplete MCQs, short-answer candidates and MEQ pages are not yet supported by this MCQ approval flow and remain in the extraction files for a later dedicated editor.


When OIDC authentication is enabled, only identities whose OIDC `sub` value appears in the comma-separated `USIPHU_REVIEWER_SUBJECTS` environment variable can save review edits or promote questions. In local single-learner mode, review is available to the local operator. Configure this allowlist before enabling shared question review in a multi-user deployment.


## Dedicated written-question review and answer checking

Use **Review Editor** in the sidebar to check extracted MCQs, short-answer candidates and MEQ page candidates separately from the learner-facing bank. The editor displays the first extracted text and source page, and lets the reviewer download the original uploaded paper for side-by-side checking. MCQ stems and options can be corrected; the first machine-extracted stem/options are retained as an audit baseline, while the raw source transcription is never overwritten. Written-question reviewers can save a corrected source transcription while retaining the original extracted text. All corrections record reviewer and review timestamps.

For MCQs, the optional **AI check extraction and suggest an answer** action compares the parsed stem/options with the source text extracted from the uploaded file, identifies possible parser/transcription mismatches, and suggests a corrected transcription. It also proposes a possible answer and rationale. A suggestion based on clinical reasoning is not an official past-paper answer key; the AI only labels a key as explicitly printed when it can quote evidence from the extracted source text. The reviewer must inspect the original paper and independently verify the clinical answer before selecting the key and approving. AI suggestions are never automatically applied or trusted.

Short-answer and MEQ items can be split into answer parts, mapped to a curriculum specialty/topic, and given a reviewer-authored marking rubric. Each rubric point records a description, acceptable phrases/variants and marks available. Approved written assessments are stored in `data/question_banks/reviewed_assessments.json` with source/page provenance and remain editorial drafts.

The learner Practice page includes short-answer and MEQ practice for those assessments. MCQ marking compares the learner's selected option with the stored option key. Draft keys are explicitly labelled provisional; only clinically reviewed or exam-validated keys are presented as trusted marking keys.

Written-answer marking is a conservative keyword/rubric screen: it awards points when reviewer-defined acceptable phrases are found. It does not understand clinical semantics, so equivalent wording can be missed. Unmatched points are flagged for manual review, and every written-answer score is labelled provisional. It is a study aid, not an official examination mark. Reviewers must check the source and rubric before approval; no answer or rubric is generated or inferred from highlighting. An optional **AI-assisted rubric review** is also available in Practice when the local Ollama provider is configured. It evaluates clinical meaning against the fixed reviewer-authored rubric and returns per-point suggested marks, reasons, answer evidence and uncertainty. The response is structurally checked so it cannot add rubric points or exceed their mark limits. AI suggestions remain provisional, are not written to official results, and always require human examiner review. This is an educational aid, not a validated clinical examiner.
