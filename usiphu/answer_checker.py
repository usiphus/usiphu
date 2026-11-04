"""Conservative automatic marking for verified MCQ keys and human-authored rubrics."""
import re
import unicodedata


def normalize_answer(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold()
    value = re.sub(r"[^\w\s+-]", " ", value)
    return " ".join(value.split())


def check_mcq_answer(
    *,
    selected_option_id: str,
    correct_option_id: str | None,
    review_status: str = "draft",
) -> dict:
    """Compare an option ID to a stored key and disclose the key's editorial status."""
    if not correct_option_id:
        return {
            "markable": False,
            "status": "no_verified_key",
            "message": "No answer key is available; this question cannot be automatically marked.",
        }
    correct = normalize_answer(correct_option_id) == normalize_answer(selected_option_id)
    trusted = review_status in {"clinically_reviewed", "exam_validated"}
    return {
        "markable": True,
        "correct": correct,
        "status": "marked" if trusted else "provisional_key",
        "trusted_key": trusted,
        "message": (
            "Correct." if correct else "Incorrect."
        ) if trusted else (
            "Your choice matches the stored draft key." if correct
            else "Your choice does not match the stored draft key."
        ),
        "caveat": None if trusted else (
            "This key is still an editorial draft. The checker can compare it, "
            "but cannot certify that the stored answer is clinically correct."
        ),
    }


def check_rubric_answer(answer: str, marking_points: list[dict]) -> dict:
    """Award rubric points when reviewer-defined acceptable phrases are present.

    This is deliberately lexical, not semantic: unrecognized correct wording is
    referred for manual review rather than automatically declared wrong.
    """
    if not marking_points:
        return {
            "markable": False,
            "status": "missing_rubric",
            "message": "No marking rubric is available for this answer.",
        }
    normalized = normalize_answer(answer)
    results = []
    awarded = 0
    possible = 0
    for item in marking_points:
        marks = max(1, int(item.get("marks", 1)))
        possible += marks
        terms = [term for term in item.get("acceptable_terms", []) if normalize_answer(term)]
        matches = [term for term in terms if normalize_answer(term) in normalized]
        earned = marks if matches else 0
        awarded += earned
        results.append({
            "point": item.get("point", ""),
            "marks_awarded": earned,
            "marks_available": marks,
            "matched_terms": matches,
            "manual_check_recommended": not bool(matches),
        })
    return {
        "markable": True,
        "status": "rubric_screened",
        "marks_awarded": awarded,
        "marks_available": possible,
        "percentage": round(100 * awarded / possible, 1) if possible else 0,
        "points": results,
        "manual_review_required": True,
        "message": (
            "This is a keyword-based rubric screen, not semantic clinical assessment. "
            "Review unmatched points manually; medically equivalent wording may not match."
        ),
    }


def check_assessment_answers(assessment: dict, answers: dict[str, str]) -> dict:
    parts = []
    total_awarded = 0
    total_available = 0
    for part in assessment.get("parts", []):
        result = check_rubric_answer(
            answers.get(part["id"], ""),
            part.get("marking_points", []),
        )
        if result.get("markable"):
            total_awarded += result["marks_awarded"]
            total_available += result["marks_available"]
        parts.append({"part_id": part["id"], "prompt": part["prompt"], **result})
    return {
        "assessment_id": assessment.get("id"),
        "assessment_type": assessment.get("assessment_type"),
        "parts": parts,
        "marks_awarded": total_awarded,
        "marks_available": total_available,
        "percentage": round(100 * total_awarded / total_available, 1) if total_available else 0,
        "manual_review_required": True,
    }
