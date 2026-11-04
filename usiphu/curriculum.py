"""Load and analyze the versioned curriculum blueprint."""
import json
from pathlib import Path

from usiphu.models import Curriculum

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "curriculum.json"


def load_curriculum(path: Path = DATA_FILE) -> Curriculum:
    with path.open(encoding="utf-8") as stream:
        return Curriculum.model_validate(json.load(stream))


def flatten_topics(curriculum: Curriculum) -> list[dict[str, str]]:
    return [
        {
            "specialty_id": specialty.id,
            "specialty": specialty.title,
            "domain_id": domain.id,
            "domain": domain.title,
            "topic_id": topic.id,
            "topic": topic.title,
            "objectives": str(len(topic.objectives)),
            "coverage_status": topic.coverage_status,
            "source_refs": ", ".join(topic.source_refs),
        }
        for specialty in curriculum.specialties
        for domain in specialty.domains
        for topic in domain.topics
    ]


def coverage_summary(curriculum: Curriculum) -> dict[str, int | float]:
    topics = [topic for specialty in curriculum.specialties
              for domain in specialty.domains for topic in domain.topics]
    objective_count = sum(len(topic.objectives) for topic in topics)
    covered = sum(bool(topic.objectives) for topic in topics)
    return {
        "specialties": len(curriculum.specialties),
        "domains": sum(len(specialty.domains) for specialty in curriculum.specialties),
        "topics": len(topics),
        "objectives": objective_count,
        "topics_with_objectives": covered,
        "objective_coverage_percent": round(100 * covered / len(topics), 1) if topics else 0.0,
        "topics_sourced": sum(topic.coverage_status in {"sourced", "reviewed", "exam_validated"}
                              for topic in topics),
        "topics_reviewed": sum(topic.coverage_status in {"reviewed", "exam_validated"}
                               for topic in topics),
        "topics_exam_validated": sum(topic.coverage_status == "exam_validated" for topic in topics),
        "topics_planned": sum(topic.coverage_status == "planned" for topic in topics),
        "topics_unmapped": sum(topic.coverage_status == "mapped" and not topic.source_refs for topic in topics),
    }
