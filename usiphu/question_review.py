"""Human review and controlled promotion of extracted past-paper MCQs."""
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from usiphu.curriculum import load_curriculum
from usiphu.models import MCQ
from usiphu.practice import DATA_DIR
from usiphu.database import is_postgres
from usiphu.extraction import load_extraction, save_extraction
from usiphu.storage import DEFAULT_DB, connect, initialize
from usiphu.source_inbox import DEFAULT_SOURCE_DIR, list_sources

QUESTION_BANK_PATH = DATA_DIR / "question_banks" / "past_papers_reviewed.json"


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def list_review_candidates(source_dir: Path = DEFAULT_SOURCE_DIR) -> list[dict]:
    """Return MCQ candidates from every source extraction, newest source first."""
    records = list_sources(source_dir)
    sources = {item["source_id"]: item for item in records}
    curriculum = load_curriculum()
    specialty_lookup = {
        specialty.title.casefold(): specialty.id for specialty in curriculum.specialties
    }
    specialty_lookup.update({specialty.id.casefold(): specialty.id for specialty in curriculum.specialties})
    candidates = []
    extraction_dir = source_dir / "extractions"
    if not extraction_dir.exists():
        return []
    extraction_rows = (
        [(source["source_id"], load_extraction(source["source_id"], source_dir))
         for source in records]
        if is_postgres()
        else [(path.stem, json.loads(path.read_text(encoding="utf-8")))
              for path in sorted(extraction_dir.glob("*.json"),
                                 key=lambda item: item.stat().st_mtime, reverse=True)]
    )
    for extraction_id, payload in extraction_rows:
        if not payload:
            continue
        source_id = payload.get("source_id") or extraction_id
        path = extraction_dir / f"{source_id}.json"
        source = sources.get(source_id, {})
        for item in payload.get("mcq_candidates", []):
            candidates.append({
                **item,
                "source_id": item.get("source_id") or source_id,
                "source_title": item.get("source_title") or source.get("title") or payload.get("source_title"),
                "source_filename": item.get("source_filename") or source.get("original_filename") or payload.get("source_filename"),
                "specialty_label": source.get("specialty", ""),
                "specialty_id": item.get("specialty_id") or specialty_lookup.get(
                    str(source.get("specialty", "")).casefold()
                ),
                "extraction_path": str(path),
                "review_state": item.get("review_state", "pending"),
            })
    return candidates


def get_review_candidate(candidate_id: str, source_dir: Path = DEFAULT_SOURCE_DIR) -> dict | None:
    for item in list_review_candidates(source_dir):
        if item.get("candidate_id") == candidate_id:
            return item
    return None


def save_candidate_review(
    candidate_id: str,
    *,
    stem: str,
    options: list[dict],
    specialty_id: str,
    topic_id: str,
    correct_option_id: str | None,
    explanation: str,
    reviewer: str,
    answer_verified: bool,
    difficulty: str = "moderate",
    source_dir: Path = DEFAULT_SOURCE_DIR,
) -> dict:
    """Save edits and reviewer attestation; optionally leave the candidate pending."""
    candidate = get_review_candidate(candidate_id, source_dir)
    if candidate is None:
        raise KeyError(f"Unknown extracted candidate: {candidate_id}")
    if len(options) < 2 or any(not item.get("text", "").strip() for item in options):
        raise ValueError("At least two non-empty answer options are required.")
    if correct_option_id and correct_option_id not in {item["id"] for item in options}:
        raise ValueError("The selected answer must match one of the current options.")
    if not reviewer.strip():
        raise ValueError("Enter the name or identifier of the person reviewing this question.")

    if answer_verified and not correct_option_id:
        raise ValueError("Select an answer key before marking it as independently verified.")

    payload = load_extraction(candidate["source_id"], source_dir)
    if payload is None:
        raise FileNotFoundError("The source extraction is no longer available.")
    for item in payload.get("mcq_candidates", []):
        if item.get("candidate_id") == candidate_id:
            # Keep the first machine extraction immutable as an audit baseline.
            original_stem = item.setdefault("original_extracted_stem", item.get("stem_extracted", ""))
            original_options = item.setdefault("original_extracted_options", item.get("options", []))
            cleaned_stem = stem.strip()
            ai_history = item.get("ai_review_history", [])
            latest_ai = ai_history[-1] if ai_history else {}
            internet_review = latest_ai.get("internet_evidence_review", {})
            ai_proposal = internet_review.get("proposed_option_id")
            ai_comparison = None
            if latest_ai:
                ai_comparison = {
                    "ai_evidence_verdict": internet_review.get("verdict", "unavailable"),
                    "ai_existing_key_assessment": internet_review.get("existing_key_assessment", "not_assessed"),
                    "ai_proposed_option_id": ai_proposal,
                    "reviewer_selected_option_id": correct_option_id,
                    "reviewer_answer_verified": bool(answer_verified),
                    "reviewer_matches_ai_proposal": (
                        correct_option_id == ai_proposal
                        if answer_verified and ai_proposal else None
                    ),
                    "reviewed_at": datetime.now(UTC).isoformat(),
                }
            item.update({
                "stem_extracted": cleaned_stem,
                "options": options,
                "transcription_accuracy_outcome": (
                    "confirmed_as_extracted"
                    if cleaned_stem == original_stem and options == original_options
                    else "corrected"
                ),
                "specialty_id": specialty_id,
                "topic_id": topic_id,
                "correct_option_id": correct_option_id,
                "explanation": explanation.strip(),
                "reviewer": reviewer.strip(),
                "answer_verified_by_reviewer": bool(answer_verified),
                "reviewer_ai_comparison": ai_comparison,
                "answer_status": (
                    "human_verified" if answer_verified and correct_option_id
                    else "proposed_unverified" if correct_option_id
                    else "not_extracted_or_verified"
                ),
                "transcription_status": "human_reviewed",
                "transcription_reviewed_by": reviewer.strip(),
                "transcription_reviewed_at": datetime.now(UTC).isoformat(),
                "difficulty": difficulty,
                "review_state": "reviewed_pending_approval",
                "reviewed_at": datetime.now(UTC).isoformat(),
            })
            break
    save_extraction(candidate["source_id"], payload, source_dir)
    return get_review_candidate(candidate_id, source_dir) or {}


