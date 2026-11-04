"""Tests for page-cited official Suez ILO transcriptions."""
import json

import pytest

from usiphu.suez_ilo_transcription import load_transcriptions, validate_transcriptions


def test_three_suez_modules_have_page_cited_granular_ilos():
    report = validate_transcriptions()
    assert report["granular_ilo_transcription_sources"] == 3
    assert report["granular_ilo_transcribed_outcomes"] == 227
    documents = {item["module_code"]: item for item in load_transcriptions()}
    expected = {
        "MI 2.4.1": ("suez-mi-2021-22", 111, 7, 26),
        "SII 2.5.2": ("suez-sii-course", 64, 4, 11),
        "E&MR 2.5.3": ("suez-emergency-guide", 52, 4, 9),
    }
    for module_code, (source_id, count, first_page, last_page) in expected.items():
        document = documents[module_code]
        assert document["source_id"] == source_id
        assert len(document["outcomes"]) == count
        assert document["extraction_status"] == "transcribed_not_faculty_verified"
        assert all(first_page <= item["source_page"] <= last_page
                   for item in document["outcomes"])


def test_transcription_validator_rejects_external_source_as_official(tmp_path, monkeypatch):
    from usiphu import suez_ilo_transcription as transcription

    source = json.loads(transcription.CATALOG_FILE.read_text(encoding="utf-8"))
    source["sources"][3]["source_type"] = "external_public_benchmark_not_suez_official"
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps(source), encoding="utf-8")
    monkeypatch.setattr(transcription, "CATALOG_FILE", catalog)
    with pytest.raises(ValueError, match="Non-official source"):
        transcription.validate_transcriptions()


def test_transcription_pages_are_within_source_bounds():
    for document in load_transcriptions():
        assert all(
            1 <= outcome["source_page"] <= document["source_page_count"]
            for outcome in document["outcomes"]
        )
