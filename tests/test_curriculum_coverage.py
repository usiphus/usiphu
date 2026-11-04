"""Regression tests for complete, provenance-aware medical curriculum coverage."""
import json
from pathlib import Path

import pytest

from usiphu.coverage import coverage_report, validate_coverage_register

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "data" / "curriculum_coverage.json"


def test_coverage_register_accounts_for_every_medical_topic_and_objective():
    result = validate_coverage_register()
    assert result["coverage_register_valid"] == 1
    assert result["coverage_topics"] == 174
    assert result["coverage_objectives"] == 291
    assert result["topics_without_verified_outcome_mapping"] == 112
    assert result["objectives_without_verified_outcome_mapping"] == 224
    assert result["objective_level_mapping_verified"] == 0


def test_official_outcome_coverage_is_measured_without_claiming_full_syllabus():
    report = coverage_report()
    assert report["course_outcomes_catalogued"] == 73
    assert report["official_outcomes_linked_at_topic_level"] == 47
    assert report["official_outcomes_not_linked_in_current_crosswalk"] == 26
    assert report["official_outcome_mapping_percent"] == 64.4
    assert report["objectives_with_topic_level_link_only"] == 55
    assert report["objectives_partially_linked_at_topic_level"] == 6


def test_external_pediatrics_benchmarks_are_not_counted_as_suez_outcomes():
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    pediatric = [row for row in register["topics"] if row["specialty_id"] == "paediatrics"]
    assert len(pediatric) == 4
    assert all(row["course_outcome_mapping_status"] == "external_benchmark_only"
               for row in pediatric)
    assert all(not row["official_course_outcome_refs"] for row in pediatric)
    assert all(row["external_benchmark_refs"] for row in pediatric)


def test_coverage_validator_detects_missing_objective_rows(tmp_path: Path):
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    register["topics"][0]["objectives"].pop()
    bad_file = tmp_path / "coverage.json"
    bad_file.write_text(json.dumps(register), encoding="utf-8")
    with pytest.raises(ValueError, match="Objective coverage mismatch"):
        validate_coverage_register(register_path=bad_file)
