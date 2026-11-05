"""Tests for shared generated/extracted assessment faculty review."""
import pytest

from usiphu.assessment_faculty_review import (
    assessment_review_history,
    enqueue_assessment_for_review,
    list_assessment_review_queue,
    record_assessment_review_decision,
)
from usiphu.faculty_review import set_reviewer_role

CLINICAL = {
    "answer_verified": True, "rationale_verified": True,
    "evidence_checked": True, "safety_checked": True,
}
EXAM = {
    "single_best_answer": True, "stem_clear": True,
    "distractors_or_tasks_reviewed": True, "curriculum_aligned": True,
    "level_appropriate": True,
}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("USIPHU_ADMIN_SUBJECTS", "admin")
    db = tmp_path / "reviews.sqlite3"
    set_reviewer_role("admin", "clinician", "clinical_reviewer", enabled=True, path=db)
    set_reviewer_role("admin", "examiner", "exam_reviewer", enabled=True, path=db)
    payload = {
        "prompt": "Describe the clinical approach.",
        "answer": "A structured answer.",
        "card_type": "osce_station",
        "source_id": "paper-1",
        "source_page": 4,
        "evidence_sources": [{"source_id": "PMID:123"}],
    }
    enqueue_assessment_for_review("generated-1", "osce_station", payload, path=db)
    return db


def test_shared_queue_starts_as_draft_and_supports_osce_items(workspace):
    item = list_assessment_review_queue(workspace)[0]
    assert item["item_type"] == "osce_station"
    assert item["release_status"] == "draft"
    assert item["payload"]["prompt"] == "Describe the clinical approach."


def test_two_stage_review_requires_roles_and_distinct_people(workspace):
    with pytest.raises(ValueError, match="clinical approval"):
        record_assessment_review_decision(
            "generated-1", stage="exam", decision="approve",
            reviewer_id="examiner", reviewer_name="Examiner", comment="Reviewed",
            attestations=EXAM, path=workspace,
        )
    clinical = record_assessment_review_decision(
        "generated-1", stage="clinical", decision="approve",
        reviewer_id="clinician", reviewer_name="Clinician", comment="Evidence checked",
        attestations=CLINICAL, path=workspace,
    )
    assert clinical["clinical_status"] == "approved"
    with pytest.raises(ValueError, match="different reviewers"):
        record_assessment_review_decision(
            "generated-1", stage="exam", decision="approve",
            reviewer_id="clinician", reviewer_name="Clinician", comment="Reviewed",
            attestations=EXAM, path=workspace,
        )
    released = record_assessment_review_decision(
        "generated-1", stage="exam", decision="approve",
        reviewer_id="examiner", reviewer_name="Examiner", comment="Blueprint checked",
        attestations=EXAM, path=workspace,
    )
    assert released["exam_status"] == "approved"
    assert list_assessment_review_queue(workspace)[0]["release_status"] == "exam_validated"
    assert [row["stage"] for row in assessment_review_history("generated-1", workspace)] == [
        "clinical", "exam"
    ]


def test_clinical_approval_requires_source_and_attestations(workspace):
    enqueue_assessment_for_review(
        "bad-item", "viva", {"prompt": "Question", "answer": "Answer"}, path=workspace
    )
    with pytest.raises(ValueError, match="traceable source"):
        record_assessment_review_decision(
            "bad-item", stage="clinical", decision="approve",
            reviewer_id="clinician", reviewer_name="Clinician", comment="Checked",
            attestations=CLINICAL, path=workspace,
        )


def test_exam_approval_requires_all_attestations(workspace):
    record_assessment_review_decision(
        "generated-1", stage="clinical", decision="approve",
        reviewer_id="clinician", reviewer_name="Clinician", comment="Checked",
        attestations=CLINICAL, path=workspace,
    )
    with pytest.raises(ValueError, match="five examination"):
        record_assessment_review_decision(
            "generated-1", stage="exam", decision="approve",
            reviewer_id="examiner", reviewer_name="Examiner", comment="Checked",
            attestations={"single_best_answer": True}, path=workspace,
        )


def test_stage_permissions_are_enforced_in_service(workspace):
    with pytest.raises(PermissionError, match="clinical_reviewer"):
        record_assessment_review_decision(
            "generated-1", stage="clinical", decision="request_changes",
            reviewer_id="examiner", reviewer_name="Examiner", comment="Wrong role",
            path=workspace,
        )


def test_extracted_candidate_must_be_completed_in_editor_before_approval(workspace):
    enqueue_assessment_for_review(
        "extracted-1", "single_best_answer",
        {"candidate_id": "extracted-1", "source_id": "paper-2", "source_page": 7,
         "raw_text": "Which investigation is appropriate?"},
        path=workspace,
    )
    with pytest.raises(ValueError, match="Complete the edited prompt"):
        record_assessment_review_decision(
            "extracted-1", stage="clinical", decision="approve",
            reviewer_id="clinician", reviewer_name="Clinician", comment="Checked",
            attestations=CLINICAL, path=workspace,
        )
    enqueue_assessment_for_review(
        "extracted-1", "single_best_answer",
        {"candidate_id": "extracted-1", "source_id": "paper-2", "source_page": 7,
         "prompt": "Which investigation is appropriate?",
         "options": [{"id": "a", "text": "Ultrasound"}, {"id": "b", "text": "MCUG"}],
         "correct_option_id": "b", "answer": "MCUG",
         "explanation": "It demonstrates reflux."},
        path=workspace,
    )
    approved = record_assessment_review_decision(
        "extracted-1", stage="clinical", decision="approve",
        reviewer_id="clinician", reviewer_name="Clinician", comment="Checked",
        attestations=CLINICAL, path=workspace,
    )
    assert approved["clinical_status"] == "approved"
