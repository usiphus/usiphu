"""Integration tests run against the ephemeral PostgreSQL service in CI."""
import os
import uuid

import pytest

from usiphu.assessment_faculty_review import (
    assessment_review_history,
    enqueue_assessment_for_review,
    record_assessment_review_decision,
)
from usiphu.faculty_review import set_reviewer_role
from usiphu.storage import (
    DEFAULT_DB,
    dashboard_stats,
    generated_drafts,
    record_question_attempt,
    question_attempt_history,
    save_flashcard,
    save_generated_drafts,
    set_topic_progress,
    topic_progress,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("USIPHU_DATABASE_URL"),
    reason="Set USIPHU_DATABASE_URL to run PostgreSQL integration tests.",
)


def test_learner_storage_round_trip_in_postgres():
    owner = f"pg-test-{uuid.uuid4().hex}"
    card_id = f"pg-card-{uuid.uuid4().hex}"
    save_flashcard(
        {
            "id": card_id,
            "specialty_id": "urology",
            "topic_id": "pujo",
            "prompt": "What does PUJO stand for?",
            "answer": "Pelvi-ureteric junction obstruction.",
            "source_url": None,
        },
        learner_id=owner,
    )
    save_generated_drafts(
        [{
            "id": f"draft-{uuid.uuid4().hex}",
            "specialty_id": "urology",
            "topic_id": "pujo",
            "prompt": "Draft question",
            "answer": "Draft answer",
            "review_status": "draft",
        }],
        learner_id=owner,
    )
    set_topic_progress("pujo", "learning", 3, learner_id=owner)
    record_question_attempt("pg-test-question", "b", True, learner_id=owner)

    stats = dashboard_stats(learner_id=owner)
    assert stats["flashcards"] == 1
    assert stats["topics_tracked"] == 1
    assert stats["topics_mastered"] == 0
    assert generated_drafts(learner_id=owner)[0]["prompt"] == "Draft question"
    assert topic_progress(learner_id=owner)[0]["confidence"] == 3
    assert question_attempt_history(learner_id=owner)[0]["question_id"] == "pg-test-question"

    from usiphu.storage import connect

    with connect(DEFAULT_DB) as db:
        db.execute("DELETE FROM question_attempts WHERE owner_id=?", (owner,))
        db.execute("DELETE FROM learner_topic_progress WHERE owner_id=?", (owner,))
        db.execute("DELETE FROM generated_drafts WHERE owner_id=?", (owner,))
        db.execute("DELETE FROM flashcards WHERE owner_id=?", (owner,))


def test_postgres_keeps_two_person_faculty_approval_invariant(monkeypatch):
    suffix = uuid.uuid4().hex
    admin = f"ci-admin-{suffix}"
    clinician = f"ci-clinician-{suffix}"
    examiner = f"ci-examiner-{suffix}"
    item_id = f"ci-assessment-{suffix}"
    monkeypatch.setenv("USIPHU_ADMIN_SUBJECTS", admin)

    set_reviewer_role(admin, clinician, "clinical_reviewer", enabled=True, path=DEFAULT_DB)
    set_reviewer_role(admin, examiner, "exam_reviewer", enabled=True, path=DEFAULT_DB)
    payload = {
        "prompt": "Describe the initial management.",
        "answer": "A structured, evidence-based response.",
        "source_id": f"source-{suffix}",
        "source_page": 2,
        "evidence_sources": [{"source_id": "PMID:123"}],
    }
    enqueue_assessment_for_review(item_id, "short_answer", payload, path=DEFAULT_DB)

    clinical_checks = {
        "answer_verified": True,
        "rationale_verified": True,
        "evidence_checked": True,
        "safety_checked": True,
    }
    exam_checks = {
        "single_best_answer": True,
        "stem_clear": True,
        "distractors_or_tasks_reviewed": True,
        "curriculum_aligned": True,
        "level_appropriate": True,
    }
    clinical = record_assessment_review_decision(
        item_id, stage="clinical", decision="approve",
        reviewer_id=clinician, reviewer_name="Clinical reviewer",
        comment="Clinical content checked.", attestations=clinical_checks, path=DEFAULT_DB,
    )
    assert clinical["clinical_status"] == "approved"

    with pytest.raises(ValueError, match="different reviewers"):
        record_assessment_review_decision(
            item_id, stage="exam", decision="approve",
            reviewer_id=clinician, reviewer_name="Same reviewer",
            comment="Should be blocked.", attestations=exam_checks, path=DEFAULT_DB,
        )

    exam = record_assessment_review_decision(
        item_id, stage="exam", decision="approve",
        reviewer_id=examiner, reviewer_name="Exam reviewer",
        comment="Assessment blueprint checked.", attestations=exam_checks, path=DEFAULT_DB,
    )
    assert exam["exam_status"] == "approved"
    assert [event["stage"] for event in assessment_review_history(item_id, DEFAULT_DB)] == [
        "clinical", "exam"
    ]

    from usiphu.storage import connect

    with connect(DEFAULT_DB) as db:
        db.execute("DELETE FROM shared_assessment_review_events WHERE item_id=?", (item_id,))
        db.execute("DELETE FROM shared_assessment_reviews WHERE item_id=?", (item_id,))
        db.execute("DELETE FROM faculty_role_events WHERE reviewer_id IN (?,?)", (clinician, examiner))
        db.execute("DELETE FROM faculty_reviewer_roles WHERE reviewer_id IN (?,?)", (clinician, examiner))
