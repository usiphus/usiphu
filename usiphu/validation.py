"""Cross-check curriculum, practice content, and editorial review requirements."""
import json

from usiphu.coverage import coverage_report, validate_coverage_register
from usiphu.curriculum import coverage_summary, load_curriculum
from usiphu.practice import load_cases, load_questions
from usiphu.suez_ilo_transcription import validate_transcriptions


def validate_content() -> dict[str, int | float | str | None]:
    curriculum = load_curriculum()
    specialty_ids = [specialty.id for specialty in curriculum.specialties]
    domain_ids = [domain.id for specialty in curriculum.specialties for domain in specialty.domains]
    topic_ids = [topic.id for specialty in curriculum.specialties
                 for domain in specialty.domains for topic in domain.topics]
    objective_ids = [objective.id for specialty in curriculum.specialties
                     for domain in specialty.domains for topic in domain.topics
                     for objective in topic.objectives]

    for label, identifiers in (
        ("specialty", specialty_ids), ("domain", domain_ids),
        ("topic", topic_ids), ("objective", objective_ids),
    ):
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"Duplicate {label} IDs found in curriculum")

    topic_pairs = {
        (specialty.id, topic.id)
        for specialty in curriculum.specialties
        for domain in specialty.domains
        for topic in domain.topics
    }
    for specialty in curriculum.specialties:
        for domain in specialty.domains:
            for topic in domain.topics:
                if not topic.objectives:
                    raise ValueError(f"Mapped topic {topic.id} has no learning objectives")
                if topic.coverage_status in {"sourced", "reviewed", "exam_validated"} and not topic.source_refs:
                    raise ValueError(f"Topic {topic.id} is marked sourced but has no source references")
                if topic.coverage_status in {"reviewed", "exam_validated"} and not (
                    topic.reviewed_by and topic.reviewed_at
                ):
                    raise ValueError(f"Topic {topic.id} is marked reviewed without reviewer metadata")
                if topic.coverage_status == "exam_validated" and not topic.syllabus_refs:
                    raise ValueError(f"Topic {topic.id} is exam-validated without syllabus references")

    questions = load_questions()
    cases = load_cases()
    bank_manifest_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "question_bank_manifest.json"
    bank_manifest = json.loads(bank_manifest_path.read_text(encoding="utf-8"))
    if bank_manifest["current_content"]["question_count"] != len(questions):
        raise ValueError("Question bank manifest count does not match loaded question content")
    for item in [*questions, *cases]:
        if (item.specialty_id, item.topic_id) not in topic_pairs:
            raise ValueError(f"Practice item {item.id} points to an unknown specialty/topic")
        if item.review_status in {"clinically_reviewed", "exam_validated"} and not (
            item.source_url and item.source_title and item.reviewed_by and item.reviewed_at
        ):
            raise ValueError(f"Practice item {item.id} is reviewed without complete provenance")
        if item.review_status == "exam_validated" and not item.jurisdiction:
            raise ValueError(f"Practice item {item.id} is exam-validated without a jurisdiction")

    summary = coverage_summary(curriculum)
    coverage_integrity = validate_coverage_register()
    transcription_integrity = validate_transcriptions()
    return {
        **summary,
        **coverage_report(),
        **coverage_integrity,
        **transcription_integrity,
        "questions": len(questions),
        "question_banks": len({item.bank_id for item in questions}),
        "cases": len(cases),
        "draft_questions": sum(item.review_status == "draft" for item in questions),
        "draft_cases": sum(item.review_status == "draft" for item in cases),
        "target_syllabus": curriculum.target_syllabus,
    }


if __name__ == "__main__":
    print(json.dumps(validate_content(), indent=2))
