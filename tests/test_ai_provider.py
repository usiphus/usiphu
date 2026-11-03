"""Tests for configured AI generation, evidence gating, and provenance mapping."""
import json

import pytest

import usiphu.ai_provider as ai
from usiphu.ai_provider import GenerationNotConfigured, generate_topic_cards


class FakeCompletions:
    def create(self, **kwargs):
        prompt = kwargs["messages"][1]["content"]
        brief_json = prompt.split("CURRICULUM BRIEF:\\n", 1)[1].split(
            "\\n\\nPERMITTED COURSE OUTCOME REFERENCES:", 1
        )[0]
        brief = json.loads(brief_json)
        refs_json = prompt.split("PERMITTED COURSE OUTCOME REFERENCES:\\n", 1)[1].split(
            "\\n\\nRETRIEVED PUBMED EVIDENCE", 1
        )[0]
        permitted_refs = json.loads(refs_json)
        content = {
            "card_type": "mcq",
            "prompt": "A child has unilateral hydroureteronephrosis. Which investigation best evaluates vesicoureteral reflux?",
            "answer": "A micturating cystourethrogram evaluates reflux; interpret in the clinical context.",
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
        }
        message = type("Message", (), {"content": json.dumps(content)})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeCompletions()})()


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


def test_generation_uses_retrieved_sources_and_returns_unapproved_draft(monkeypatch, pubmed_record):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai, "_openai_client", lambda: FakeClient())
    monkeypatch.setattr(ai, "retrieve_pubmed_evidence", lambda query, max_results: [pubmed_record])

    result = generate_topic_cards("urology", "pujo", evidence_limit=3)

    assert result["draft_cards"] == result["total_objectives"]
    card = result["results"][0]["card"]
    assert card["review_status"] == "draft"
    assert card["source_url"] == pubmed_record["source_url"]
    assert card["evidence_claims"][0]["source_id"] == "PMID:12345"
    assert card["clinical_review_required"] is True
    assert result["clinical_approval_granted"] is False


def test_generation_returns_evidence_gate_without_making_a_card(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai, "_openai_client", lambda: FakeClient())
    monkeypatch.setattr(ai, "retrieve_pubmed_evidence", lambda query, max_results: [])

    result = generate_topic_cards("urology", "pujo")

    assert result["draft_cards"] == 0
    assert all(item["status"] == "needs_evidence_review" for item in result["results"])
    assert all(item["card"] is None for item in result["results"])


def test_generation_fails_before_retrieval_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(GenerationNotConfigured):
        generate_topic_cards("urology", "pujo")


def test_external_pediatrics_never_gets_official_suez_alignment(monkeypatch, pubmed_record):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai, "_openai_client", lambda: FakeClient())
    monkeypatch.setattr(ai, "retrieve_pubmed_evidence", lambda query, max_results: [pubmed_record])

    result = generate_topic_cards("paediatrics", "neonatal-resuscitation")
    for item in result["results"]:
        if item.get("card"):
            assert item["card"]["external_benchmark_only"] is True
            assert item["card"]["official_suez_alignment"] is False
