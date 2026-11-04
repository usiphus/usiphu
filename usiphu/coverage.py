"""Auditable topic/objective and official course-outcome coverage reporting."""
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CURRICULUM_FILE = ROOT / "data" / "curriculum.json"
COVERAGE_FILE = ROOT / "data" / "curriculum_coverage.json"
COURSE_ILO_FILE = ROOT / "data" / "suez_course_ilos.json"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def load_coverage_register(path: Path = COVERAGE_FILE) -> dict[str, Any]:
    return _read_json(path)


def coverage_report(
    register_path: Path = COVERAGE_FILE,
) -> dict[str, int | float]:
    """Return verified coverage counts; topic links are not objective-level sign-off."""
    register = load_coverage_register(register_path)
    counts = register["counts"]
    return {
        "course_outcomes_catalogued": counts["official_course_outcomes"],
        "official_outcomes_linked_at_topic_level": counts[
            "official_outcomes_linked_at_topic_level"
        ],
        "official_outcomes_not_linked_in_current_crosswalk": counts[
            "official_outcomes_not_linked_in_current_crosswalk"
        ],
        "official_outcome_mapping_percent": counts["official_outcome_mapping_percent"],
        "topics_directly_mapped": counts["topic_mapping_statuses"].get(
            "direct_course_outcome", 0
        ),
        "topics_partially_mapped": counts["topic_mapping_statuses"].get(
            "partial_related_outcome", 0
        ),
        "topics_external_benchmark_only": counts["topic_mapping_statuses"].get(
            "external_benchmark_only", 0
        ),
        "topics_module_only_no_specific_ilo": counts["topic_mapping_statuses"].get(
            "module_only_no_specific_ilo", 0
        ),
        "topics_without_verified_outcome_mapping": counts["topic_mapping_statuses"].get(
            "not_mapped_no_verified_course_outcome", 0
        ),
        "objectives_with_topic_level_link_only": counts["objective_mapping_statuses"].get(
            "topic_level_link_only_not_objective_specific", 0
        ),
        "objectives_partially_linked_at_topic_level": counts["objective_mapping_statuses"].get(
            "partial_topic_level_link_not_objective_specific", 0
        ),
        "objectives_external_benchmark_only": counts["objective_mapping_statuses"].get(
            "external_benchmark_only_not_official_suez", 0
        ),
        "objectives_module_only_no_specific_ilo": counts["objective_mapping_statuses"].get(
            "module_alignment_only_no_specific_ilo", 0
        ),
        "objectives_without_verified_outcome_mapping": counts["objective_mapping_statuses"].get(
            "not_mapped_no_verified_course_outcome", 0
        ),
        "objective_level_mapping_verified": 0,
    }


