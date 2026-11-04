"""Tests for local Ollama generation, evidence gating, and provenance mapping."""
import json

import pytest

import usiphu.ai_provider as ai
from usiphu.ai_provider import GenerationNotConfigured, generate_topic_cards


@pytest.fixture
def pubmed_record():
    return {
        "source_id": "PMID:12345",
        "source_title": "Imaging evaluation of vesicoureteral reflux",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
        "source_date": "2024",
        "journal": "Pediatric Radiology",
        "doi": None,
        "publication_types": ["Review"],
        "evidence_tier": "review",
        "abstract": "Micturating cystourethrography is used in evaluation of reflux.",
        "retrieved_at": "2026-11-03",
        "source_database": "PubMed",
        "limitations": "Abstract-level evidence only.",
    }


def _model_response(prompt):
    refs_json = prompt.split("PERMITTED COURSE OUTCOME REFERENCES:", 1)[1].split(
        "RETRIEVED PUBMED EVIDENCE", 1
    )[0].strip()
    permitted_refs = json.loads(refs_json)
    return json.dumps({
        "card_type": "mcq",
        "prompt": "Which investigation evaluates vesicoureteral reflux?",
        "answer": "A micturating cystourethrogram evaluates reflux in the appropriate clinical context.",
        "options": [
            {"id": "A", "text": "Renal biopsy"},
            {"id": "B", "text": "Micturating cystourethrogram"},
            {"id": "C", "text": "Plain abdominal radiograph"},
            {"id": "D", "text": "Serum creatinine alone"},
            {"id": "E", "text": "Uroflowmetry alone"},
        ],
        "correct_option_id": "B",
        "course_outcome_refs": permitted_refs[:1],
        "evidence_claims": [
            {"claim": "MCUG is used to assess vesicoureteral reflux.", "source_id": "PMID:12345"}
        ],
        "difficulty": "intermediate",
        "learning_point": "Select imaging according to the suspected pathology.",
    })


def test_generation_uses_retrieved_sources_and_returns_unapproved_draft(monkeypatch, pubmed_record):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("USIPHU_OLLAMA_MODEL", "qwen2.5:7b")
    monkeypatch.setattr(ai, "_ollama_chat", lambda prompt, model: _model_response(prompt))
    monkeypatch.setattr(ai, "retrieve_pubmed_evidence", lambda query, max_results: [pubmed_record])

    result = generate_topic_cards("urology", "pujo", evidence_limit=3)

    assert result["draft_cards"] == result["total_objectives"]
    card = result["results"][0]["card"]
    assert card["review_status"] == "draft"
    assert card["source_url"] == pubmed_record["source_url"]
    assert card["evidence_claims"][0]["source_id"] == "PMID:12345"
    assert result["results"][0]["clinical_review_required"] is True
    assert result["results"][0]["review_packet"]["automatic_approval_prohibited"] is True
    assert card["review_packet"]["status"] == "human_review_required"
    assert result["clinical_approval_granted"] is False
    assert result["provider"]["provider"] == "ollama"


def test_generation_returns_evidence_gate_without_making_a_card(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr(ai, "_ollama_chat", lambda prompt, model: pytest.fail("must not call model"))
    monkeypatch.setattr(ai, "retrieve_pubmed_evidence", lambda query, max_results: [])

    result = generate_topic_cards("urology", "pujo")

    assert result["draft_cards"] == 0
    assert all(item["status"] == "needs_evidence_review" for item in result["results"])
    assert all(item["card"] is None for item in result["results"])


def test_generation_fails_when_ollama_endpoint_is_not_configured(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    with pytest.raises(GenerationNotConfigured):
        generate_topic_cards("urology", "pujo")


def test_external_pediatrics_never_gets_official_suez_alignment(monkeypatch, pubmed_record):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr(ai, "_ollama_chat", lambda prompt, model: _model_response(prompt))
    monkeypatch.setattr(ai, "retrieve_pubmed_evidence", lambda query, max_results: [pubmed_record])

    result = generate_topic_cards("paediatrics", "neonatal-resuscitation")
    for item in result["results"]:
        if item.get("card"):
            assert item["card"]["external_benchmark_only"] is True
            assert item["card"]["official_suez_alignment"] is False


def test_ollama_chat_sends_json_mode(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"message": {"content": '{"ok": true}'}}).encode()

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode())
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setattr(ai, "urlopen", fake_urlopen)

    assert ai._ollama_chat("prompt", "qwen2.5:7b") == '{"ok": true}'
    assert captured["url"] == "http://ollama:11434/api/chat"
    assert captured["payload"]["format"] == "json"
    assert captured["payload"]["stream"] is False


def test_model_output_must_be_json_object(monkeypatch, pubmed_record):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr(ai, "_ollama_chat", lambda prompt, model: "[]")
    with pytest.raises(ValueError, match="JSON object"):
        ai._author_one(
            {"brief_id": "b", "course_outcome_mapping_status": "direct",
             "official_suez_outcomes": [], "external_benchmark_outcomes": []},
            [pubmed_record], "qwen2.5:7b"
        )
