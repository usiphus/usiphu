"""Build provenance-bound generation briefs and validate generated exam cards.

This module deliberately does not invent clinical facts or call an unconfigured LLM.
It prepares deterministic, source-grounded jobs for a future model adapter and
rejects outputs that lose curriculum, ILO, or evidence provenance.
"""
import json
import re
from pathlib import Path
from typing import Any

from usiphu.curriculum import load_curriculum

ROOT = Path(__file__).resolve().parent.parent
PROFILE_FILE = ROOT / "data" / "suez_university_curriculum.json"
ILO_FILE = ROOT / "data" / "suez_course_ilos.json"
EXAM_BLUEPRINT_FILE = ROOT / "data" / "specialty_exam_blueprints.json"
EXAM_FORMATS = {
    "mixed": ["mcq", "short_answer", "clinical_case", "osce_station", "viva", "emq"],
    "mcq": ["mcq"],
    "short_answer": ["short_answer"],
    "clinical_case": ["clinical_case"],
    "osce": ["osce_station"],
    "viva": ["viva"],
    "emq": ["emq"],
}
SUPPORTED_CARD_TYPES = {item for values in EXAM_FORMATS.values() for item in values}
VALID_MAPPING_STATUSES = {
    "direct_course_outcome", "partial_related_outcome",
    "external_benchmark_only", "module_only_no_specific_ilo",
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _catalog_index(catalog: dict[str, Any]) -> tuple[dict[str, dict], dict[str, dict]]:
    official = {
        outcome["id"]: {**outcome, "provenance": "official_suez_course_specification"}
        for module in catalog["modules"] for outcome in module["outcomes"]
    }
    external = {
        outcome["id"]: {
            **outcome, "provenance": "external_benchmark_only",
            "source_id": benchmark["source_id"],
        }
        for benchmark in catalog["external_benchmarks"]
        for outcome in benchmark["outcome_groups"]
    }
    return official, external


def build_generation_briefs(
    specialty_id: str | None = None,
    topic_id: str | None = None,
    *,
    curriculum_path: Path | None = None,
    profile_path: Path = PROFILE_FILE,
    catalog_path: Path = ILO_FILE,
    exam_format: str = "mixed",
    blueprint_path: Path = EXAM_BLUEPRINT_FILE,
) -> list[dict[str, Any]]:
    """Compile one bounded, traceable generation brief per learning objective."""
    if exam_format not in EXAM_FORMATS:
        raise ValueError(f"Unsupported exam_format: {exam_format}")
    curriculum = load_curriculum(curriculum_path) if curriculum_path else load_curriculum()
    profile = _load_json(profile_path)
    exam_blueprints = _load_json(blueprint_path)
    default_blueprint = exam_blueprints["default"]
    catalog = _load_json(catalog_path)
    official, external = _catalog_index(catalog)
    crosswalk = {row["topic_id"]: row for row in catalog["topic_crosswalk"]}
    profile_topics = {row["topic_id"]: row for row in profile["topics"]}
    briefs: list[dict[str, Any]] = []

    for specialty in curriculum.specialties:
        if specialty_id and specialty.id != specialty_id:
            continue
        for domain in specialty.domains:
            for topic in domain.topics:
                if topic_id and topic.id != topic_id:
                    continue
                mapping = crosswalk.get(topic.id)
                profile_mapping = profile_topics.get(topic.id, {})
                status = (
                    mapping["status"] if mapping else
                    profile_mapping.get("course_outcome_mapping_status", "unmapped")
                )
                if status not in VALID_MAPPING_STATUSES:
                    status = "unmapped"
                refs = mapping.get("outcome_refs", []) if mapping else []
                is_external = status == "external_benchmark_only"
                index = external if is_external else official
                outcomes = [index[ref] for ref in refs if ref in index]
                if len(outcomes) != len(refs):
                    raise ValueError(f"Unresolved or incorrectly classified ILO refs for {topic.id}")
                specialty_blueprint = exam_blueprints["specialties"].get(
                    specialty.id, {**default_blueprint, "title": specialty.title}
                )
                for objective in topic.objectives:
                    brief_id = f"{specialty.id}:{topic.id}:{objective.id}"
                    briefs.append({
                        "brief_id": brief_id,
                        "specialty_id": specialty.id,
                        "specialty": specialty.title,
                        "domain_id": domain.id,
                        "domain": domain.title,
                        "topic_id": topic.id,
                        "topic": topic.title,
                        "objective_id": objective.id,
                        "objective": objective.text,
                        "objective_level": objective.level,
                        "exam_weight": topic.exam_weight,
                        "curriculum_source_refs": topic.source_refs,
                        "course_outcome_mapping_status": status,
                        "official_suez_outcomes": outcomes if not is_external else [],
                        "external_benchmark_outcomes": outcomes if is_external else [],
                        "generation_status": "brief_ready",
                        "requested_exam_format": exam_format,
                        "specialty_exam_blueprint": specialty_blueprint,
                        "output_contract": {
                            "allowed_card_types": EXAM_FORMATS[exam_format],
                            "required_review_status": "draft",
                            "required_provenance_fields": [
                                "source_title", "source_url", "source_date",
                                "evidence_claims", "course_outcome_refs",
                            ],
                            "clinical_safety": [
                                "Do not invent doses, thresholds, guideline recommendations, or local protocols.",
                                "If evidence is insufficient or conflicting, return needs_evidence_review; do not guess.",
                                "Use only official_suez_outcomes as official Suez alignment.",
                                "Never relabel external_benchmark_outcomes as official Suez outcomes.",
                                "Do not claim faculty approval, clinical review, or exam validation.",
                                "Use the learner objective as the scope boundary; avoid unrelated facts.",
                            ],
                        },
                    })
    if topic_id and not briefs:
        raise KeyError(f"Unknown topic or topic has no objectives: {topic_id}")
    return briefs


def validate_generated_card(
    card: dict[str, Any], brief: dict[str, Any], *,
    existing_cards: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate structure, provenance, alignment and duplicates; never approve clinically."""
    errors: list[str] = []
    required = {"id", "card_type", "specialty_id", "topic_id", "prompt", "answer",
                "source_title", "source_url", "source_date", "course_outcome_refs",
                "evidence_claims", "review_status"}
    missing = sorted(required - card.keys())
    if missing:
        errors.append("Missing required fields: " + ", ".join(missing))
    if card.get("specialty_id") != brief["specialty_id"] or card.get("topic_id") != brief["topic_id"]:
        errors.append("Card specialty/topic does not match its generation brief")
    if card.get("review_status") != "draft":
        errors.append("Generated cards must enter the system as draft")
    allowed_types = set(brief.get("output_contract", {}).get(
        "allowed_card_types", EXAM_FORMATS["mixed"]
    ))
    if (card.get("card_type") not in SUPPORTED_CARD_TYPES
            or card.get("card_type") not in allowed_types):
        errors.append("card_type is unsupported or does not match the requested exam format")
    for field in ("id", "prompt", "answer", "source_title", "source_url", "source_date"):
        if not isinstance(card.get(field), str) or not card[field].strip():
            errors.append(f"{field} must be a non-empty string")
    if isinstance(card.get("source_url"), str) and not re.match(r"^https?://", card["source_url"]):
        errors.append("source_url must be an HTTP(S) URL")
    if not isinstance(card.get("evidence_claims"), list) or not card.get("evidence_claims"):
        errors.append("At least one traceable evidence_claim is required")
    elif any(not isinstance(claim, dict) or not claim.get("claim") or
             not claim.get("source_url") for claim in card["evidence_claims"]):
        errors.append("Each evidence_claim needs claim and source_url")
    evidence_sources = card.get("evidence_sources")
    if evidence_sources is not None:
        if not isinstance(evidence_sources, list) or not evidence_sources:
            errors.append("evidence_sources must be a non-empty list when supplied")
        else:
            source_urls = {item.get("source_url") for item in evidence_sources
                           if isinstance(item, dict) and item.get("source_id")}
            source_ids = {item.get("source_id") for item in evidence_sources
                          if isinstance(item, dict) and item.get("source_id")}
            if card.get("source_url") not in source_urls:
                errors.append("Primary source URL must come from the retrieved evidence packet")
            for claim in card.get("evidence_claims", []):
                if isinstance(claim, dict) and (
                    claim.get("source_url") not in source_urls or
                    claim.get("source_id") not in source_ids
                ):
                    errors.append("Evidence claim references a source outside the retrieved packet")
                    break
    allowed_refs = {
        item["id"] for item in (
            brief["external_benchmark_outcomes"] if brief["course_outcome_mapping_status"] ==
            "external_benchmark_only" else brief["official_suez_outcomes"]
        )
    }
    refs = card.get("course_outcome_refs")
    if (not isinstance(refs, list) or (allowed_refs and not refs)
            or any(ref not in allowed_refs for ref in refs)):
        errors.append("course_outcome_refs must include only permitted outcomes and cannot be empty when mapped")
    if brief["course_outcome_mapping_status"] == "external_benchmark_only":
        if card.get("official_suez_alignment") not in (None, False):
            errors.append("External benchmark content cannot claim official Suez alignment")
        if not card.get("external_benchmark_only", False):
            errors.append("External Pediatrics benchmark cards must retain external_benchmark_only=true")
    elif card.get("external_benchmark_only", False):
        errors.append("Non-external topic cannot be labelled as an external-only benchmark")
    if card.get("card_type") == "osce_station":
        for field in ("station_tasks", "marking_criteria"):
            value = card.get(field)
            if not isinstance(value, list) or len(value) < 2 or any(not str(item).strip() for item in value):
                errors.append(f"osce_station requires at least two non-empty {field}")
    if card.get("card_type") == "viva":
        questions = card.get("viva_questions")
        if not isinstance(questions, list) or len(questions) < 2:
            errors.append("viva requires at least two viva_questions")
    if card.get("card_type") == "emq":
        options = card.get("options")
        items = card.get("emq_items")
        if (not isinstance(options, list) or len(options) < 5
                or any(not isinstance(o, dict) or not o.get("id") or not o.get("text")
                       for o in options)):
            errors.append("emq requires at least five labelled options")
        elif (not isinstance(items, list) or len(items) < 2
              or any(not isinstance(item, dict) or not item.get("stem")
                     or item.get("correct_option_id") not in {o["id"] for o in options}
                     for item in items)):
            errors.append("emq requires at least two stems keyed to the option list")
    if card.get("card_type") == "mcq":
        options = card.get("options")
        if not isinstance(options, list) or len(options) != 5:
            errors.append("MCQ requires exactly five options")
        elif (any(not isinstance(option, dict) or not option.get("id") or
                  not option.get("text") for option in options) or
              len({option.get("id") for option in options if isinstance(option, dict)}) != 5):
            errors.append("MCQ options require five unique IDs and non-empty text")
        elif card.get("correct_option_id") not in {option["id"] for option in options}:
            errors.append("correct_option_id must reference one of the five options")
    if existing_cards:
        normalized = re.sub(r"\W+", " ", str(card.get("prompt", "")).casefold()).strip()
        for existing in existing_cards:
            other = re.sub(r"\W+", " ", str(existing.get("prompt", "")).casefold()).strip()
            if normalized and normalized == other:
                errors.append(f"Duplicate prompt matches existing card {existing.get('id', 'unknown')}")
                break
    return {
        "valid": not errors,
        "errors": errors,
        "review_status": "draft",
        "clinical_review_required": True,
        "exam_validation_required": True,
        "card": card if not errors else None,
    }


def validate_generation_batch(
    cards: list[dict[str, Any]], briefs: list[dict[str, Any]],
    existing_cards: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate a batch and detect duplicates within the batch as well as the bank."""
    by_id = {brief["brief_id"]: brief for brief in briefs}
    seen: list[dict[str, Any]] = list(existing_cards or [])
    results = []
    for card in cards:
        brief = by_id.get(card.get("brief_id"))
        if not brief:
            results.append({"valid": False, "errors": ["Unknown or missing brief_id"],
                            "review_status": "draft", "clinical_review_required": True,
                            "exam_validation_required": True, "card": None})
            continue
        result = validate_generated_card(card, brief, existing_cards=seen)
        results.append(result)
        if result["valid"]:
            seen.append(card)
    return {
        "total": len(cards),
        "accepted_as_draft": sum(item["valid"] for item in results),
        "rejected": sum(not item["valid"] for item in results),
        "clinical_approval_granted": False,
        "results": results,
    }
