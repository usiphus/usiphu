"""One-way, non-destructive migration from a local USIPHU SQLite workspace to Supabase."""
from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Any
from pathlib import Path

from usiphu.database import is_postgres
from usiphu.source_inbox import _upload_object
from usiphu.storage import DEFAULT_DB, connect, initialize

ROOT = Path(__file__).resolve().parent.parent
TABLES = (
    "flashcards",
    "generated_drafts",
    "review_states",
    "review_events",
    "question_attempts",
    "topic_progress",
    "learner_topic_progress",
    "faculty_question_reviews",
    "faculty_question_review_events",
    "faculty_reviewer_roles",
    "faculty_role_events",
    "shared_assessment_reviews",
    "shared_assessment_review_events",
)
IDENTITY_TABLES = (
    "review_events",
    "question_attempts",
    "faculty_question_review_events",
    "faculty_role_events",
    "shared_assessment_review_events",
)


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _copy_sqlite_tables(source: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        if not _table_exists(source, table):
            continue
        rows = source.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            counts[table] = 0
            continue
        columns = [item[0] for item in source.execute(f"SELECT * FROM {table}").description]
        column_sql = ",".join(columns)
        placeholders = ",".join("?" for _ in columns)
        copied = 0
        with connect(DEFAULT_DB) as target:
            for row in rows:
                cursor = target.execute(
                    f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                    tuple(row),
                )
                copied += max(cursor.rowcount, 0)
        counts[table] = copied
    with connect(DEFAULT_DB) as target:
        target.execute(
            """INSERT INTO learner_topic_progress(owner_id,topic_id,status,confidence,updated_at)
               SELECT 'local',topic_id,status,confidence,updated_at FROM topic_progress
               ON CONFLICT(owner_id,topic_id) DO NOTHING"""
        )
    for table in IDENTITY_TABLES:
        with connect(DEFAULT_DB) as target:
            target.execute(
                f"""SELECT setval(
                    pg_get_serial_sequence('public.{table}', 'id'),
                    COALESCE(MAX(id), 1),
                    COUNT(*) > 0
                ) FROM {table}"""
            )
    return counts


def _copy_source_workspace(source_dir: Path, apply: bool) -> dict[str, int]:
    manifest = source_dir / "sources.json"
    if not manifest.is_file():
        return {"source_files": 0, "extractions": 0}
    records = json.loads(manifest.read_text(encoding="utf-8"))
    copied_sources = 0
    for record in records:
        source_id = record["source_id"]
        local_file = source_dir / record["stored_filename"]
        if not local_file.is_file():
            raise FileNotFoundError(f"Missing local source file for {source_id}: {local_file}")
        object_key = f"{source_id}/{record['stored_filename']}"
        metadata = {**record, "object_key": object_key}
        if not apply:
            copied_sources += 1
            continue
        with connect(DEFAULT_DB) as target:
            existing = target.execute(
                "SELECT source_id FROM source_documents WHERE source_id=? OR sha256=?",
                (source_id, record["sha256"]),
            ).fetchone()
        if existing:
            if existing["source_id"] != source_id:
                raise ValueError(
                    f"Source {source_id} duplicates an existing SHA-256 under ID {existing['source_id']}; resolve manually."
                )
            continue
        _upload_object(object_key, local_file.read_bytes(), record["original_filename"])
        with connect(DEFAULT_DB) as target:
            target.execute(
                """INSERT INTO source_documents(source_id,sha256,object_key,metadata_json,uploaded_at)
                   VALUES(?,?,?,?,?) ON CONFLICT(source_id) DO NOTHING""",
                (source_id, record["sha256"], object_key,
                 json.dumps(metadata, ensure_ascii=False), record["uploaded_at"]),
            )
        copied_sources += 1

    extraction_dir = source_dir / "extractions"
    copied_extractions = 0
    if extraction_dir.is_dir():
        for path in sorted(extraction_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            source_id = str(payload.get("source_id") or path.stem)
            if apply:
                with connect(DEFAULT_DB) as target:
                    target.execute(
                        """INSERT INTO source_extractions(source_id,payload_json)
                           VALUES(?,?) ON CONFLICT(source_id) DO NOTHING""",
                        (source_id, json.dumps(payload, ensure_ascii=False)),
                    )
            copied_extractions += 1
    return {"source_files": copied_sources, "extractions": copied_extractions}


def _copy_approved_banks(apply: bool) -> dict[str, int]:
    result = {"approved_questions": 0, "approved_assessments": 0}
    question_file = ROOT / "data" / "question_banks" / "past_papers_reviewed.json"
    if question_file.is_file():
        payload = json.loads(question_file.read_text(encoding="utf-8"))
        for item in payload.get("questions", []):
            result["approved_questions"] += 1
            if apply:
                with connect(DEFAULT_DB) as target:
                    target.execute(
                        """INSERT INTO approved_question_bank(question_id,payload_json)
                           VALUES(?,?) ON CONFLICT(question_id) DO NOTHING""",
                        (item["id"], json.dumps(item, ensure_ascii=False)),
                    )
    assessment_file = ROOT / "data" / "question_banks" / "reviewed_assessments.json"
    if assessment_file.is_file():
        payload = json.loads(assessment_file.read_text(encoding="utf-8"))
        for item in payload.get("assessments", []):
            result["approved_assessments"] += 1
            if apply:
                with connect(DEFAULT_DB) as target:
                    target.execute(
                        """INSERT INTO approved_assessment_bank(assessment_id,payload_json)
                           VALUES(?,?) ON CONFLICT(assessment_id) DO NOTHING""",
                        (item["id"], json.dumps(item, ensure_ascii=False)),
                    )
    return result


def migrate(source_db: Path, source_dir: Path, apply: bool) -> dict[str, Any]:
    if not is_postgres():
        raise RuntimeError("Set USIPHU_DATABASE_URL to the target Supabase PostgreSQL session-mode URL.")
    if not source_db.is_file():
        raise FileNotFoundError(f"Local SQLite database not found: {source_db}")
    if apply:
        initialize(DEFAULT_DB)
    source = sqlite3.connect(source_db)
    source.row_factory = sqlite3.Row
    try:
        tables = _copy_sqlite_tables(source) if apply else {
            table: source.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in TABLES if _table_exists(source, table)
        }
    finally:
        source.close()
    source_counts = _copy_source_workspace(source_dir, apply)
    bank_counts = _copy_approved_banks(apply)
    return {
        "mode": "applied" if apply else "dry_run",
        "sqlite_tables": tables,
        **source_counts,
        **bank_counts,
        "note": "Local files are not deleted. Re-run is safe for existing IDs; review conflicts manually.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, default=ROOT / "usiphu_data.sqlite3")
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data" / "source_inbox")
    parser.add_argument("--apply", action="store_true", help="Write to Supabase. Without this flag, only report counts.")
    args = parser.parse_args()
    report = migrate(args.source_db, args.source_dir, args.apply)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
