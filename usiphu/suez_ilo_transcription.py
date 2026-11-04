"""Validate granular, page-cited transcriptions of official Suez course ILOs."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTION_DIR = ROOT / "data" / "suez_ilo_transcriptions"
CATALOG_FILE = ROOT / "data" / "suez_course_ilos.json"


def load_transcriptions() -> list[dict]:
    """Load all granular transcription records."""
    if not TRANSCRIPTION_DIR.exists():
        return []
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(TRANSCRIPTION_DIR.glob("*.json"))
    ]


def validate_transcriptions() -> dict[str, int]:
    """Check source identity, page bounds, uniqueness and transcription completeness."""
    catalog = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    source_by_id = {source["id"]: source for source in catalog["sources"]}
    module_codes = {module["module_code"] for module in catalog["modules"]}
    seen_ids: set[str] = set()
    outcome_count = 0
    source_count = 0
    kinds: Counter[str] = Counter()

    for document in load_transcriptions():
        source_count += 1
        source_id = document.get("source_id")
        if source_id not in source_by_id:
            raise ValueError(f"Unknown official source_id in transcription: {source_id}")
        source = source_by_id[source_id]
        if source.get("source_type") not in {
            "user_supplied_course_specification",
            "user_supplied_course_guide",
            "user_supplied_ilo_proposal",
        }:
            raise ValueError(f"Non-official source used for official ILO transcription: {source_id}")
        if document.get("institution") != "Suez University, Faculty of Medicine":
            raise ValueError(f"Incorrect institution identity in {source_id}")
        if document.get("source_file") != source.get("file"):
            raise ValueError(f"Source filename mismatch in {source_id}")
        if document.get("module_code") not in module_codes:
            raise ValueError(f"Unknown module code in {source_id}")
        if source.get("module_code") != document.get("module_code"):
            raise ValueError(f"Source/module code mismatch in {source_id}")
        if not document.get("academic_year") or not document.get("extraction_status"):
            raise ValueError(f"Missing extraction provenance in {source_id}")
        page_count = document.get("source_page_count")
        if not isinstance(page_count, int) or page_count < 1:
            raise ValueError(f"Invalid source page count in {source_id}")
        outcomes = document.get("outcomes")
        if not isinstance(outcomes, list) or not outcomes:
            raise ValueError(f"No transcribed outcomes in {source_id}")
        for outcome in outcomes:
            outcome_id = outcome.get("id")
            if not outcome_id or outcome_id in seen_ids:
                raise ValueError(f"Missing or duplicate transcription outcome ID: {outcome_id}")
            seen_ids.add(outcome_id)
            page = outcome.get("source_page")
            if not isinstance(page, int) or not 1 <= page <= page_count:
                raise ValueError(f"Invalid source page for {outcome_id}")
            if not isinstance(outcome.get("transcribed_text"), str) or not outcome["transcribed_text"].strip():
                raise ValueError(f"Empty source text for {outcome_id}")
            if not outcome.get("kind") or not outcome.get("domain"):
                raise ValueError(f"Missing classification for {outcome_id}")
            kinds[outcome["kind"]] += 1
            outcome_count += 1

    return {
        "granular_ilo_transcription_sources": source_count,
        "granular_ilo_transcribed_outcomes": outcome_count,
        "granular_ilo_unique_ids": len(seen_ids),
        "granular_ilo_transcribed_pages": len({
            (document["source_id"], outcome["source_page"])
            for document in load_transcriptions()
            for outcome in document["outcomes"]
        }),
    }
