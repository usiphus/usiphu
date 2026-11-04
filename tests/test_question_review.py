"""Tests for human review and promotion of extracted past-paper questions."""
import json

import pytest

from usiphu.question_review import approve_candidate, save_candidate_review
from usiphu.source_inbox import save_source


def _candidate_in_inbox(source_dir):
    source = save_source(
        "urology-paper.txt",
        b"1) Which diagnosis is most likely?\nA. Option one\nB. Option two\nC. Option three\n",
        specialty="Urology",
        source_dir=source_dir,
    )
    extraction_dir = source_dir / "extractions"
    extraction_dir.mkdir()
    payload = {
        "source_id": source["source_id"],
        "source_title": "Urology paper",
        "source_filename": "urology-paper.txt",
        "mcq_candidates": [{
            "candidate_id": "candidate-001",
            "source_id": source["source_id"],
            "source_page": 2,
            "question_type": "single_best_answer",
            "stem_extracted": "Which diagnosis is most likely?",
            "raw_text": "Which diagnosis is most likely?",
            "options": [
                {"id": "a", "text": "Option one"},
                {"id": "b", "text": "Option two"},
                {"id": "c", "text": "Option three"},
            ],
            "correct_option_id": None,
            "explanation": None,
            "answer_status": "not_extracted_or_verified",
        }],
    }
    (extraction_dir / f"{source['source_id']}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return source, payload


def test_review_draft_does_not_promote_question(tmp_path):
    source_dir = tmp_path / "inbox"
    _source, _payload = _candidate_in_inbox(source_dir)
    reviewed = save_candidate_review(
        "candidate-001",
        stem="Which diagnosis is most likely?",
        options=[
            {"id": "a", "text": "Option one"},
            {"id": "b", "text": "Option two"},
            {"id": "c", "text": "Option three"},
        ],
        specialty_id="urology",
        topic_id="rcc",
        correct_option_id="b",
        explanation="Rationale verified against the cited teaching source.",
        reviewer="Reviewer A",
        answer_verified=True,
        source_dir=source_dir,
    )
    assert reviewed["review_state"] == "reviewed_pending_approval"
    assert reviewed["original_extracted_stem"] == "Which diagnosis is most likely?"
    assert reviewed["original_extracted_options"][0]["text"] == "Option one"
    assert reviewed["transcription_status"] == "human_reviewed"
    assert reviewed["answer_status"] == "human_verified"
    assert not (tmp_path / "bank.json").exists()


def test_approval_promotes_only_verified_candidate_and_keeps_draft_status(tmp_path):
    source_dir = tmp_path / "inbox"
    _candidate_in_inbox(source_dir)
    save_candidate_review(
        "candidate-001",
        stem="Which diagnosis is most likely?",
        options=[
            {"id": "a", "text": "Option one"},
            {"id": "b", "text": "Option two"},
            {"id": "c", "text": "Option three"},
        ],
        specialty_id="urology",
        topic_id="rcc",
        correct_option_id="b",
        explanation="Rationale verified against the cited teaching source.",
        reviewer="Reviewer A",
        answer_verified=True,
        source_dir=source_dir,
    )
    bank_path = tmp_path / "bank.json"
    promoted = approve_candidate("candidate-001", source_dir=source_dir, bank_path=bank_path)
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    assert promoted["review_status"] == "draft"
    assert promoted["source_page"] == 2
    assert len(bank["questions"]) == 1
    with pytest.raises(ValueError, match="already been promoted"):
        approve_candidate("candidate-001", source_dir=source_dir, bank_path=bank_path)


def test_approval_rejects_unverified_answer(tmp_path):
    source_dir = tmp_path / "inbox"
    _candidate_in_inbox(source_dir)
    save_candidate_review(
        "candidate-001",
        stem="Which diagnosis is most likely?",
        options=[
            {"id": "a", "text": "Option one"},
            {"id": "b", "text": "Option two"},
        ],
        specialty_id="urology",
        topic_id="rcc",
        correct_option_id="b",
        explanation="Unverified rationale.",
        reviewer="Reviewer A",
        answer_verified=False,
        source_dir=source_dir,
    )
    with pytest.raises(ValueError, match="independently verified"):
        approve_candidate("candidate-001", source_dir=source_dir, bank_path=tmp_path / "bank.json")


def test_human_answer_decision_is_compared_with_latest_ai_suggestion(tmp_path):
    source_dir = tmp_path / "inbox"
    source, payload = _candidate_in_inbox(source_dir)
    payload["mcq_candidates"][0]["ai_review_history"] = [{
        "internet_evidence_review": {
            "verdict": "supported",
            "existing_key_assessment": "uncertain",
            "proposed_option_id": "a",
        }
    }]
    (source_dir / "extractions" / f"{source['source_id']}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    reviewed = save_candidate_review(
        "candidate-001",
        stem="Which diagnosis is most likely?",
        options=[
            {"id": "a", "text": "Option one"},
            {"id": "b", "text": "Option two"},
            {"id": "c", "text": "Option three"},
        ],
        specialty_id="urology",
        topic_id="rcc",
        correct_option_id="b",
        explanation="Independently checked rationale.",
        reviewer="Reviewer A",
        answer_verified=True,
        source_dir=source_dir,
    )
    comparison = reviewed["reviewer_ai_comparison"]
    assert comparison["ai_proposed_option_id"] == "a"
    assert comparison["reviewer_selected_option_id"] == "b"
    assert comparison["reviewer_matches_ai_proposal"] is False
