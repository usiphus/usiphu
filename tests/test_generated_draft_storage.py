"""Tests for learner-isolated draft storage."""
from usiphu.storage import (
    due_cards, generated_drafts, save_generated_drafts,
)


def test_generated_drafts_are_isolated_and_not_flashcards(tmp_path):
    db = tmp_path / "drafts.sqlite3"
    card = {
        "id": "generated-1",
        "specialty_id": "urology",
        "topic_id": "pujo",
        "prompt": "Question?",
        "answer": "Answer.",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
        "review_status": "draft",
        "evidence_sources": [],
    }
    assert save_generated_drafts([card], path=db, learner_id="learner-a") == 1
    assert save_generated_drafts([card], path=db, learner_id="learner-a") == 0
    assert len(generated_drafts(path=db, learner_id="learner-a")) == 1
    assert generated_drafts(path=db, learner_id="learner-b") == []
    assert due_cards(path=db, learner_id="learner-a") == []


def test_generated_draft_storage_rejects_non_draft_cards(tmp_path):
    db = tmp_path / "drafts.sqlite3"
    card = {
        "id": "generated-2", "specialty_id": "urology", "topic_id": "pujo",
        "prompt": "Question?", "answer": "Answer.", "review_status": "approved",
    }
    try:
        save_generated_drafts([card], path=db)
    except ValueError as exc:
        assert "Only draft cards" in str(exc)
    else:
        raise AssertionError("Non-draft card must not enter generated_drafts")
