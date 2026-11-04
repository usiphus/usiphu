# USIPHU past-paper pilot validation

The **Pilot Dashboard** summarizes the actual workflow records created by Source Inbox, extraction, Review Editor and AI open-access evidence comparison.

## Suggested pilot

Start with the first 50 MCQ candidates and 10 MEQ page candidates from the supplied past papers. Review them against the original PDF, not only the extracted text.

For each MCQ:
1. Compare the stem and every option with the rendered original paper.
2. Save the transcription as confirmed unchanged or correct the transcription in Review Editor.
3. Run the open-access evidence comparison when relevant sources can be retrieved.
4. Compare the existing paper key with the evidence and inspect each source.
5. Independently verify the answer and rationale against current clinical references before marking the answer key verified.
6. Record the reviewer and only approve a complete item after all checks.

For each MEQ page:
1. Check the page against the original PDF and correct the source transcription.
2. Determine whether it is a complete MEQ, a continuation page, an answer page or unrelated material.
3. Build and independently verify the assessment rubric before approval.

## What the dashboard reports

- Source files, extraction status and candidate counts by paper.
- MCQ and MEQ transcription checks saved by a human reviewer.
- Number of transcriptions confirmed unchanged versus corrected.
- Reviewer-attested answer keys and pending/approved review states.
- Persisted AI evidence-review runs, including supported/contradicted/mixed/insufficient verdicts and assessments of existing paper keys.
- Retrieved article metadata completeness, publication-date availability, and full-text versus abstract-only records.

The AI review result is saved as an advisory audit event on the extracted candidate. It is never promoted into an official answer key. Re-running AI review appends another event, so the history remains available for audit.

## Interpretation safeguards

- Transcription confirmation rates are calculated only for candidates whose human review was saved. They are not automatic extraction accuracy estimates.
- A correction count shows that a reviewer changed the text, not whether every corrected character is now correct.
- Page-level MEQ candidates may be continuations or answers; they are not assumed to be complete questions.
- Answer-key verification is a human attestation. The dashboard does not independently prove medical correctness.
- AI evidence verdicts are advisory. Retrieved article counts and metadata completeness do not establish study quality, guideline status, clinical relevance or certainty.
- Abstract-only records are not equivalent to full-text sources.
- Current extraction does not OCR scanned papers or inspect rendered PDF page images. Those require a separate OCR/visual validation step.
- Do not use pilot results as proof of clinical safety or as an automated exam marking standard.

## Pilot acceptance gates (proposed)

Before expanding beyond the pilot sample:
- Every sampled MCQ and MEQ page has a recorded human transcription check.
- Every corrected transcription is checked again against the original page.
- Every answer key used for learner scoring has an identified reviewer and documented rationale.
- AI-suggested answers are checked against source quotations and current specialty guidelines; contradictions are resolved by a qualified reviewer.
- Source citations open successfully and match the cited claim.
- Scanned pages, missing options, ambiguous questions and MEQ continuations are visibly flagged rather than silently accepted.

The dashboard measures recorded progress toward these gates; it does not automatically certify that the gates have been met.
