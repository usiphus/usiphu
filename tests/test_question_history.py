"""Persistence and learner-isolation tests for question-bank attempts."""
from usiphu.question_history import question_performance, record_question_attempts


def test_question_attempts_are_saved_and_summarized_by_topic(tmp_path):
    db = tmp_path / "question-history.sqlite3"
    attempts = [
        {
            "question_id": "uro-001",
            "selected_option_id": "b",
            "is_correct": True,
            "mode": "practice",
        },
        {
            "question_id": "uro-001",
            "selected_option_id": "a",
            "is_correct": False,
            "mode": "exam",
        },
    ]
    assert record_question_attempts(attempts, db, learner_id="learner-a") == 2
    result = question_performance(db, learner_id="learner-a")
    assert result["attempted"] == 2
    assert result["correct"] == 1
    assert result["accuracy"] == 50.0
    assert result["by_topic"] == [
        {"topic": "retention", "attempted": 2, "correct": 1, "accuracy": 50.0}
    ]


def test_question_attempts_are_isolated_between_learners(tmp_path):
    db = tmp_path / "question-isolation.sqlite3"
    attempt = [{
        "question_id": "uro-001",
        "selected_option_id": "b",
        "is_correct": True,
        "mode": "practice",
    }]
    record_question_attempts(attempt, db, learner_id="learner-a")
    assert question_performance(db, learner_id="learner-a")["attempted"] == 1
    assert question_performance(db, learner_id="learner-b")["attempted"] == 0


def test_question_attempts_reject_invalid_mode(tmp_path):
    db = tmp_path / "question-invalid.sqlite3"
    attempt = [{
        "question_id": "uro-001",
        "selected_option_id": "b",
        "is_correct": True,
        "mode": "review",
    }]
    try:
        record_question_attempts(attempt, db)
    except ValueError as exc:
        assert "mode" in str(exc)
    else:
        raise AssertionError("Invalid attempt mode should be rejected")
