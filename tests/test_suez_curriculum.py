"""Institution-specific Suez University bylaw mapping integrity tests."""
import json
from pathlib import Path

PROFILE = Path(__file__).resolve().parents[1] / "data" / "suez_university_curriculum.json"


def load_profile():
    return json.loads(PROFILE.read_text(encoding="utf-8"))


def test_profile_targets_suez_university_not_suez_canal():
    profile = load_profile()
    assert profile["institution"]["name_en"] == "Suez University"
    assert profile["institution"]["name_ar"] == "جامعة السويس"
    assert "Suez Canal University" in profile["institution"]["explicit_exclusion"]


def test_programme_structure_matches_uploaded_bylaw():
    profile = load_profile()
    programme = profile["programme"]
    assert programme["academic_programme_years"] == 5
    assert programme["phases"][0]["years"] == [1, 2]
    assert programme["phases"][1]["years"] == [3, 4, 5]
    assert "Not specified" in programme["internship"]
    assert len(profile["official_curriculum"]["modules"]) == 24
    assert profile["mapping_rules"]["status"] == "course_outcome_catalog_ingested_partial_topic_mapping"


def test_every_starter_topic_has_explicit_mapping_status_and_preserved_objectives():
    profile = load_profile()
    refs = [(row["specialty_id"], row["domain_id"], row["topic_id"])
            for row in profile["topics"]]
    assert len(refs) == 62
    assert len(refs) == len(set(refs))
    assert len({row["specialty_id"] for row in profile["topics"]}) == 13
    assert all(row["objective_ids"] for row in profile["topics"])
    assert all(row["provisional_competency_strands"] for row in profile["topics"])
    assert all(row["mapping_status"] in {
        "bylaw_module_alignment",
        "related_department_alignment",
        "not_separately_timetabled_in_module_table",
    } for row in profile["topics"])
    assert all(row["competency_mapping_status"] == "provisional_framework_alignment"
               for row in profile["topics"])
    assert all("course_outcome_mapping_status" in row for row in profile["topics"])
    assert all("course_outcome_refs" in row for row in profile["topics"])
    assert all(
        row["official_outcome_reference"] is None
        or row["official_outcome_reference"] in row["course_outcome_refs"]
        for row in profile["topics"]
    )


def test_urology_is_mapped_to_the_bylaw_surgery_module():
    profile = load_profile()
    topics = [row for row in profile["topics"] if row["specialty_id"] == "urology"]
    assert len(topics) == 9
    assert all("SI 2.4.2" in row["bylaw_module_codes"] for row in topics)
    assert all("US 1.2.9" in row["bylaw_module_codes"] for row in topics)


def test_anaesthesia_topics_are_not_given_an_invented_standalone_module():
    profile = load_profile()
    topics = [row for row in profile["topics"]
              if row["specialty_id"] == "anaesthesia-critical-care"]
    assert topics
    assert all(not row["bylaw_module_codes"] for row in topics)
    assert all(row["mapping_status"] == "not_separately_timetabled_in_module_table"
               for row in topics)
