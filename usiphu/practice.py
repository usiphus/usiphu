"""Load, validate and filter versioned medical question banks and clinical cases."""
import json
import os
from pathlib import Path

from usiphu.models import MCQ, ClinicalCase

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_question_file(path: Path, default_bank_id: str) -> list[MCQ]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        bank_id = payload.get("bank_id", default_bank_id)
        raw_questions = payload.get("questions", [])
    else:
        bank_id = default_bank_id
        raw_questions = payload
    if not isinstance(raw_questions, list):
        raise ValueError(f"Question bank {path} must contain a questions list")
    questions = [
        MCQ.model_validate({**item, "bank_id": item.get("bank_id", bank_id)})
        for item in raw_questions
    ]
    for question in questions:
        if question.correct_option_id not in {option.id for option in question.options}:
            raise ValueError(f"Question {question.id} references a missing correct option")
    return questions


def load_questions(
    path: Path | None = None, bank_dir: Path | None = None
) -> list[MCQ]:
    """Load the starter bank plus every installed JSON bank; IDs must be globally unique.

    Passing path loads only that file, preserving isolated-file validation workflows.
    """
    if path is not None:
        return _read_question_file(path, "custom-bank")
    questions = _read_question_file(DATA_DIR / "questions.json", "starter-medical-bank")
    directory = bank_dir or DATA_DIR / "question_banks"
    remote_bank_enabled = os.getenv(
        "USIPHU_FILE_STORAGE_BACKEND", "local"
    ).strip().lower() == "supabase"
    if directory.exists():
        for bank_path in sorted(directory.glob("*.json")):
            if remote_bank_enabled and bank_path.name == "past_papers_reviewed.json":
                continue
            questions.extend(_read_question_file(bank_path, bank_path.stem))
    from usiphu.durable_documents import load_json_document, remote_documents_enabled
    if remote_documents_enabled():
        remote_bank = load_json_document(
            "question-bank:past-papers-reviewed",
            directory / "past_papers_reviewed.json",
            {"questions": []},
        )
        questions.extend(
            MCQ.model_validate(item) for item in remote_bank.get("questions", [])
        )
    # Pilot sign-off is stored in PostgreSQL as an append-only faculty audit trail.
    # Overlay the latest two-stage release state without mutating source JSON.
    from usiphu.faculty_review import faculty_release_statuses

    release_states = faculty_release_statuses()
    questions = [
        question.model_copy(update=release_states[question.id])
        if question.id in release_states and question.bank_id.startswith("pilot-")
        else question
        for question in questions
    ]
    identifiers = [question.id for question in questions]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Question IDs must be unique across all installed banks")
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
    bank_id: str | None = None,
) -> list[MCQ]:
    """Return a deterministic filtered view of the authored bank."""
    return [
        question for question in questions
        if (not specialty_id or question.specialty_id == specialty_id)
        and (not topic_id or question.topic_id == topic_id)
        and (not difficulty or question.difficulty == difficulty)
        and (not review_status or question.review_status == review_status)
        and (not question_type or question.question_type == question_type)
        and (not bank_id or question.bank_id == bank_id)
    ]
