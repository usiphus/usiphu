"""Domain, content-integrity, and persistence regression tests."""
import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

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
from usiphu.validation import validate_content


def test_curriculum_has_specialties_topics_and_objectives():
    curriculum = load_curriculum()
    summary = coverage_summary(curriculum)
    assert summary["specialties"] >= 10 and summary["topics"] >= 35
    assert summary["objectives"] > 0
    assert len(flatten_topics(curriculum)) == summary["topics"]


def test_curriculum_ids_are_unique_and_every_topic_has_an_objective():
    curriculum = load_curriculum()
    specialty_ids = [item.id for item in curriculum.specialties]
    domain_ids = [item.id for specialty in curriculum.specialties for item in specialty.domains]
    topic_ids = [item.id for specialty in curriculum.specialties
                 for domain in specialty.domains for item in domain.topics]
    assert len(specialty_ids) == len(set(specialty_ids))
    assert len(domain_ids) == len(set(domain_ids))
    assert len(topic_ids) == len(set(topic_ids))
    assert all(topic.objectives for specialty in curriculum.specialties
               for domain in specialty.domains for topic in domain.topics)


def test_practice_banks_validate_and_answers_exist():
    questions = load_questions()
    assert len(questions) >= 3
    cases = load_cases()
    assert len(cases) >= 2
    assert all(question.review_status == "draft" for question in questions)
    assert all(case.review_status == "draft" for case in cases)
    for question in questions:
        assert question.correct_option_id in {option.id for option in question.options}


def test_practice_loader_rejects_missing_correct_option(tmp_path: Path):
    invalid = [{
        "id": "bad", "specialty_id": "x", "topic_id": "y", "stem": "Question?",
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "correct_option_id": "z", "explanation": "Invalid answer reference."
    }]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="missing correct option"):
        load_questions(path)


def test_resource_discovery_has_general_and_specialty_sources():
    results = discover_resources("acute urinary retention", "Urology")
    assert len(results) >= 12
    pubmed = next(item for item in results if item["id"] == "pubmed")
    assert "acute+urinary+retention" in pubmed["url"] and "full text is not guaranteed" in pubmed["note"]
    assert any(item["id"] == "guideline-urology" for item in results)
    assert any(item["id"] == "acp-doctors-dilemma" for item in results)
    assert any(item["id"] == "doctors-challenge" and "play.google.com" in item["url"]
               for item in results)


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
    card = {"id": "c1", "specialty_id": "urology", "topic_id": "retention",
            "prompt": "Define acute urinary retention.",
            "answer": "Inability to empty the bladder.", "source_url": None}
    save_flashcard(card, db)
    assert len(due_cards(db, date.today())) == 1
    state = schedule_review(ReviewState(card_id="c1", due_date=date.today().isoformat()), 5)
    record_review("c1", 5, state, db)
    assert dashboard_stats(db)["reviews_completed"] == 1
    assert due_cards(db, date.today()) == []
    set_topic_progress("retention", "mastered", 5, db)
    assert topic_progress(db)[0]["status"] == "mastered"
    assert dashboard_stats(db)["topics_mastered"] == 1


def test_learner_data_isolation(tmp_path: Path):
    db = tmp_path / "learners.sqlite3"
    card = {"id": "shared-id", "specialty_id": "urology", "topic_id": "retention",
            "prompt": "Front", "answer": "Back", "source_url": None}
    save_flashcard(card, db, learner_id="learner-a")
    save_flashcard(card, db, learner_id="learner-b")
    cards_a = due_cards(db, learner_id="learner-a")
    cards_b = due_cards(db, learner_id="learner-b")
    assert len(cards_a) == len(cards_b) == 1
    assert cards_a[0]["id"] != cards_b[0]["id"]
    with pytest.raises(KeyError, match="Unknown flashcard"):
        state = ReviewState(card_id=cards_a[0]["id"], due_date=date.today().isoformat())
        record_review(cards_a[0]["id"], 5, state, db, learner_id="learner-b")
    set_topic_progress("retention", "mastered", 5, db, learner_id="learner-a")
    set_topic_progress("retention", "learning", 2, db, learner_id="learner-b")
    assert topic_progress(db, learner_id="learner-a")[0]["status"] == "mastered"
    assert topic_progress(db, learner_id="learner-b")[0]["status"] == "learning"
    assert dashboard_stats(db, learner_id="learner-a")["flashcards"] == 1
    assert dashboard_stats(db, learner_id="learner-b")["flashcards"] == 0


def test_existing_single_learner_database_migrates(tmp_path: Path):
    db = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.executescript("""
            CREATE TABLE flashcards (
                id TEXT PRIMARY KEY, specialty_id TEXT NOT NULL, topic_id TEXT NOT NULL,
                prompt TEXT NOT NULL, answer TEXT NOT NULL, source_url TEXT
            );
            CREATE TABLE topic_progress (
                topic_id TEXT PRIMARY KEY, status TEXT NOT NULL,
                confidence INTEGER NOT NULL, updated_at TEXT NOT NULL
            );
            INSERT INTO topic_progress VALUES ('old-topic','mastered',5,'2025-01-01');
        """)
    initialize(db)
    assert topic_progress(db, learner_id="local")[0]["topic_id"] == "old-topic"


def test_content_validator_checks_complete_starter_dataset():
    report = validate_content()
    assert report["specialties"] == 13
    assert report["topics"] == 62
    assert report["questions"] == 3
    assert report["cases"] == 2
    assert report["topics_sourced"] == 0
    assert report["topics_reviewed"] == 0
