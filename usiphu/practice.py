"""Load, validate and filter versioned medical question banks and clinical cases."""
import json
from pathlib import Path

from usiphu.database import is_postgres
from usiphu.models import MCQ, ClinicalCase
from usiphu.storage import DEFAULT_DB, connect, initialize

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
    if directory.exists():
        for bank_path in sorted(directory.glob("*.json")):
            questions.extend(_read_question_file(bank_path, bank_path.stem))
    # Hosted question-bank additions are persisted in Postgres rather than the ephemeral app filesystem.
    if is_postgres():
        initialize(DEFAULT_DB)
        with connect(DEFAULT_DB) as db:
            approved_rows = db.execute(
                "SELECT payload_json FROM approved_question_bank ORDER BY created_at, question_id"
            ).fetchall()
        questions.extend(MCQ.model_validate(json.loads(row["payload_json"])) for row in approved_rows)

    # Faculty sign-off is an append-only audit trail. Overlay its latest two-stage state.
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
