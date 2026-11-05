"""End-to-end persistence and faculty authorization checks against disposable PostgreSQL."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

from usiphu.assessment_faculty_review import (
    assessment_review_history,
    enqueue_assessment_for_review,
    list_assessment_review_queue,
    record_assessment_review_decision,
)
from usiphu.faculty_review import (
    _pilot_questions,
    record_faculty_decision,
    review_history,
    set_reviewer_role,
)
from usiphu.storage import dashboard_stats, save_flashcard, set_topic_progress

DATABASE_URL = os.getenv("USIPHU_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Requires USIPHU_TEST_POSTGRES_URL for a disposable PostgreSQL database"
)
MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "0001_postgresql_schema.sql"

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
ADMIN = "https://auth.example/:faculty-admin"
CLINICAL = "https://auth.example/:faculty-clinical"
EXAM = "https://auth.example/:faculty-exam"


@pytest.fixture(scope="session", autouse=True)
def postgres_schema():
    """Apply the versioned schema to the disposable CI database once."""
    with psycopg.connect(DATABASE_URL, sslmode=os.getenv("USIPHU_DATABASE_SSLMODE", "disable")) as conn:
        for statement in MIGRATION.read_text(encoding="utf-8").split(";"):
            if statement.strip():
                conn.execute(statement)
    yield


@pytest.fixture(autouse=True)
def clean_postgres(monkeypatch, postgres_schema):
    monkeypatch.setenv("USIPHU_DATABASE_BACKEND", "postgres")
    monkeypatch.setenv("SUPABASE_DB_URL", DATABASE_URL)
    monkeypatch.setenv("USIPHU_DATABASE_SSLMODE", os.getenv("USIPHU_DATABASE_SSLMODE", "disable"))
    monkeypatch.setenv("USIPHU_ADMIN_SUBJECTS", ADMIN)
    with psycopg.connect(DATABASE_URL, sslmode=os.getenv("USIPHU_DATABASE_SSLMODE", "disable")) as conn:
        conn.execute(
            "TRUNCATE TABLE shared_assessment_review_events, shared_assessment_reviews, "
            "faculty_question_review_events, faculty_role_events, faculty_reviewer_roles, "
            "faculty_question_reviews, question_attempts, review_events, review_states, "
            "generated_drafts, learner_topic_progress, topic_progress, flashcards "
            "RESTART IDENTITY CASCADE"
        )


def _grant_faculty_roles():
    set_reviewer_role(ADMIN, CLINICAL, "clinical_reviewer", enabled=True)
    set_reviewer_role(ADMIN, EXAM, "exam_reviewer", enabled=True)


def test_postgres_learner_records_are_isolated_between_auth0_subjects():
    save_flashcard(
        {
            "id": "card-1",
            "specialty_id": "urology",
            "topic_id": "pujo",
            "prompt": "What does PUJO stand for?",
            "answer": "Pelvi-ureteric junction obstruction",
            "source_url": None,
        },
        learner_id="https://auth.example/:learner-a",
    )
    set_topic_progress(
        "pujo", "learning", 3, learner_id="https://auth.example/:learner-a"
    )

    learner_a = dashboard_stats(learner_id="https://auth.example/:learner-a")
    learner_b = dashboard_stats(learner_id="https://auth.example/:learner-b")

    assert learner_a["flashcards"] == 1
    assert learner_a["topics_tracked"] == 1
    assert learner_b["flashcards"] == 0
    assert learner_b["topics_tracked"] == 0


def test_postgres_faculty_review_enforces_two_person_approval_and_audit():
    _grant_faculty_roles()
    question = _pilot_questions()[0]
    question_id = question["id"]
    result = record_faculty_decision(
        question_id,
        stage="clinical",
        decision="approve",
        reviewer_id=CLINICAL,
        reviewer_name="Clinical Reviewer",
        comment="Source, answer and rationale checked.",
        content={
            "source_id": "ci-source-paper",
            "source_page": 1,
            "transcription_status": "corrected",
            "evidence_sources": [{"source_id": "PMID:123456"}],
        },
        attestations=CLINICAL_CHECKS,
    )
    assert result["faculty_release_status"] == "clinically_reviewed"

    with pytest.raises(ValueError, match="different reviewers"):
        record_faculty_decision(
            question_id,
            stage="exam",
            decision="approve",
            reviewer_id=CLINICAL,
            reviewer_name="Clinical Reviewer",
            comment="Attempted self-approval.",
            attestations=EXAM_CHECKS,
        )

    released = record_faculty_decision(
        question_id,
        stage="exam",
        decision="approve",
        reviewer_id=EXAM,
        reviewer_name="Exam Reviewer",
        comment="Blueprint and single-best-answer quality checked.",
        attestations=EXAM_CHECKS,
    )
    assert released["faculty_release_status"] == "exam_validated"
    history = review_history(question_id)
    assert [event["stage"] for event in history] == ["clinical", "exam"]
    assert [event["reviewer_id"] for event in history] == [CLINICAL, EXAM]


def test_postgres_shared_assessment_queue_requires_independent_reviewers():
    _grant_faculty_roles()
    item_id = "postgres-ci-osce"
    enqueue_assessment_for_review(
        item_id,
        "osce_station",
        {
            "prompt": "Describe the initial management.",
            "answer": "A structured approach.",
            "source_id": "ci-source-paper",
            "source_page": 2,
            "evidence_sources": [{"source_id": "PMID:654321"}],
        },
    )
    record_assessment_review_decision(
        item_id,
        stage="clinical",
        decision="approve",
        reviewer_id=CLINICAL,
        reviewer_name="Clinical Reviewer",
        comment="Clinical content checked.",
        attestations=CLINICAL_CHECKS,
    )
    with pytest.raises(ValueError, match="different reviewers"):
        record_assessment_review_decision(
            item_id,
            stage="exam",
            decision="approve",
            reviewer_id=CLINICAL,
            reviewer_name="Clinical Reviewer",
            comment="Attempted self-approval.",
            attestations={
                "single_best_answer": True,
                "stem_clear": True,
                "distractors_or_tasks_reviewed": True,
                "curriculum_aligned": True,
                "level_appropriate": True,
            },
        )
    record_assessment_review_decision(
        item_id,
        stage="exam",
        decision="approve",
        reviewer_id=EXAM,
        reviewer_name="Exam Reviewer",
        comment="Assessment quality checked.",
        attestations={
            "single_best_answer": True,
            "stem_clear": True,
            "distractors_or_tasks_reviewed": True,
            "curriculum_aligned": True,
            "level_appropriate": True,
        },
    )
    assert list_assessment_review_queue()[0]["release_status"] == "exam_validated"
    assert [event["stage"] for event in assessment_review_history(item_id)] == [
        "clinical",
        "exam",
    ]
