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
        "evidence_sources": [{
            "source_id": "PMID:123", "source_title": "Clinical guideline",
            "source_url": "https://example.org/guideline", "source_date": "2025-01-01",
        }],
        "learning_point": "Recognize the key clinical pattern.",
        "difficulty": "intermediate",
        "course_outcome_refs": [row["id"] for row in brief["official_suez_outcomes"]],
        "evidence_claims": [{"claim": "The key clinical claim.", "source_id": "PMID:123", "source_url": "https://example.org/guideline"}],
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


def test_expanded_curriculum_and_specialty_blueprint_are_used():
    briefs = build_generation_briefs(
        specialty_id="anatomy", topic_id="upper-limb-anatomy", exam_format="osce"
    )
    assert len(briefs) == 2
    brief = briefs[0]
    assert brief["requested_exam_format"] == "osce"
    assert brief["output_contract"]["allowed_card_types"] == ["osce_station"]
    assert "surface-landmark viva" in brief["specialty_exam_blueprint"]["preferred_formats"]


def test_unsupported_exam_format_fails_closed():
    try:
        build_generation_briefs(exam_format="image_based")
    except ValueError as exc:
        assert "Unsupported exam_format" in str(exc)
    else:
        raise AssertionError("Unsupported exam format should fail closed")


def test_osce_station_requires_tasks_and_observable_marking_criteria():
    brief = build_generation_briefs(
        specialty_id="anatomy", topic_id="upper-limb-anatomy", exam_format="osce"
    )[0]
    card = valid_mcq(brief)
    card.update({
        "card_type": "osce_station",
        "station_tasks": ["Take a focused history", "Demonstrate relevant examination"],
        "marking_criteria": ["Identifies key findings", "Explains anatomical localization"],
    })
    result = validate_generated_card(card, brief)
    assert result["valid"]
    card["marking_criteria"] = []
    rejected = validate_generated_card(card, brief)
    assert not rejected["valid"]
    assert any("marking_criteria" in error for error in rejected["errors"])


def test_valid_card_returns_specialty_specific_human_review_packet():
    brief = build_generation_briefs(specialty_id="urology", topic_id="pujo")[0]
    result = validate_generated_card(valid_mcq(brief), brief)
    packet = result["review_packet"]
    assert result["valid"]
    assert packet["status"] == "human_review_required"
    assert packet["automatic_approval_prohibited"] is True
    assert any("adult from paediatric" in item.lower() or "obstruction" in item.lower()
               for item in packet["specialty_safety_checks"])
    assert packet["format_checks"]


def test_validator_rejects_untraceable_claim_and_duplicate_mcq_options():
    brief = build_generation_briefs(specialty_id="urology", topic_id="pujo")[0]
    card = valid_mcq(brief)
    card["evidence_claims"][0]["source_id"] = "PMID:999"
    card["options"][4]["text"] = card["options"][0]["text"]
    result = validate_generated_card(card, brief)
    assert not result["valid"]
    assert any("outside the retrieved packet" in error for error in result["errors"])
    assert any("distinct text" in error for error in result["errors"])


def test_new_medical_topics_are_explicitly_unmapped_in_generation_briefs():
    briefs = build_generation_briefs(
        specialty_id="anatomy", topic_id="upper-limb-anatomy", exam_format="mcq"
    )
    assert briefs
    brief = briefs[0]
    assert brief["course_outcome_mapping_status"] == "not_mapped_no_verified_course_outcome"
    assert brief["objective_mapping_status"] == "not_mapped_no_verified_course_outcome"
    assert brief["official_suez_outcomes"] == []
    assert brief["external_benchmark_outcomes"] == []
