"""Tests for source-grounded generator briefs and strict draft validation."""
from usiphu.generator import (
    build_generation_briefs,
    validate_generated_card,
    validate_generation_batch,
)


def test_briefs_bind_objectives_to_official_suez_outcomes():
    briefs = build_generation_briefs(specialty_id="urology", topic_id="pujo")
    assert len(briefs) == 2
    brief = briefs[0]
    assert brief["course_outcome_mapping_status"] == "direct_course_outcome"
    assert [row["id"] for row in brief["official_suez_outcomes"]] == ["SI-URO-01"]
    assert not brief["external_benchmark_outcomes"]
    assert brief["generation_status"] == "brief_ready"


def test_pediatrics_briefs_preserve_external_only_provenance():
    briefs = build_generation_briefs(specialty_id="paediatrics", topic_id="neonatal-resuscitation")
    assert briefs
    brief = briefs[0]
    assert brief["course_outcome_mapping_status"] == "external_benchmark_only"
    assert not brief["official_suez_outcomes"]
    assert brief["external_benchmark_outcomes"]
    assert all(row["provenance"] == "external_benchmark_only"
               for row in brief["external_benchmark_outcomes"])


def test_unknown_topic_fails_closed():
    try:
        build_generation_briefs(topic_id="not-a-real-topic")
    except KeyError as exc:
        assert "Unknown topic" in str(exc)
    else:
        raise AssertionError("Unknown topic should not silently produce an empty job")


def valid_mcq(brief):
    return {
        "brief_id": brief["brief_id"],
        "id": "test-card-1",
        "card_type": "mcq",
        "specialty_id": brief["specialty_id"],
        "topic_id": brief["topic_id"],
        "prompt": "A sufficiently specific exam-style question?",
        "answer": "A concise rationale.",
        "options": [{"id": f"o{i}", "text": f"Option {i}"} for i in range(1, 6)],
        "correct_option_id": "o2",
        "source_title": "Clinical guideline",
        "source_url": "https://example.org/guideline",
        "source_date": "2025-01-01",
        "course_outcome_refs": [row["id"] for row in brief["official_suez_outcomes"]],
        "evidence_claims": [{"claim": "The key clinical claim.", "source_url": "https://example.org/guideline"}],
        "review_status": "draft",
    }


def test_valid_card_is_accepted_only_as_draft_and_requires_human_review():
    brief = build_generation_briefs(specialty_id="urology", topic_id="pujo")[0]
    result = validate_generated_card(valid_mcq(brief), brief)
    assert result["valid"]
    assert result["review_status"] == "draft"
    assert result["clinical_review_required"]
    assert result["exam_validation_required"]


def test_generator_rejects_wrong_ilo_provenance_and_non_draft():
    brief = build_generation_briefs(specialty_id="urology", topic_id="pujo")[0]
    card = valid_mcq(brief)
    card["course_outcome_refs"] = ["EXT-PED-K-01"]
    card["review_status"] = "exam_validated"
    result = validate_generated_card(card, brief)
    assert not result["valid"]
    assert any("permitted outcomes" in error for error in result["errors"])
    assert any("draft" in error for error in result["errors"])


def test_external_benchmark_card_cannot_claim_official_suez_alignment():
    brief = build_generation_briefs(specialty_id="paediatrics", topic_id="neonatal-resuscitation")[0]
    card = valid_mcq(brief)
    card["course_outcome_refs"] = [row["id"] for row in brief["external_benchmark_outcomes"]]
    card["external_benchmark_only"] = True
    card["official_suez_alignment"] = True
    result = validate_generated_card(card, brief)
    assert not result["valid"]
    assert any("cannot claim official Suez" in error for error in result["errors"])


def test_batch_rejects_duplicate_prompts_and_unknown_briefs():
    brief = build_generation_briefs(specialty_id="urology", topic_id="pujo")[0]
    first = valid_mcq(brief)
    second = {**valid_mcq(brief), "id": "test-card-2"}
    result = validate_generation_batch([first, second, {"id": "orphan"}], [brief])
    assert result["accepted_as_draft"] == 1
    assert result["rejected"] == 2
    assert result["clinical_approval_granted"] is False



def test_generated_card_rejects_evidence_sources_outside_retrieved_packet():
    brief = build_generation_briefs(specialty_id="urology", topic_id="pujo")[0]
    card = valid_mcq(brief)
    card["evidence_sources"] = [{
        "source_id": "PMID:111",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/111/",
    }]
    card["source_url"] = "https://example.org/not-retrieved"
    card["evidence_claims"] = [{
        "claim": "An unsupported claim.",
        "source_id": "PMID:222",
        "source_url": "https://example.org/not-retrieved",
    }]
    result = validate_generated_card(card, brief)
    assert not result["valid"]
    assert any("retrieved evidence packet" in error for error in result["errors"])
