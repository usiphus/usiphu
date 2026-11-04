"""Learner-isolated question attempt history and topic-level performance."""
from collections import defaultdict
from pathlib import Path

from usiphu.practice import load_questions
from usiphu.storage import DEFAULT_DB, connect, initialize


def initialize_question_history(path: Path = DEFAULT_DB) -> None:
    """Create the question-attempt table without changing existing learner data."""
    initialize(path)
    with connect(path) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS question_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                selected_option_id TEXT NOT NULL,
                is_correct INTEGER NOT NULL CHECK(is_correct IN (0, 1)),
                mode TEXT NOT NULL CHECK(mode IN ('practice', 'exam')),
                attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_question_attempts_owner_date "
            "ON question_attempts(owner_id, attempted_at)"
        )


def record_question_attempts(
    attempts: list[dict],
    path: Path = DEFAULT_DB,
    learner_id: str = "local",
) -> int:
    """Append a batch of submitted answers for one learner."""
    if not attempts:
        return 0
    rows = []
    for attempt in attempts:
        question_id = attempt.get("question_id")
        selected_option_id = attempt.get("selected_option_id")
        mode = attempt.get("mode", "practice")
        is_correct = attempt.get("is_correct")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError("question_id is required")
        if not isinstance(selected_option_id, str) or not selected_option_id.strip():
            raise ValueError("selected_option_id is required")
        if mode not in {"practice", "exam"}:
            raise ValueError("mode must be practice or exam")
        if not isinstance(is_correct, bool):
            raise ValueError("is_correct must be a boolean")
        rows.append(
            (learner_id, question_id, selected_option_id, int(is_correct), mode)
        )

    initialize_question_history(path)
    with connect(path) as db:
        db.executemany(
            """
            INSERT INTO question_attempts
                (owner_id, question_id, selected_option_id, is_correct, mode)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def question_performance(
    path: Path = DEFAULT_DB,
    learner_id: str = "local",
) -> dict:
    """Summarize a learner's question attempts by curriculum topic."""
    initialize_question_history(path)
    with connect(path) as db:
        rows = db.execute(
            """
            SELECT question_id, COUNT(*) AS attempted,
                   SUM(is_correct) AS correct
            FROM question_attempts
            WHERE owner_id = ?
            GROUP BY question_id
            """,
            (learner_id,),
        ).fetchall()

    question_map = {question.id: question for question in load_questions()}
    topic_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"attempted": 0, "correct": 0}
    )
    attempted = 0
    correct = 0
    for row in rows:
        attempted += row["attempted"]
        correct += row["correct"] or 0
        question = question_map.get(row["question_id"])
        if question is None:
            continue
        topic = topic_totals[question.topic_id]
        topic["attempted"] += row["attempted"]
        topic["correct"] += row["correct"] or 0

    by_topic = [
        {
            "topic": topic,
            "attempted": values["attempted"],
            "correct": values["correct"],
            "accuracy": round(100 * values["correct"] / values["attempted"], 1),
        }
        for topic, values in sorted(topic_totals.items())
    ]
    return {
        "attempted": attempted,
        "correct": correct,
        "accuracy": round(100 * correct / attempted, 1) if attempted else 0.0,
        "by_topic": by_topic,
    }
