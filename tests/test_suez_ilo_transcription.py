"""Tests for page-cited official Suez ILO transcriptions."""
import json
from pathlib import Path

import pytest

from usiphu.suez_ilo_transcription import load_transcriptions, validate_transcriptions


def test_medicine_one_transcription_is_page_cited_and_official():
    report = validate_transcriptions()
    assert report["granular_ilo_transcription_sources"] == 1
    assert report["granular_ilo_transcribed_outcomes"] >= 100
    document = load_transcriptions()[0]
    assert document["module_code"] == "MI 2.4.1"
    assert document["source_id"] == "suez-mi-2021-22"
    assert document["extraction_status"] == "transcribed_not_faculty_verified"
    assert all(6 <= item["source_page"] <= 26 for item in document["outcomes"])


def test_transcription_validator_rejects_external_source_as_official(tmp_path, monkeypatch):
    from usiphu import suez_ilo_transcription as transcription

    source = json.loads(transcription.CATALOG_FILE.read_text(encoding="utf-8"))
    source["sources"][0]["source_type"] = "external_public_benchmark_not_suez_official"
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
