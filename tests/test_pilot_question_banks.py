"""Regression tests for evidence-checked pilot question banks."""
from collections import Counter

from usiphu.curriculum import load_curriculum
from usiphu.practice import load_questions


def test_pilot_banks_are_traceable_evidence_linked_and_not_scored():
    questions = load_questions()
    pilot = [item for item in questions if item.bank_id.startswith("pilot-")]

    assert len(pilot) == 17
    assert Counter(item.bank_id for item in pilot) == {
        "pilot-urology-2026": 9,
        "pilot-general-surgery-2026": 8,
    }
    for item in pilot:
        assert item.review_status == "draft"
        assert item.human_signoff_status == "pending"
        assert item.evidence_review_status in {
            "supported", "supported_with_editorial_revision"
        }
        assert item.evidence_sources
        assert all(source.url.startswith("https://") for source in item.evidence_sources)
        assert item.source_id in {"paper1", "paper2"}
        assert item.source_filename
        assert item.source_page and item.source_page > 0
        assert item.source_candidate_id
        assert item.transcription_status == "text_layer_checked_not_image_verified"
        assert item.correct_option_id in {option.id for option in item.options}
        assert item.editorial_notes
        assert item.reviewed_by is None
        assert item.reviewed_at is None


def test_pilot_questions_do_not_count_as_clinically_reviewed():
    pilot = [
        item for item in load_questions()
        if item.bank_id in {"pilot-urology-2026", "pilot-general-surgery-2026"}
    ]
    assert pilot
    assert all(item.review_status == "draft" for item in pilot)
    assert not any(item.review_status in {"clinically_reviewed", "exam_validated"} for item in pilot)



def test_pilot_topics_exist_in_the_current_medical_curriculum():
    curriculum = load_curriculum()
    valid_topics = {
        topic.id
        for specialty in curriculum.specialties
        for domain in specialty.domains
        for topic in domain.topics
    }
    pilot = [
        item for item in load_questions()
        if item.bank_id in {"pilot-urology-2026", "pilot-general-surgery-2026"}
    ]
    assert all(item.topic_id in valid_topics for item in pilot)
