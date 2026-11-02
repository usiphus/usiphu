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
