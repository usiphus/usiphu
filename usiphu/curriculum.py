"""Curriculum loading, lookup, and coverage reporting."""
from __future__ import annotations

import json
from pathlib import Path

from usiphu.models import Curriculum

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "curriculum.json"


def load_curriculum(path: Path = DATA_FILE) -> Curriculum:
    with path.open(encoding="utf-8") as handle:
        return Curriculum.model_validate(json.load(handle))


def flatten_topics(curriculum: Curriculum) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for specialty in curriculum.specialties:
        for domain in specialty.domains:
            for topic in domain.topics:
                rows.append({
                    "specialty_id": specialty.id,
                    "specialty": specialty.title,
                    "domain_id": domain.id,
                    "domain": domain.title,
                    "topic_id": topic.id,
                    "topic": topic.title,
                    "objectives": str(len(topic.objectives)),
                })
    return rows


def coverage_summary(curriculum: Curriculum) -> dict[str, int | float]:
    topics = [topic for specialty in curriculum.specialties
              for domain in specialty.domains for topic in domain.topics]
    objectives = [objective for topic in topics for objective in topic.objectives]
    return {
        "specialties": len(curriculum.specialties),
        "domains": sum(len(s.domains) for s in curriculum.specialties),
        "topics": len(topics),
        "objectives": len(objectives),
        "topics_with_objectives": sum(bool(topic.objectives) for topic in topics),
        "objective_coverage_percent": round(100 * sum(bool(t.objectives) for t in topics) / len(topics), 1) if topics else 0.0,
    }
