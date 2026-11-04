"""Tests for pilot dashboard metrics and persistent AI review history."""
import json

from usiphu.pilot_validation import build_pilot_validation_report, record_ai_review
from usiphu.source_inbox import save_source


def _seed_pilot(tmp_path):
    source_dir = tmp_path / "source-inbox"
    source = save_source(
        "pilot-paper.pdf",
        b"%PDF placeholder",
        title="Pilot paper",
        specialty="Urology",
        exam_year="2024",
        source_dir=source_dir,
    )
    extraction_dir = source_dir / "extractions"
    extraction_dir.mkdir()
    payload = {
        "source_id": source["source_id"],
        "summary": {"question_candidates": 2, "meq_page_candidates": 1},
        "mcq_candidates": [
            {
                "candidate_id": "mcq-confirmed",
                "question_type": "single_best_answer",
                "stem_extracted": "Which diagnosis?",
                "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                "answer_status": "human_verified",
                "correct_option_id": "a",
                "review_state": "reviewed_pending_approval",
                "transcription_accuracy_outcome": "confirmed_as_extracted",
                "ai_review_history": [{
                    "recorded_at": "2026-11-01T12:00:00+00:00",
                    "internet_evidence_review": {
                        "verdict": "contradicted",
                        "existing_key_assessment": "contradicted",
                        "proposed_option_id": "b",
                        "sources": [{
                            "source_id": "PMC:PMC123",
                            "source_title": "Open access study",
                            "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/",
                            "source_date": "2024-01-01",
                            "journal": "Example Journal",
                            "full_text_available": True,
                        }],
                    },
                }],
            },
            {
                "candidate_id": "mcq-corrected",
                "question_type": "single_best_answer",
                "stem_extracted": "Corrected question stem",
                "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                "answer_status": "proposed_unverified",
                "review_state": "reviewed_pending_approval",
                "transcription_accuracy_outcome": "corrected",
            },
        ],
        "meq_page_candidates": [{
            "candidate_id": "meq-1",
            "question_type": "modified_essay_question",
            "transcription_accuracy_outcome": "corrected",
            "review_state": "reviewed_pending_approval",
        }],
    }
    (extraction_dir / f"{source['source_id']}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return source_dir, source, payload


def test_report_counts_transcription_answers_and_evidence_quality(tmp_path):
    source_dir, _source, _payload = _seed_pilot(tmp_path)
    report = build_pilot_validation_report(source_dir)

    assert report["totals"]["source_files"] == 1
    assert report["totals"]["mcq_candidates"] == 2
    assert report["totals"]["meq_pages"] == 1
    assert report["totals"]["mcq_transcription_checked"] == 2
    assert report["transcription"]["mcq_confirmed_as_extracted"] == 1
    assert report["transcription"]["mcq_corrected"] == 1
    assert report["totals"]["meq_transcription_checked"] == 1
    assert report["totals"]["answer_verified"] == 1
    assert report["totals"]["ai_review_runs"] == 1
    assert report["totals"]["ai_key_contradictions"] == 1
    assert report["evidence_quality"]["full_text_articles"] == 1
    assert report["evidence_quality"]["abstract_only_articles"] == 0
    assert report["ai_evidence_verdict_counts"] == {"contradicted": 1}
    assert report["existing_key_assessment_counts"] == {"contradicted": 1}


def test_record_ai_review_appends_advisory_audit_event(tmp_path):
    source_dir, source, _payload = _seed_pilot(tmp_path)
    review = {
        "candidate_id": "mcq-corrected",
        "status": "ai_suggestion_requires_human_review",
        "official_answer_key": False,
        "transcription": {"confidence": "medium", "issues": ["Check punctuation"]},
        "answer_review": {"suggested_option_id": None, "basis": "unclear"},
        "internet_evidence_review": {
            "verdict": "insufficient_evidence",
            "existing_key_assessment": "no_existing_key",
            "proposed_option_id": None,
            "sources": [],
        },
    }
    event = record_ai_review("mcq-corrected", review, source_dir=source_dir)

    assert event["official_answer_key"] is False
    report = build_pilot_validation_report(source_dir)
    assert report["totals"]["ai_review_runs"] == 2
    assert report["ai_evidence_verdict_counts"]["insufficient_evidence"] == 1

    saved = json.loads(
        (source_dir / "extractions" / f"{source['source_id']}.json").read_text(encoding="utf-8")
    )
    candidate = next(item for item in saved["mcq_candidates"] if item["candidate_id"] == "mcq-corrected")
    assert len(candidate["ai_review_history"]) == 1
    assert candidate["ai_review_history"][0]["official_answer_key"] is False


def test_empty_inbox_returns_zeroed_report(tmp_path):
    report = build_pilot_validation_report(tmp_path)
    assert report["totals"]["source_files"] == 0
    assert report["totals"]["mcq_candidates"] == 0
    assert report["totals"]["ai_review_runs"] == 0
    assert report["transcription"]["mcq_confirmation_rate_percent"] is None
