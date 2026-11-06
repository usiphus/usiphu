"""Review and promotion workflow for short-answer and modified essay questions."""
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from usiphu.practice import DATA_DIR
from usiphu.source_inbox import (
    DEFAULT_SOURCE_DIR,
    list_extractions,
    load_extraction,
    write_extraction,
)

ASSESSMENT_BANK_PATH = DATA_DIR / "question_banks" / "reviewed_assessments.json"


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def list_non_mcq_candidates(source_dir: Path = DEFAULT_SOURCE_DIR) -> list[dict]:
    """Return extracted short-answer candidates and page-level MEQ candidates."""
    results = []
    for source, payload in list_extractions(source_dir):
        for collection, kind in (
            ("mcq_candidates", "short_answer"),
            ("meq_page_candidates", "meq"),
        ):
            for item in payload.get(collection, []):
                extracted_type = item.get("question_type")
                if kind == "short_answer" and extracted_type != "short_answer_candidate":
                    continue
                if kind == "meq" and extracted_type != "modified_essay_question":
                    continue
                results.append({
                    **item,
                    "assessment_type": kind,
                    "source_id": item.get("source_id") or payload.get("source_id"),
                    "source_title": item.get("source_title") or payload.get("source_title"),
                    "source_filename": item.get("source_filename") or source.get("original_filename") or payload.get("source_filename"),
                    "specialty_label": source.get("specialty", payload.get("specialty", "")),
                    "extraction_path": source.get("extraction_file") or f"extractions/{source.get('source_id', '')}.json",
                    "review_state": item.get("review_state", "pending"),
                })
    return results


def get_non_mcq_candidate(candidate_id: str, source_dir: Path = DEFAULT_SOURCE_DIR) -> dict | None:
    return next((item for item in list_non_mcq_candidates(source_dir)
                 if item.get("candidate_id") == candidate_id), None)


def _validate_marking_points(points: list[dict], context: str) -> list[dict]:
    if not points:
        raise ValueError(f"Add at least one marking point for {context}.")
    cleaned = []
    for index, point in enumerate(points, start=1):
        statement = str(point.get("point", "")).strip()
        terms = [str(term).strip() for term in point.get("acceptable_terms", []) if str(term).strip()]
        marks = int(point.get("marks", 1))
        if not statement or not terms or marks < 1:
            raise ValueError(
                f"Marking point {index} for {context} needs a description, accepted terms and positive marks."
            )
        cleaned.append({"point": statement, "acceptable_terms": terms, "marks": marks})
    return cleaned


def save_non_mcq_review(
    candidate_id: str,
    *,
    assessment_type: str,
    prompt: str,
    scenario: str,
    parts: list[dict],
    specialty_id: str,
    topic_id: str,
    reviewer: str,
    rubric_verified: bool,
    corrected_source_text: str | None = None,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    bank_path: Path = ASSESSMENT_BANK_PATH,
    approve: bool = False,
) -> dict:
    """Save a short-answer/MEQ review; approval adds a draft assessment to its own bank."""
    candidate = get_non_mcq_candidate(candidate_id, source_dir)
    if candidate is None:
        raise KeyError(f"Unknown short-answer/MEQ candidate: {candidate_id}")
    if candidate.get("assessment_type") != assessment_type:
        raise ValueError("The selected editor does not match this candidate's extracted type.")
    if not prompt.strip():
        raise ValueError("Enter a question prompt or case title.")
    if not reviewer.strip():
        raise ValueError("Enter the reviewer name or identifier.")
    if not parts:
        raise ValueError("Add at least one answer part.")
    normalized_parts = []
    for index, part in enumerate(parts, start=1):
        part_prompt = str(part.get("prompt", "")).strip()
        if not part_prompt:
            raise ValueError(f"Part {index} needs a prompt.")
        points = _validate_marking_points(part.get("marking_points", []), f"part {index}")
        normalized_parts.append({
            "id": str(part.get("id") or f"part-{index}"),
            "prompt": part_prompt,
            "max_marks": sum(item["marks"] for item in points),
            "marking_points": points,
        })
    if not rubric_verified:
        if approve:
            raise ValueError("Confirm that the marking rubric has been independently checked before approval.")

    payload = load_extraction(candidate["source_id"], source_dir)
    if payload is None:
        raise FileNotFoundError("The stored extraction is missing.")
    collection = "meq_page_candidates" if assessment_type == "meq" else "mcq_candidates"
    updated = False
    for item in payload.get(collection, []):
        if item.get("candidate_id") == candidate_id:
            original_text = item.setdefault("original_extracted_text", item.get("raw_text", ""))
            reviewed_text = (
                str(corrected_source_text).strip()
                if corrected_source_text is not None
                else item.get("reviewed_source_text", item.get("raw_text", ""))
            )
            item.update({
                "review_prompt": prompt.strip(),
                "review_scenario": scenario.strip(),
                "reviewed_source_text": reviewed_text,
                "transcription_accuracy_outcome": (
                    "confirmed_as_extracted" if reviewed_text == original_text else "corrected"
                ),
                "transcription_status": "human_reviewed",
                "transcription_reviewed_by": reviewer.strip(),
                "transcription_reviewed_at": datetime.now(UTC).isoformat(),
                "review_parts": normalized_parts,
                "specialty_id": specialty_id,
                "topic_id": topic_id,
                "reviewer": reviewer.strip(),
                "rubric_verified_by_reviewer": bool(rubric_verified),
                "review_state": "reviewed_pending_approval",
                "reviewed_at": datetime.now(UTC).isoformat(),
            })
            updated = True
            break
    if not updated:
        raise KeyError(f"Could not update candidate: {candidate_id}")
    write_extraction(candidate["source_id"], payload, source_dir)

    assessment = {
        "id": re.sub(r"[^a-zA-Z0-9_-]", "-", f"assess-{candidate_id}"),
        "candidate_id": candidate_id,
        "assessment_type": assessment_type,
        "specialty_id": specialty_id,
        "topic_id": topic_id,
        "prompt": prompt.strip(),
        "scenario": scenario.strip(),
        "parts": normalized_parts,
        "reviewer": reviewer.strip(),
        "rubric_verified_by_reviewer": bool(rubric_verified),
        "reviewed_at": datetime.now(UTC).isoformat(),
        "review_status": "draft",
        "source_id": candidate.get("source_id"),
        "source_title": candidate.get("source_title") or candidate.get("source_filename"),
        "source_page": candidate.get("source_page"),
        "source_page_end": candidate.get("source_page_end", candidate.get("source_page")),
    }
    if approve:
        if not rubric_verified:
            raise ValueError("A verified rubric is required before approval.")
        bank = json.loads(bank_path.read_text(encoding="utf-8")) if bank_path.exists() else {
            "bank_id": "reviewed-short-answer-meq",
            "title": "Reviewed Short Answer and MEQ Assessments",
            "assessments": [],
        }
        if any(item.get("candidate_id") == candidate_id for item in bank.get("assessments", [])):
            raise ValueError("This assessment has already been promoted.")
        bank.setdefault("assessments", []).append(assessment)
        _atomic_json(bank_path, bank)
        for item in payload.get(collection, []):
            if item.get("candidate_id") == candidate_id:
                item["review_state"] = "approved"
                item["approved_assessment_id"] = assessment["id"]
                item["approved_at"] = datetime.now(UTC).isoformat()
                break
        write_extraction(candidate["source_id"], payload, source_dir)
    return assessment


def load_assessments(path: Path = ASSESSMENT_BANK_PATH) -> list[dict]:
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("assessments", [])
