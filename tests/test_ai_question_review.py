"""Tests for advisory transcription and open-access MCQ evidence review."""
import json

import pytest

import usiphu.ai_question_review as review
from usiphu.ai_provider import GenerationNotConfigured


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(review, "retrieve_open_access_evidence", lambda candidate: [])


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
    assert result["internet_evidence_review"]["verdict"] == "insufficient_evidence"
    assert result["internet_evidence_review"]["proposed_option_id"] is None
    assert result["official_answer_key"] is False
    assert result["human_review_required"] is True


def test_explicit_source_key_requires_a_quote(monkeypatch, candidate):
    candidate["raw_text"] += "\nAnswer: B"
    monkeypatch.setattr(review, "provider_status", lambda: {"configured": True, "model": "test-model"})
    monkeypatch.setattr(review, "_ollama_chat", lambda prompt, model: _response("b", "explicit_source_key"))
    result = review.review_mcq_candidate(candidate)
    assert result["answer_review"]["basis"] == "explicit_source_key"
    assert result["answer_review"]["source_evidence"] == "Answer: B"


def test_claimed_printed_key_quote_must_exist_in_source(monkeypatch, candidate):
    monkeypatch.setattr(review, "provider_status", lambda: {"configured": True, "model": "test-model"})
    payload = json.loads(_response("b", "explicit_source_key"))
    payload["answer_review"]["source_evidence"] = "The printed key says option B."
    monkeypatch.setattr(review, "_ollama_chat", lambda prompt, model: json.dumps(payload))
    result = review.review_mcq_candidate(candidate)
    assert result["answer_review"]["basis"] == "unclear"
    assert result["answer_review"]["suggested_option_id"] is None


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


def test_internet_review_validates_sources_quotes_and_all_options(monkeypatch, candidate):
    evidence = [{
        "source_id": "PMC:PMC123",
        "source_title": "Open access clinical study",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/",
        "source_date": "2024-01-01",
        "journal": "Example Journal",
        "doi": "10.1000/example",
        "pmid": "12345",
        "pmcid": "PMC123",
        "license": "CC BY",
        "full_text_available": True,
        "evidence_text": "Computed tomography is recommended for this clinical presentation.",
        "source_database": "Europe PMC / PubMed Central",
        "limitations": "Study-specific evidence.",
    }]
    monkeypatch.setattr(review, "retrieve_open_access_evidence", lambda candidate: evidence)
    monkeypatch.setattr(review, "provider_status", lambda: {"configured": True, "model": "test-model"})
    payload = json.loads(_response())
    payload["internet_evidence_review"] = {
        "verdict": "supported",
        "existing_key_assessment": "no_existing_key",
        "proposed_option_id": "b",
        "summary": "The source supports CT in the stated context.",
        "option_assessments": [
            {"option_id": "a", "assessment": "neutral", "reasoning": "Not addressed.", "citations": []},
            {"option_id": "b", "assessment": "supports", "reasoning": "The article recommends CT.",
             "citations": [{"source_id": "PMC:PMC123", "quote": "Computed tomography is recommended for this clinical presentation."}]},
            {"option_id": "c", "assessment": "neutral", "reasoning": "Not addressed.", "citations": []},
        ],
        "conflicts": [],
    }
    monkeypatch.setattr(review, "_ollama_chat", lambda prompt, model: json.dumps(payload))
    result = review.review_mcq_candidate(candidate)
    internet = result["internet_evidence_review"]
    assert internet["proposed_option_id"] == "b"
    assert internet["option_assessments"][1]["citations"][0]["source_url"] == evidence[0]["source_url"]
    assert internet["official_answer_key"] is False


def test_internet_review_rejects_fabricated_quotes(monkeypatch, candidate):
    evidence = [{
        "source_id": "PMC:PMC123", "source_title": "Article",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/",
        "source_date": "2024", "journal": "Journal", "doi": None, "pmid": None,
        "pmcid": "PMC123", "license": "CC BY", "full_text_available": True,
        "evidence_text": "A source statement about the first treatment.",
        "source_database": "Europe PMC / PubMed Central", "limitations": "Study-specific.",
    }]
    monkeypatch.setattr(review, "retrieve_open_access_evidence", lambda candidate: evidence)
    monkeypatch.setattr(review, "provider_status", lambda: {"configured": True, "model": "test-model"})
    payload = json.loads(_response())
    payload["internet_evidence_review"] = {
        "verdict": "supported", "existing_key_assessment": "no_existing_key",
        "proposed_option_id": "b", "summary": "Claimed support.",
        "option_assessments": [
            {"option_id": "a", "assessment": "neutral", "reasoning": "", "citations": []},
            {"option_id": "b", "assessment": "supports", "reasoning": "Claimed support.",
             "citations": [{"source_id": "PMC:PMC123", "quote": "This fabricated quote is not in the source."}]},
            {"option_id": "c", "assessment": "neutral", "reasoning": "", "citations": []},
        ], "conflicts": [],
    }
    monkeypatch.setattr(review, "_ollama_chat", lambda prompt, model: json.dumps(payload))
    with pytest.raises(review.QuestionReviewError, match="quotation could not be verified"):
        review.review_mcq_candidate(candidate)
