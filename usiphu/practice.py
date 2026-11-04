"""Load and validate authored practice banks from versioned JSON files."""
import json
from pathlib import Path

from usiphu.models import MCQ, ClinicalCase

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_questions(path: Path = DATA_DIR / "questions.json") -> list[MCQ]:
    with path.open(encoding="utf-8") as stream:
        questions = [MCQ.model_validate(item) for item in json.load(stream)]
    for question in questions:
        if question.correct_option_id not in {option.id for option in question.options}:
            raise ValueError(f"Question {question.id} references a missing correct option")
    return questions


def load_cases(path: Path = DATA_DIR / "cases.json") -> list[ClinicalCase]:
    with path.open(encoding="utf-8") as stream:
        return [ClinicalCase.model_validate(item) for item in json.load(stream)]


def filter_questions(
    questions: list[MCQ],
    specialty_id: str | None = None,
    topic_id: str | None = None,
    difficulty: str | None = None,
    review_status: str | None = None,
    question_type: str | None = None,
) -> list[MCQ]:
    """Return a deterministic filtered view of the authored bank."""
    return [
        question for question in questions
        if (not specialty_id or question.specialty_id == specialty_id)
        and (not topic_id or question.topic_id == topic_id)
        and (not difficulty or question.difficulty == difficulty)
        and (not review_status or question.review_status == review_status)
        and (not question_type or question.question_type == question_type)
    ]
