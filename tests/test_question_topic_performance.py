"""Tests for learner-isolated question accuracy summaries by topic."""
from usiphu.storage import (
    question_bank_stats,
    question_topic_performance,
    record_question_attempt,
)


def test_question_topic_performance_groups_attempts_and_isolates_learners(tmp_path, monkeypatch):
    from usiphu.practice import load_questions

    questions = load_questions()
    trusted_questions = [
        item.model_copy(update={"review_status": "exam_validated"})
        if item.id in {"uro-001", "uro-002"} else item
        for item in questions
    ]
    monkeypatch.setattr("usiphu.practice.load_questions", lambda: trusted_questions)
    database = tmp_path / "question-performance.sqlite3"

    record_question_attempt(
        "uro-001", "b", True, database, learner_id="learner-a"
    )
    record_question_attempt(
        "uro-001", "a", False, database, learner_id="learner-a"
    )
    record_question_attempt(
        "uro-002", "a", True, database, learner_id="learner-a"
    )
    # The starter bank's vascular item is still a draft and must not affect accuracy.
    record_question_attempt(
        "vas-001", "a", True, database, learner_id="learner-a"
    )
    record_question_attempt(
        "uro-001", "b", True, database, learner_id="learner-b"
    )

    learner_a = question_topic_performance(database, learner_id="learner-a")
    learner_b = question_topic_performance(database, learner_id="learner-b")

    assert learner_a == [
        {
            "topic": "puv",
            "attempted": 1,
            "correct": 1,
            "accuracy_percent": 100.0,
        },
        {
            "topic": "retention",
            "attempted": 2,
            "correct": 1,
            "accuracy_percent": 50.0,
        },
    ]
    assert learner_b == [
        {
            "topic": "retention",
            "attempted": 1,
            "correct": 1,
            "accuracy_percent": 100.0,
        }
    ]
    assert question_bank_stats(database, learner_id="learner-a") == {
        "attempts": 3,
        "correct": 2,
        "questions_attempted": 2,
        "accuracy_percent": 66.7,
    }
