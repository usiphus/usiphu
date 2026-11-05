"""Pilot validation metrics and durable audit records for source-question review."""
from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from usiphu.durable_documents import save_json_document
from usiphu.source_inbox import DEFAULT_SOURCE_DIR, list_extractions, list_sources, write_extraction


def _read_extractions(source_dir: Path) -> list[dict[str, Any]]:
    return [payload for _source, payload in list_extractions(source_dir)]


def record_ai_review(
    candidate_id: str,
    review: dict[str, Any],
    *,
    source_dir: Path = DEFAULT_SOURCE_DIR,
) -> dict[str, Any]:
    """Persist an AI review as an advisory audit event on its source candidate."""
    for source, payload in list_extractions(source_dir):
        for collection in ("mcq_candidates", "meq_page_candidates"):
            for item in payload.get(collection, []):
                if item.get("candidate_id") != candidate_id:
                    continue
                if review.get("candidate_id") not in {None, candidate_id}:
                    raise ValueError("AI review candidate ID does not match the selected question.")
                history = item.setdefault("ai_review_history", [])
                event = {
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "status": review.get("status", "ai_suggestion_requires_human_review"),
                    "official_answer_key": False,
                    "transcription": review.get("transcription", {}),
                    "answer_review": review.get("answer_review", {}),
                    "internet_evidence_review": review.get("internet_evidence_review", {}),
                }
                history.append(event)
                item["latest_ai_review_at"] = event["recorded_at"]
                write_extraction(source["source_id"], payload, source_dir)
                return event
    raise KeyError(f"Unknown extracted candidate: {candidate_id}")



def save_pilot_validation_report(
    report: dict | None = None,
    source_dir: Path = DEFAULT_SOURCE_DIR,
) -> dict[str, str]:
    """Persist the latest report and an immutable timestamped report snapshot."""
    payload = report or build_pilot_validation_report(source_dir)
    generated_at = str(payload.get("generated_at") or datetime.now(UTC).isoformat())
    stamp = re.sub(r"[^0-9A-Za-z_-]", "-", generated_at)
    latest_path = source_dir / "reports" / "pilot-validation" / "latest.json
    archive_path = source_dir / "reports" / "pilot-validation" / f"{stamp}.json"
    save_json_document("reports/pilot-validation/latest.json", payload, latest_path)
    save_json_document(f"reports/pilot-validation/{stamp}.json", payload, archive_path)
    return {
        "latest": "reports/pilot-validation/latest.json",
        "archive": f"reports/pilot-validation/{stamp}.json",
    }


