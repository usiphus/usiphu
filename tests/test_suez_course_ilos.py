"""Integrity tests for ingested Suez University course ILOs and external benchmark."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data" / "suez_university_curriculum.json"
CATALOG = ROOT / "data" / "suez_course_ilos.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_catalog_targets_suez_university_and_excludes_suez_canal():
    catalog = load(CATALOG)
    assert catalog["institution"]["name_en"] == "Suez University"
    assert catalog["institution"]["name_ar"] == "جامعة السويس"
    assert "Suez Canal University" in catalog["institution"]["exclusion"]


def test_all_course_outcome_ids_are_unique_and_sources_exist():
    catalog = load(CATALOG)
    source_ids = {source["id"] for source in catalog["sources"]}
    outcome_ids = []
    for module in catalog["modules"]:
        assert module["source_id"] in source_ids
        outcome_ids.extend(outcome["id"] for outcome in module["outcomes"])
    assert len(outcome_ids) == len(set(outcome_ids))


def test_crosswalk_covers_every_starter_topic_and_uses_valid_references():
    profile = load(PROFILE)
    catalog = load(CATALOG)
    profile_topic_ids = {topic["topic_id"] for topic in profile["topics"]}
    crosswalk = catalog["topic_crosswalk"]
    assert {row["topic_id"] for row in crosswalk} == profile_topic_ids
    official_ids = {
        outcome["id"]
        for module in catalog["modules"]
        for outcome in module["outcomes"]
    }
    external_ids = {
        outcome["id"]
        for benchmark in catalog["external_benchmarks"]
        for outcome in benchmark["outcome_groups"]
    }
    for row in crosswalk:
        valid = external_ids if row["status"] == "external_benchmark_only" else official_ids
        assert set(row["outcome_refs"]) <= valid


def test_pediatrics_benchmark_is_explicitly_external_not_official():
    catalog = load(CATALOG)
    benchmark = catalog["external_benchmarks"][0]
    assert benchmark["source_id"] == "azhar-damietta-pediatrics-benchmark"
    source = next(s for s in catalog["sources"] if s["id"] == benchmark["source_id"])
    assert source["institution"] == "Al-Azhar University, Damietta Faculty of Medicine"
    assert source["source_type"] == "external_public_benchmark_not_suez_official"
    assert all(row["status"] == "external_benchmark_only"
               for row in catalog["topic_crosswalk"]
               if row["topic_id"] in {"neonatal-resuscitation", "neonatal-jaundice", "dehydration", "febrile-child"})


def test_phc_obs_is_not_mislabelled_as_pediatrics_and_schedules_are_not_ilos():
    catalog = load(CATALOG)
    phc_obs = next(m for m in catalog["modules"] if m["module_code"] == "PHC/Obs 2.3.2")
    assert "Obstetrics and Gynaecology" in phc_obs["domains"]
    assert "Pediatrics" not in phc_obs["domains"]
    schedules = [s for s in catalog["sources"] if s["source_type"] == "user_supplied_teaching_schedule"]
    assert len(schedules) == 2
    assert all("not a separate formal ILO" in s["notes"] for s in schedules)


def test_profile_marks_pediatric_official_outcome_reference_as_unavailable():
    profile = load(PROFILE)
    pediatric = [topic for topic in profile["topics"] if topic["specialty_id"] == "paediatrics"]
    assert len(pediatric) == 4
    assert all(topic["official_outcome_reference"] is None for topic in pediatric)
    assert all(topic["external_benchmark_refs"] for topic in pediatric)
    assert all(topic["course_outcome_mapping_status"] == "external_benchmark_only" for topic in pediatric)
