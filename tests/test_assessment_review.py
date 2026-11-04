"""Tests for written assessment review and conservative answer checking."""
import json

import pytest

from usiphu.answer_checker import check_assessment_answers, check_mcq_answer, check_rubric_answer
from usiphu.assessment_review import load_assessments, save_non_mcq_review
from usiphu.source_inbox import save_source


def _candidate(source_dir, kind):
    source = save_source(
        "exam.txt",
        b"1) Describe the management.\n",
        specialty="Urology",
        source_dir=source_dir,
    )
    extraction_dir = source_dir / "extractions"
    extraction_dir.mkdir()
    item = {
        "candidate_id": "written-001",
        "source_page": 3,
        "source_page_end": 4,
        "raw_text": "Clinical scenario and extracted question text",
    }
    if kind == "meq":
        item["question_type"] = "modified_essay_question"
        collection = "meq_page_candidates"
    else:
        item["question_type"] = "short_answer_candidate"
        item["stem_extracted"] = "Describe the management."
        collection = "mcq_candidates"
    payload = {
        "source_id": source["source_id"],
        "source_title": "Exam paper",
        "source_filename": "exam.txt",
        collection: [item],
    }
    (extraction_dir / f"{source['source_id']}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return source


def _parts():
    return [{
        "id": "part-1",
        "prompt": "Describe the initial management.",
        "marking_points": [
            {
                "point": "Assess airway and breathing",
                "acceptable_terms": ["airway", "breathing", "ABC assessment"],
                "marks": 2,
            },
            {
                "point": "Establish IV access",
                "acceptable_terms": ["IV access", "intravenous cannula"],
                "marks": 1,
            },
        ],
    }]


def test_short_answer_review_can_be_promoted_with_verified_rubric(tmp_path):
    source_dir = tmp_path / "inbox"
    _candidate(source_dir, "short_answer")
    result = save_non_mcq_review(
        "written-001",
        assessment_type="short_answer",
        prompt="Describe the management.",
        scenario="",
        parts=_parts(),
        specialty_id="urology",
        topic_id="acute-retention",
        reviewer="Reviewer A",
        rubric_verified=True,
        corrected_source_text="Corrected and verified question transcription.",
        source_dir=source_dir,
        bank_path=tmp_path / "assessments.json",
        approve=True,
    )
    assert result["review_status"] == "draft"
    assert result["source_page"] == 3
    extraction = json.loads(next((source_dir / "extractions").glob("*.json")).read_text(encoding="utf-8"))
    saved_candidate = extraction["mcq_candidates"][0]
    assert saved_candidate["original_extracted_text"] == "Clinical scenario and extracted question text"
    assert saved_candidate["reviewed_source_text"] == "Corrected and verified question transcription."
    assert saved_candidate["transcription_status"] == "human_reviewed"
    assert len(load_assessments(tmp_path / "assessments.json")) == 1


def test_meq_review_requires_rubric_verification(tmp_path):
    source_dir = tmp_path / "inbox"
    _candidate(source_dir, "meq")
    with pytest.raises(ValueError, match="independently checked"):
        save_non_mcq_review(
            "written-001",
            assessment_type="meq",
            prompt="Acute clinical case",
            scenario="Case details",
            parts=_parts(),
            specialty_id="urology",
            topic_id="acute-retention",
            reviewer="Reviewer A",
            rubric_verified=False,
            source_dir=source_dir,
            bank_path=tmp_path / "assessments.json",
            approve=True,
        )


def test_rubric_checker_awards_points_for_accepted_terms_and_flags_manual_review():
    result = check_rubric_answer(
        "Start with ABC assessment and insert an IV access.",
        _parts()[0]["marking_points"],
    )
    assert result["marks_awarded"] == 3
    assert result["marks_available"] == 3
    assert result["manual_review_required"] is True


def test_rubric_checker_does_not_claim_semantic_judgement_for_unmatched_wording():
    result = check_rubric_answer(
        "Stabilize the patient first.",
        _parts()[0]["marking_points"],
    )
    assert result["marks_awarded"] == 0
    assert all(point["manual_check_recommended"] for point in result["points"])


def test_mcq_checker_discloses_unreviewed_answer_key():
    result = check_mcq_answer(
        selected_option_id="b",
        correct_option_id="b",
        review_status="draft",
    )
    assert result["correct"] is True
    assert result["status"] == "provisional_key"
    assert result["trusted_key"] is False


def test_assessment_checker_returns_part_and_overall_scores():
    assessment = {
        "id": "demo",
        "assessment_type": "meq",
        "parts": _parts(),
    }
    result = check_assessment_answers(
        assessment,
        {"part-1": "ABC assessment and IV access"},
    )
    assert result["marks_awarded"] == 3
    assert result["marks_available"] == 3
    assert result["manual_review_required"] is True


def test_rubric_checker_requires_word_boundaries_for_short_terms():
    result = check_rubric_answer(
        "The patient should be given fluids.",
        [{
            "point": "Establish IV access",
            "acceptable_terms": ["IV"],
            "marks": 1,
        }],
    )
    assert result["marks_awarded"] == 0
    assert result["points"][0]["manual_check_recommended"] is True