def validate_coverage_register(
    curriculum_path: Path = CURRICULUM_FILE,
    register_path: Path = COVERAGE_FILE,
    course_ilo_path: Path = COURSE_ILO_FILE,
) -> dict[str, int | float]:
    """Fail on missing curriculum rows, stale objective IDs, or invalid outcome references."""
    curriculum = _read_json(curriculum_path)
    register = load_coverage_register(register_path)
    catalog = _read_json(course_ilo_path)

    current_topics = {}
    for specialty in curriculum["specialties"]:
        for domain in specialty["domains"]:
            for topic in domain["topics"]:
                key = (specialty["id"], topic["id"])
                if key in current_topics:
                    raise ValueError(f"Duplicate curriculum topic key: {key}")
                current_topics[key] = {item["id"] for item in topic["objectives"]}

    rows = register["topics"]
    row_keys = [(row["specialty_id"], row["topic_id"]) for row in rows]
    if len(row_keys) != len(set(row_keys)):
        raise ValueError("Duplicate topic keys in coverage register")
    if set(row_keys) != set(current_topics):
        missing = sorted(set(current_topics) - set(row_keys))
        extra = sorted(set(row_keys) - set(current_topics))
        raise ValueError(f"Coverage register topic mismatch; missing={missing}, extra={extra}")

    for row in rows:
        key = (row["specialty_id"], row["topic_id"])
        objective_ids = [item["objective_id"] for item in row["objectives"]]
        if len(objective_ids) != len(set(objective_ids)):
            raise ValueError(f"Duplicate objective IDs for topic {key}")
        if set(objective_ids) != current_topics[key]:
            raise ValueError(f"Objective coverage mismatch for topic {key}")
        status = row["course_outcome_mapping_status"]
        if row["external_benchmark_refs"] and row["official_course_outcome_refs"]:
            raise ValueError(f"External-only topic has official outcome refs: {key}")
        if status in {"direct_course_outcome", "partial_related_outcome"} and not row["official_course_outcome_refs"]:
            raise ValueError(f"Mapped topic lacks official outcome refs: {key}")
        if status == "external_benchmark_only" and not row["external_benchmark_refs"]:
            raise ValueError(f"External-only topic lacks benchmark refs: {key}")
        if status in {"module_only_no_specific_ilo", "not_mapped_no_verified_course_outcome"} and (
            row["official_course_outcome_refs"] or row["external_benchmark_refs"]
        ):
            raise ValueError(f"Unmapped/module-only topic contains outcome refs: {key}")
        expected_objective_status = {
            "direct_course_outcome": "topic_level_link_only_not_objective_specific",
            "partial_related_outcome": "partial_topic_level_link_not_objective_specific",
            "external_benchmark_only": "external_benchmark_only_not_official_suez",
            "module_only_no_specific_ilo": "module_alignment_only_no_specific_ilo",
            "not_mapped_no_verified_course_outcome": "not_mapped_no_verified_course_outcome",
        }.get(status)
        if any(item["mapping_status"] != expected_objective_status for item in row["objectives"]):
            raise ValueError(f"Objective mapping status mismatch for topic {key}")
        if row["course_outcome_mapping_status"] == "not_mapped_no_verified_course_outcome":
            if row["official_course_outcome_refs"] or row["external_benchmark_refs"]:
                raise ValueError(f"Unmapped topic contains unsupported refs: {key}")

    official = {
        outcome["id"]
        for module in catalog["modules"]
        for outcome in module["outcomes"]
    }
    external = {
        outcome["id"]
        for benchmark in catalog["external_benchmarks"]
        for outcome in benchmark["outcome_groups"]
    }
    for row in rows:
        if not set(row["official_course_outcome_refs"]) <= official:
            raise ValueError(f"Unknown official outcome reference in {row['topic_id']}")
        if not set(row["external_benchmark_refs"]) <= external:
            raise ValueError(f"Unknown external benchmark reference in {row['topic_id']}")

    outcome_rows = register["official_course_outcomes"]
    outcome_ids = [row["outcome_id"] for row in outcome_rows]
    if len(outcome_ids) != len(set(outcome_ids)) or set(outcome_ids) != official:
        raise ValueError("Official outcome register does not match the source ILO catalogue")
    for outcome in outcome_rows:
        expected_topics = sorted(
            row["topic_id"] for row in rows
            if outcome["outcome_id"] in row["official_course_outcome_refs"]
        )
        if sorted(outcome["linked_topic_ids"]) != expected_topics:
            raise ValueError(
                f"Stale topic links for official outcome {outcome['outcome_id']}"
            )

    report = coverage_report(register_path)
    topic_status_counts: dict[str, int] = {}
    objective_status_counts: dict[str, int] = {}
    for row in rows:
        status = row["course_outcome_mapping_status"]
        topic_status_counts[status] = topic_status_counts.get(status, 0) + 1
        for objective in row["objectives"]:
            obj_status = objective["mapping_status"]
            objective_status_counts[obj_status] = objective_status_counts.get(obj_status, 0) + 1
    if topic_status_counts != register["counts"]["topic_mapping_statuses"]:
        raise ValueError("Stored topic mapping counts do not match the coverage rows")
    if objective_status_counts != register["counts"]["objective_mapping_statuses"]:
        raise ValueError("Stored objective mapping counts do not match the coverage rows")
    linked_outcomes = sum(bool(row["linked_topic_ids"]) for row in outcome_rows)
    if (register["counts"]["official_outcomes_linked_at_topic_level"] != linked_outcomes
            or register["counts"]["official_outcomes_not_linked_in_current_crosswalk"]
            != len(outcome_rows) - linked_outcomes):
        raise ValueError("Stored official outcome mapping counts do not match the outcome rows")
    if sum(report[key] for key in (
        "topics_directly_mapped", "topics_partially_mapped",
        "topics_external_benchmark_only", "topics_module_only_no_specific_ilo",
        "topics_without_verified_outcome_mapping",
    )) != len(rows):
        raise ValueError("Topic mapping status counts do not reconcile")
    if sum(report[key] for key in (
        "objectives_with_topic_level_link_only", "objectives_partially_linked_at_topic_level",
        "objectives_external_benchmark_only", "objectives_module_only_no_specific_ilo",
        "objectives_without_verified_outcome_mapping",
    )) != sum(
        len(row["objectives"]) for row in rows
    ):
        raise ValueError("Objective mapping status counts do not reconcile")
    return {
        "coverage_register_valid": 1,
        "coverage_topics": len(rows),
        "coverage_objectives": sum(len(row["objectives"]) for row in rows),
        **report,
    }
