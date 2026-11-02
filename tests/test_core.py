"""Domain and persistence regression tests."""
from datetime import date
from pathlib import Path

from usiphu.curriculum import coverage_summary, flatten_topics, load_curriculum
from usiphu.models import ReviewState
from usiphu.practice import load_cases, load_questions
from usiphu.resources import discover_resources
from usiphu.scheduler import schedule_review
from usiphu.storage import (
    dashboard_stats,
    due_cards,
    initialize,
    record_review,
    save_flashcard,
    set_topic_progress,
    topic_progress,
)


def test_curriculum_has_specialties_topics_and_objectives():
    curriculum = load_curriculum()
    summary = coverage_summary(curriculum)
    assert summary["specialties"] >= 10 and summary["topics"] >= 35
    assert summary["objectives"] > 0
    assert len(flatten_topics(curriculum)) == summary["topics"]


def test_practice_banks_validate():
    assert len(load_questions()) >= 3
    assert len(load_cases()) >= 2


def test_resource_discovery_encodes_query_and_has_notes():
    results = discover_resources("acute urinary retention", "Urology")
    assert len(results) >= 7
    pubmed = next(item for item in results if item["id"] == "pubmed")
    assert "acute+urinary+retention" in pubmed["url"] and pubmed["note"]


def test_scheduler_pass_and_fail():
    initial = ReviewState(card_id="x", due_date="2025-01-01")
    failed = schedule_review(initial, 1, date(2025, 1, 1))
    assert failed.repetitions == 0 and failed.interval_days == 1
    passed = schedule_review(initial, 4, date(2025, 1, 1))
    assert passed.repetitions == 1 and passed.interval_days == 1
    second = schedule_review(passed, 5, date(2025, 1, 2))
    assert second.repetitions == 2 and second.interval_days == 6


def test_sqlite_flashcard_and_progress_lifecycle(tmp_path: Path):
    db = tmp_path / "test.sqlite3"
    initialize(db)
    card = {
        "id": "c1",
        "specialty_id": "urology",
        "topic_id": "retention",
        "prompt": "Define acute urinary retention.",
        "answer": "Inability to empty the bladder.",
        "source_url": None,
    }
    save_flashcard(card, db)
    assert len(due_cards(db, date.today())) == 1
    state = schedule_review(ReviewState(card_id="c1", due_date=date.today().isoformat()), 5)
    record_review("c1", 5, state, db)
    assert dashboard_stats(db)["reviews_completed"] == 1
    assert due_cards(db, date.today()) == []
    set_topic_progress("retention", "mastered", 5, db)
    assert topic_progress(db)[0]["status"] == "mastered"
    assert dashboard_stats(db)["topics_mastered"] == 1
