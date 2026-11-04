"""Tests for advisory source-transcription and MCQ answer review."""
import json

import pytest

import usiphu.ai_question_review as review
from usiphu.ai_provider import GenerationNotConfigured


@pytest.fixture
def candidate():
    return {
        "candidate_id": "mcq-1",
        "source_filename": "paper.pdf",
        "source_page": 4,
        "raw_text": "1) Which is the best test?\nA. Ultrasound\nB. CT scan\nC. MRI",
        "stem_extracted": "Which is the best test?",
        "options": [
            {"id": "a", "text": "Ultrasound"},
            {"id": "b", "text": "CT scan"},
            {"id": "c", "text": "MRI"},
        ],
    }


def _response(key="b", basis="clinical_reasoning"):
    return json.dumps({
        "transcription": {
            "suggested_stem": "Which is the best test?",
            "suggested_options": [
                {"id": "a", "text": "Ultrasound"},
                {"id": "b", "text": "CT scan"},
                {"id": "c", "text": "MRI"},
            ],
            "issues": [],
            "confidence": "high",
        },
        "answer_review": {
            "suggested_option_id": key,
            "basis": basis,
            "source_evidence": "Answer: B" if basis == "explicit_source_key" else "",
            "rationale": "Illustrative rationale.",
            "confidence": "medium",
            "uncertainties": ["Clinical context is limited."],
        },
    })


def test_review_returns_advisory_answer_and_transcription(monkeypatch, candidate):
    monkeypatch.setattr(review, "provider_status", lambda: {"configured": True, "model": "test-model"})
    monkeypatch.setattr(review, "_ollama_chat", lambda prompt, model: _response())
    result = review.review_mcq_candidate(candidate)
    assert result["transcription"]["suggested_stem"] == candidate["stem_extracted"]
    assert result["answer_review"]["suggested_option_id"] == "b"
    assert result["answer_review"]["basis"] == "clinical_reasoning"
    assert result["official_answer_key"] is False
    assert result["human_review_required"] is True


def test_explicit_source_key_requires_a_quote(monkeypatch, candidate):
    monkeypatch.setattr(review, "provider_status", lambda: {"configured": True, "model": "test-model"})
    monkeypatch.setattr(review, "_ollama_chat", lambda prompt, model: _response("b", "explicit_source_key"))
    result = review.review_mcq_candidate(candidate)
    assert result["answer_review"]["basis"] == "explicit_source_key"
    assert result["answer_review"]["source_evidence"] == "Answer: B"


def test_unknown_option_ids_are_rejected(monkeypatch, candidate):
    payload = json.loads(_response())
    payload["transcription"]["suggested_options"][1]["id"] = "d"
    monkeypatch.setattr(review, "provider_status", lambda: {"configured": True, "model": "test-model"})
    monkeypatch.setattr(review, "_ollama_chat", lambda prompt, model: json.dumps(payload))
    with pytest.raises(review.QuestionReviewError, match="preserve every original option ID"):
        review.review_mcq_candidate(candidate)


def test_answer_key_must_be_one_of_existing_options(monkeypatch, candidate):
    monkeypatch.setattr(review, "provider_status", lambda: {"configured": True, "model": "test-model"})
    monkeypatch.setattr(review, "_ollama_chat", lambda prompt, model: _response("z"))
    with pytest.raises(review.QuestionReviewError, match="not one of the extracted options"):
        review.review_mcq_candidate(candidate)


def test_unclear_answer_is_never_returned_as_a_key(monkeypatch, candidate):
    monkeypatch.setattr(review, "provider_status", lambda: {"configured": True, "model": "test-model"})
    monkeypatch.setattr(review, "_ollama_chat", lambda prompt, model: _response("b", "unclear"))
    result = review.review_mcq_candidate(candidate)
    assert result["answer_review"]["suggested_option_id"] is None
    assert result["official_answer_key"] is False


def test_review_requires_original_text(candidate):
    candidate["raw_text"] = ""
    with pytest.raises(review.QuestionReviewError, match="original extracted source text"):
        review.review_mcq_candidate(candidate)


def test_review_requires_configured_local_model(monkeypatch, candidate):
    monkeypatch.setattr(review, "provider_status", lambda: {"configured": False, "model": "test-model"})
    with pytest.raises(GenerationNotConfigured):
        review.review_mcq_candidate(candidate)
