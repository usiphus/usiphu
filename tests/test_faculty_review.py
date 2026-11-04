"""Tests for independent two-stage pilot faculty review and release gating."""
import json
import shutil

import pytest

from usiphu.answer_checker import check_mcq_answer
from usiphu.faculty_review import (
    DATA_DIR,
    faculty_release_statuses,
    list_pilot_questions,
    record_faculty_decision,
    review_history,
)

CLINICAL_CHECKS = {
    "answer_verified": True,
    "rationale_verified": True,
    "evidence_checked": True,
    "safety_checked": True,
}
EXAM_CHECKS = {
    "single_best_answer": True,
    "stem_clear": True,
    "distractors_reviewed": True,
    "curriculum_aligned": True,
    "level_appropriate": True,
}


@pytest.fixture
def review_workspace(tmp_path):
    bank_dir = tmp_path / "banks"
    bank_dir.mkdir()
    source = DATA_DIR / "question_banks" / "pilot_urology_2026.json"
    shutil.copy(source, bank_dir / source.name)
    return tmp_path / "faculty.sqlite3", bank_dir, "uro-pilot-0001"


def approve_clinical(db_path, bank_dir, question_id="uro-pilot-0001", reviewer="clinician-1", content=None):
    return record_faculty_decision(
        question_id,
        stage="clinical",
        decision="approve",
        reviewer_id=reviewer,
        reviewer_name="Clinical Faculty",
        comment="Answer, explanation, evidence and clinical caveats independently checked.",
        content=content,
        attestations=CLINICAL_CHECKS,
        path=db_path,
        bank_dir=bank_dir,
    )


def approve_exam(db_path, bank_dir, question_id="uro-pilot-0001", reviewer="examiner-1"):
    return record_faculty_decision(
        question_id,
        stage="exam",
        decision="approve",
        reviewer_id=reviewer,
        reviewer_name="Exam Faculty",
        comment="Single-best-answer quality, blueprint alignment and level checked.",
        attestations=EXAM_CHECKS,
        path=db_path,
        bank_dir=bank_dir,
    )


def test_exam_validation_is_blocked_until_clinical_approval(review_workspace):
    db_path, bank_dir, _ = review_workspace
    with pytest.raises(ValueError, match="clinical approval"):
        approve_exam(db_path, bank_dir)


def test_clinical_approval_requires_every_attestation(review_workspace):
    db_path, bank_dir, question_id = review_workspace
    with pytest.raises(ValueError, match="four clinical approval attestations"):
        record_faculty_decision(
            question_id,
            stage="clinical",
            decision="approve",
            reviewer_id="clinician-1",
            reviewer_name="Clinical Faculty",
            comment="Checked.",
            attestations={"answer_verified": True},
            path=db_path,
            bank_dir=bank_dir,
        )


def test_two_distinct_faculty_members_are_required_for_release(review_workspace):
    db_path, bank_dir, question_id = review_workspace
    clinical = approve_clinical(db_path, bank_dir)
    assert clinical["faculty_release_status"] == "clinically_reviewed"

    with pytest.raises(ValueError, match="different reviewers"):
        approve_exam(db_path, bank_dir, reviewer="clinician-1")

    released = approve_exam(db_path, bank_dir, reviewer="examiner-2")
    assert released["faculty_release_status"] == "exam_validated"

    state = faculty_release_statuses(db_path)[question_id]
    assert state["review_status"] == "exam_validated"
    assert state["human_signoff_status"] == "approved"
    assert state["clinical_reviewed_by"] == "Clinical Faculty"
    assert state["exam_validated_by"] == "Exam Faculty"
    assert "Clinical: Clinical Faculty" in state["reviewed_by"]
    assert "Examination: Exam Faculty" in state["reviewed_by"]
    assert state["reviewed_at"] == state["exam_validated_at"]

    history = review_history(question_id, db_path)
    assert [event["stage"] for event in history] == ["clinical", "exam"]
    assert json.loads(history[0]["content_snapshot_json"])["review_attestations"] == CLINICAL_CHECKS
    assert json.loads(history[1]["content_snapshot_json"])["review_attestations"] == EXAM_CHECKS

    visible = next(item for item in list_pilot_questions(db_path, bank_dir) if item["id"] == question_id)
    assert visible["faculty_release_status"] == "exam_validated"


def test_content_change_invalidates_previous_approvals(review_workspace):
    db_path, bank_dir, question_id = review_workspace
    approve_clinical(db_path, bank_dir)
    approve_exam(db_path, bank_dir, reviewer="examiner-2")

    changed = approve_clinical(
        db_path,
        bank_dir,
        reviewer="clinician-2",
        content={"stem": "UPDATED: " + next(
            item["stem"] for item in list_pilot_questions(db_path, bank_dir)
            if item["id"] == question_id
        )},
    )
    assert changed["content_changed"] is True
    assert changed["clinical_status"] == "approved"
    assert changed["exam_status"] == "pending"
    assert changed["faculty_release_status"] == "clinically_reviewed"
    visible = next(item for item in list_pilot_questions(db_path, bank_dir) if item["id"] == question_id)
    assert visible["stem"].startswith("UPDATED: ")
    assert faculty_release_statuses(db_path)[question_id]["stem"].startswith("UPDATED: ")


def test_request_changes_is_preserved_in_append_only_history(review_workspace):
    db_path, bank_dir, question_id = review_workspace
    result = record_faculty_decision(
        question_id,
        stage="clinical",
        decision="request_changes",
        reviewer_id="clinician-1",
        reviewer_name="Clinical Faculty",
        comment="Clarify the imaging protocol and add the relevant exception.",
        path=db_path,
        bank_dir=bank_dir,
    )
    assert result["clinical_status"] == "request_changes"
    events = review_history(question_id, db_path)
    assert len(events) == 1
    assert events[0]["decision"] == "request_changes"
    assert "relevant exception" in events[0]["comment"]


def test_clinical_approval_is_provisional_until_exam_validation():
    clinical = check_mcq_answer(
        selected_option_id="c", correct_option_id="c", review_status="clinically_reviewed"
    )
    assert clinical["status"] == "provisional_key"
    assert clinical["trusted_key"] is False

    validated = check_mcq_answer(
        selected_option_id="c", correct_option_id="c", review_status="exam_validated"
    )
    assert validated["status"] == "marked"
    assert validated["trusted_key"] is True