def build_pilot_validation_report(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    *,
    mcq_review_target: int = 50,
    meq_review_target: int = 10,
) -> dict[str, Any]:
    """Summarize extraction, reviewer corrections, answer checks and evidence quality."""
    sources = list_sources(source_dir)
    extractions = _read_extractions(source_dir)
    mcqs: list[dict[str, Any]] = []
    short_answers: list[dict[str, Any]] = []
    meqs: list[dict[str, Any]] = []
    source_mcq_counts: Counter[str] = Counter()
    source_meq_counts: Counter[str] = Counter()
    for payload in extractions:
        source_id = str(payload.get("source_id", ""))
        for item in payload.get("mcq_candidates", []):
            row = {**item, "source_id": source_id}
            if item.get("question_type") == "single_best_answer":
                mcqs.append(row)
                source_mcq_counts[source_id] += 1
            else:
                short_answers.append(row)
        for item in payload.get("meq_page_candidates", []):
            meqs.append({**item, "source_id": source_id})
            source_meq_counts[source_id] += 1

    all_written = [*short_answers, *meqs]
    checked_mcqs = [
        item for item in mcqs
        if item.get("transcription_accuracy_outcome") in {"confirmed_as_extracted", "corrected"}
    ]
    checked_written = [
        item for item in all_written
        if item.get("transcription_accuracy_outcome") in {"confirmed_as_extracted", "corrected"}
    ]
    mcq_confirmed = sum(item.get("transcription_accuracy_outcome") == "confirmed_as_extracted" for item in checked_mcqs)
    mcq_corrected = sum(item.get("transcription_accuracy_outcome") == "corrected" for item in checked_mcqs)
    written_confirmed = sum(item.get("transcription_accuracy_outcome") == "confirmed_as_extracted" for item in checked_written)
    written_corrected = sum(item.get("transcription_accuracy_outcome") == "corrected" for item in checked_written)

    answer_status = Counter(str(item.get("answer_status", "not_extracted_or_verified")) for item in mcqs)
    review_states = Counter(str(item.get("review_state", "pending")) for item in [*mcqs, *all_written])
    ai_events = [
        event
        for item in mcqs
        for event in item.get("ai_review_history", [])
        if isinstance(event, dict)
    ]
    latest_reviews = [
        item.get("ai_review_history", [])[-1]
        for item in mcqs
        if item.get("ai_review_history")
    ]
    verdict_counts = Counter(
        str(event.get("internet_evidence_review", {}).get("verdict", "unavailable"))
        for event in ai_events
    )
    key_assessments = Counter(
        str(event.get("internet_evidence_review", {}).get("existing_key_assessment", "not_assessed"))
        for event in ai_events
    )
    key_contradictions = sum(
        event.get("internet_evidence_review", {}).get("existing_key_assessment") == "contradicted"
        for event in ai_events
    )
    ai_proposals = [
        event.get("internet_evidence_review", {}).get("proposed_option_id")
        for event in ai_events
        if event.get("internet_evidence_review", {}).get("proposed_option_id")
    ]
    reviewer_ai_comparisons = [
        item["reviewer_ai_comparison"]
        for item in mcqs
        if isinstance(item.get("reviewer_ai_comparison"), dict)
        and item["reviewer_ai_comparison"].get("reviewer_answer_verified")
        and item["reviewer_ai_comparison"].get("ai_proposed_option_id")
    ]
    reviewer_ai_agreements = sum(
        item.get("reviewer_matches_ai_proposal") is True for item in reviewer_ai_comparisons
    )
    reviewer_ai_disagreements = sum(
        item.get("reviewer_matches_ai_proposal") is False for item in reviewer_ai_comparisons
    )
    evidence_references_count = sum(
        len(event.get("internet_evidence_review", {}).get("sources", []))
        for event in ai_events
    )
    source_index: dict[str, dict[str, Any]] = {}
    for event in ai_events:
        evidence = event.get("internet_evidence_review", {})
        for source in evidence.get("sources", []):
            if isinstance(source, dict) and source.get("source_id"):
                source_index[source["source_id"]] = source
    evidence_sources = list(source_index.values())
    full_text_sources = sum(bool(item.get("full_text_available")) for item in evidence_sources)
    abstract_only_sources = len(evidence_sources) - full_text_sources
    metadata_complete = sum(
        bool(item.get("source_title") and item.get("source_url") and item.get("source_date") and item.get("journal"))
        for item in evidence_sources
    )
    dated_sources = sum(bool(item.get("source_date")) for item in evidence_sources)
    answer_verified = answer_status.get("human_verified", 0)
    source_lookup = {str(item.get("source_id", "")): item for item in sources}
    candidate_rows = []
    for item in [*mcqs, *short_answers, *meqs]:
        history = item.get("ai_review_history", [])
        latest = history[-1] if history else {}
        internet = latest.get("internet_evidence_review", {})
        source = source_lookup.get(str(item.get("source_id", "")), {})
        candidate_rows.append({
            "candidate_id": item.get("candidate_id"),
            "source": source.get("title") or source.get("original_filename") or item.get("source_id"),
            "page": item.get("source_page"),
            "page_end": item.get("source_page_end", item.get("source_page")),
            "type": (
                "MCQ" if item.get("question_type") == "single_best_answer"
                else "MEQ page" if item.get("question_type") == "modified_essay_question"
                else "Short answer"
            ),
            "review_state": item.get("review_state", "pending"),
            "transcription_outcome": item.get("transcription_accuracy_outcome", "not_checked"),
            "answer_status": item.get("answer_status", "not_extracted_or_verified"),
            "AI_evidence_verdict": internet.get("verdict", "not_reviewed"),
            "AI_existing_key_assessment": internet.get("existing_key_assessment", "not_assessed"),
            "AI_proposed_option": internet.get("proposed_option_id"),
            "human_selected_option": item.get("correct_option_id"),
            "reviewer": item.get("reviewer") or item.get("transcription_reviewed_by"),
        })

    source_rows = []
    for source in sources:
        source_id = str(source.get("source_id", ""))
        candidates_for_source = [
            item for item in [*mcqs, *short_answers, *meqs] if item.get("source_id") == source_id
        ]
        ai_count = sum(len(item.get("ai_review_history", [])) for item in candidates_for_source)
        source_ai_ids = {
            ref.get("source_id")
            for item in candidates_for_source
            for event in item.get("ai_review_history", [])
            for ref in event.get("internet_evidence_review", {}).get("sources", [])
            if ref.get("source_id")
        }
        source_rows.append({
            "source_id": source_id,
            "title": source.get("title") or source.get("original_filename"),
            "filename": source.get("original_filename"),
            "specialty": source.get("specialty", "Unassigned"),
            "exam_year": source.get("exam_year", ""),
            "status": source.get("status", "unknown"),
            "mcq_candidates": source_mcq_counts[source_id],
            "short_answer_candidates": sum(item.get("source_id") == source_id for item in short_answers),
            "meq_pages": source_meq_counts[source_id],
            "transcription_checked": sum(
                item.get("transcription_accuracy_outcome") in {"confirmed_as_extracted", "corrected"}
                for item in candidates_for_source
            ),
            "transcription_corrections": sum(
                item.get("transcription_accuracy_outcome") == "corrected"
                for item in candidates_for_source
            ),
            "human_verified_answers": sum(
                item.get("answer_status") == "human_verified"
                for item in candidates_for_source
            ),
            "ai_review_runs": ai_count,
            "evidence_articles": len(source_ai_ids),
        })

    total_mcq_checked = len(checked_mcqs)
    total_written_checked = len(checked_written)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "targets": {"mcq_review_target": mcq_review_target, "meq_review_target": meq_review_target},
        "totals": {
            "source_files": len(sources),
            "extracted_sources": sum(bool(item.get("summary")) for item in extractions),
            "mcq_candidates": len(mcqs),
            "short_answer_candidates": len(short_answers),
            "meq_pages": len(meqs),
            "transcription_checked": total_mcq_checked + total_written_checked,
            "mcq_transcription_checked": total_mcq_checked,
            "meq_transcription_checked": sum(
                item.get("transcription_accuracy_outcome") in {"confirmed_as_extracted", "corrected"}
                for item in meqs
            ),
            "answer_verified": answer_verified,
            "reviewed_pending_approval": review_states.get("reviewed_pending_approval", 0),
            "approved_candidates": review_states.get("approved", 0),
            "ai_review_runs": len(ai_events),
            "ai_candidates_reviewed": len(latest_reviews),
            "ai_key_contradictions": key_contradictions,
            "reviewer_ai_comparisons": len(reviewer_ai_comparisons),
            "reviewer_ai_agreements": reviewer_ai_agreements,
            "reviewer_ai_disagreements": reviewer_ai_disagreements,
            "evidence_articles": len(evidence_sources),
            "full_text_articles": full_text_sources,
            "abstract_only_articles": abstract_only_sources,
            "evidence_metadata_complete": metadata_complete,
            "evidence_dated": dated_sources,
        },
        "transcription": {
            "mcq_checked": total_mcq_checked,
            "mcq_confirmed_as_extracted": mcq_confirmed,
            "mcq_corrected": mcq_corrected,
            "written_checked": total_written_checked,
            "written_confirmed_as_extracted": written_confirmed,
            "written_corrected": written_corrected,
            "mcq_confirmation_rate_percent": round(100 * mcq_confirmed / total_mcq_checked, 1) if total_mcq_checked else None,
            "written_confirmation_rate_percent": round(100 * written_confirmed / total_written_checked, 1) if total_written_checked else None,
        },
        "answer_status_counts": dict(answer_status),
        "ai_evidence_verdict_counts": dict(verdict_counts),
        "existing_key_assessment_counts": dict(key_assessments),
        "ai_proposed_options_count": len(ai_proposals),
        "evidence_quality": {
            "unique_articles": len(evidence_sources),
            "full_text_articles": full_text_sources,
            "abstract_only_articles": abstract_only_sources,
            "full_text_percent": round(100 * full_text_sources / len(evidence_sources), 1) if evidence_sources else None,
            "metadata_complete_articles": metadata_complete,
            "dated_articles": dated_sources,
            "mean_articles_per_ai_review": round(evidence_references_count / len(ai_events), 2) if ai_events else 0,
            "interpretation": (
                "Metadata and full-text availability indicators only; they do not establish study quality, "
                "clinical relevance, guideline status or certainty of evidence."
            ),
        },
        "source_rows": source_rows,
        "candidate_rows": candidate_rows,
        "limitations": [
            "Transcription confirmation rates describe only items explicitly saved after human comparison; they are not automatic OCR accuracy estimates.",
            "Question segmentation and page grouping require separate manual validation; a page-level MEQ candidate is not necessarily a complete MEQ.",
            "Answer-key outcomes count reviewer attestations and advisory AI evidence verdicts; they do not independently establish medical correctness.",
            "Evidence source counts measure retrieved records, not evidence quality. Abstract-only sources are not equivalent to full-text evidence.",
            "The current pilot does not automatically inspect rendered PDF page images or perform OCR on scanned papers.",
        ],
    }
