#!/usr/bin/env python3
"""Exercise Source Inbox extraction and SQLite persistence in a disposable staging container."""
import argparse
import os
from pathlib import Path

from usiphu.extraction import extract_source, load_extraction
from usiphu.source_inbox import list_sources, save_source
from usiphu.storage import initialize, question_attempt_history, record_question_attempt

SOURCE_DIR = Path(os.environ.get("USIPHU_SOURCE_DIR", "data/source_inbox"))
DB_PATH = Path(os.environ.get("USIPHU_DB_PATH", "usiphu_data.sqlite3"))
TITLE = "USIPHU staging persistence smoke test"
LEARNER = "staging-smoke-learner"
QUESTION = "staging-smoke-question"
SAMPLE = (
    "1. Which option is used only to verify extraction in this synthetic test?\n"
    "A. Synthetic option A\n"
    "B. Synthetic option B\n"
)


def seed() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if any(item.get("title") == TITLE for item in list_sources(SOURCE_DIR)):
        raise RuntimeError("Smoke-test source already exists; use fresh disposable volumes")
    saved = save_source(
        "staging-smoke.txt",
        SAMPLE.encode("utf-8"),
        title=TITLE,
        specialty="Staging validation",
        notes="Synthetic test fixture; not clinical content.",
        source_dir=SOURCE_DIR,
    )
    payload = extract_source(saved["source_id"], source_dir=SOURCE_DIR)
    if payload["summary"]["mcq_candidates"] != 1:
        raise RuntimeError("Synthetic paper did not produce exactly one MCQ candidate")
    candidate = payload["mcq_candidates"][0]
    if candidate["correct_option_id"] is not None or candidate["answer_status"] != "not_extracted_or_verified":
        raise RuntimeError("Extraction smoke test must not infer an answer key")
    initialize(DB_PATH)
    record_question_attempt(
        QUESTION, "a", True, path=DB_PATH, learner_id=LEARNER,
        session_id="staging-smoke-session",
    )
    print("STAGING_SMOKE_SEEDED")


def verify() -> None:
    records = [item for item in list_sources(SOURCE_DIR) if item.get("title") == TITLE]
    if len(records) != 1:
        raise RuntimeError(f"Expected one persisted smoke source, found {len(records)}")
    record = records[0]
    original = SOURCE_DIR / record["stored_filename"]
    if not original.is_file() or original.read_text(encoding="utf-8") != SAMPLE:
        raise RuntimeError("Original uploaded source did not survive restart/restore")
    extraction = load_extraction(record["source_id"], source_dir=SOURCE_DIR)
    if not extraction or extraction["summary"]["mcq_candidates"] != 1:
        raise RuntimeError("Extracted question JSON did not survive restart/restore")
    if extraction["mcq_candidates"][0]["correct_option_id"] is not None:
        raise RuntimeError("Smoke-test extraction unexpectedly contains an answer key")
    initialize(DB_PATH)
    history = question_attempt_history(path=DB_PATH, learner_id=LEARNER)
    if len(history) != 1 or history[0]["question_id"] != QUESTION:
        raise RuntimeError("Learner attempt did not survive restart/restore")
    print("STAGING_SMOKE_VERIFIED")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seed", "verify"))
    args = parser.parse_args()
    (seed if args.mode == "seed" else verify)()


if __name__ == "__main__":
    main()
