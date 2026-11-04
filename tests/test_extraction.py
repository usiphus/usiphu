"""Tests for source-paper text extraction and draft candidate handling."""
import json

from usiphu.extraction import extract_source, parse_question_text
from usiphu.source_inbox import list_sources, save_source


def test_parse_question_text_keeps_options_and_does_not_invent_answers():
    source = {
        "source_id": "source-test",
        "title": "Test paper",
        "original_filename": "paper.txt",
        "sha256": "abc123",
        "specialty": "Urology",
    }
    payload = parse_question_text(
        [
            "Urology\n"
            "1) Which investigation is most appropriate?\n"
            "A. Ultrasound\n"
            "B. CT\n"
            "C. MRI\n\n"
            "2) State two causes of urinary retention?\n"
        ],
        source,
    )

    assert payload["summary"]["question_candidates"] == 2
    mcq = payload["mcq_candidates"][0]
    assert mcq["question_type"] == "single_best_answer"
    assert [option["id"] for option in mcq["options"]] == ["a", "b", "c"]
    assert mcq["correct_option_id"] is None
    assert mcq["answer_status"] == "not_extracted_or_verified"
    assert payload["mcq_candidates"][1]["question_type"] == "short_answer_candidate"


def test_extract_source_writes_candidates_and_updates_inbox_status(tmp_path):
    saved = save_source(
        "urology-paper.txt",
        (
            "1) Which of the following is correct?\n"
            "A. Option one\nB. Option two\nC. Option three\n"
        ).encode(),
        specialty="Urology",
        source_dir=tmp_path,
    )

    payload = extract_source(saved["source_id"], source_dir=tmp_path)

    assert payload["summary"]["mcq_candidates"] == 1
    updated = list_sources(tmp_path)[0]
    assert updated["status"] == "extracted_pending_review"
    assert updated["question_count"] == 1
    extraction_path = tmp_path / updated["extraction_file"]
    assert extraction_path.is_file()
    stored = json.loads(extraction_path.read_text(encoding="utf-8"))
    assert stored["mcq_candidates"][0]["correct_option_id"] is None
