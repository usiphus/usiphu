"""Institution-specific Suez University curriculum profile integrity tests."""
import json
from pathlib import Path

PROFILE = Path(__file__).resolve().parents[1] / "data" / "suez_university_curriculum.json"


def test_profile_targets_suez_university_not_suez_canal():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert profile["institution"]["name_en"] == "Suez University"
    assert profile["institution"]["name_ar"] == "جامعة السويس"
    assert "Suez Canal University" in profile["institution"]["explicit_exclusion"]


def test_suez_profile_is_honest_about_unverified_official_course_mapping():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    programme = profile["programme"]
    assert programme["structure_years"] == {"academic_programme": 5, "mandatory_internship": 2}
    assert programme["academic_year_sequence"] is None
    assert programme["semester_map"] is None
    assert profile["mapping_rules"]["status"] == "provisional_framework_alignment"
    assert all(topic["official_course_code"] is None for topic in profile["topics"])
    assert all(topic["official_outcome_reference"] is None for topic in profile["topics"])


def test_every_starter_topic_has_a_provisional_crosswalk_entry():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    refs = [(row["specialty_id"], row["domain_id"], row["topic_id"])
            for row in profile["topics"]]
    assert len(refs) == 62
    assert len(refs) == len(set(refs))
    assert len({row["specialty_id"] for row in profile["topics"]}) == 13
    assert all(row["objective_ids"] for row in profile["topics"])
    assert all(row["provisional_competency_strands"] for row in profile["topics"])
    assert all(row["mapping_status"] == "provisional_framework_alignment"
               for row in profile["topics"])