def approve_candidate(
    candidate_id: str,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    bank_path: Path = QUESTION_BANK_PATH,
) -> dict:
    """Promote one fully reviewed MCQ to the installable past-paper bank."""
    candidate = get_review_candidate(candidate_id, source_dir)
    if candidate is None:
        raise KeyError(f"Unknown extracted candidate: {candidate_id}")
    if candidate.get("review_state") == "approved":
        raise ValueError("This question has already been promoted to the question bank.")
    if not candidate.get("answer_verified_by_reviewer"):
        raise ValueError("Confirm that you have independently verified the answer key before approval.")
    if not candidate.get("reviewer"):
        raise ValueError("A reviewer name is required.")
    if not candidate.get("correct_option_id"):
        raise ValueError("Choose and verify the correct option before approval.")
    if not candidate.get("explanation", "").strip():
        raise ValueError("Add a brief explanation/rationale before approval.")
    if candidate.get("question_type") != "single_best_answer":
        raise ValueError("Only complete single-best-answer MCQs can be promoted in this workflow.")
    if len(candidate.get("options", [])) < 2:
        raise ValueError("This candidate has fewer than two extracted options and needs manual completion.")

    source_id = candidate.get("source_id") or "source"
    raw_id = candidate.get("candidate_id") or candidate_id
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "-", f"past-{source_id[:10]}-{raw_id}")
    question = {
        "id": safe_id,
        "specialty_id": candidate["specialty_id"],
        "topic_id": candidate["topic_id"],
        "stem": candidate["stem_extracted"],
        "options": candidate["options"],
        "correct_option_id": candidate["correct_option_id"],
        "explanation": candidate["explanation"],
        "source_title": candidate.get("source_title") or candidate.get("source_filename") or "Past examination paper",
        "reviewed_by": candidate["reviewer"],
        "reviewed_at": candidate.get("reviewed_at") or datetime.now(UTC).isoformat(),
        # Promotion means editorially curated, not clinically approved or exam-validated.
        "review_status": "draft",
        "difficulty": candidate.get("difficulty", "moderate"),
        "question_type": "single_best_answer",
        "bank_id": "past-papers-review-bank",
        "tags": ["past-paper", "human-reviewed-transcription"],
        "source_id": source_id,
        "source_page": candidate.get("source_page"),
    }
    try:
        validated = MCQ.model_validate(question)
    except ValidationError as exc:
        raise ValueError(f"Question does not meet the bank schema: {exc}") from exc

    if is_postgres():
        initialize(DEFAULT_DB)
        with connect(DEFAULT_DB) as db:
            inserted = db.execute(
                """INSERT INTO approved_question_bank(question_id,payload_json)
                   VALUES(?,?) ON CONFLICT(question_id) DO NOTHING RETURNING question_id""",
                (validated.id, json.dumps(validated.model_dump(), ensure_ascii=False)),
            ).fetchone()
        if not inserted:
            raise ValueError("A question with this ID already exists in the past-paper bank.")
    else:
        if bank_path.exists():
            bank = json.loads(bank_path.read_text(encoding="utf-8"))
        else:
            bank = {
                "bank_id": "past-papers-review-bank",
                "title": "Reviewed Past-Paper Questions",
                "questions": [],
            }
        if any(item.get("id") == validated.id for item in bank.get("questions", [])):
            raise ValueError("A question with this ID already exists in the past-paper bank.")
        bank.setdefault("questions", []).append(validated.model_dump())
        _atomic_json(bank_path, bank)

    payload = load_extraction(candidate["source_id"], source_dir)
    if payload is None:
        raise FileNotFoundError("The source extraction is no longer available.")
    for item in payload.get("mcq_candidates", []):
        if item.get("candidate_id") == candidate_id:
            item["review_state"] = "approved"
            item["approved_question_id"] = validated.id
            item["approved_at"] = datetime.now(UTC).isoformat()
            break
    save_extraction(candidate["source_id"], payload, source_dir)
    return validated.model_dump()
