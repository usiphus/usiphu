"""Tests for the dry-run-first Supabase import planner."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "migrate_to_supabase", ROOT / "scripts" / "migrate_to_supabase.py"
)
migration = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(migration)


def make_source(root: Path) -> Path:
    source = root / "source_inbox"
    (source / "extractions").mkdir(parents=True)
    paper = b"synthetic exam source"
    (source / "paper.txt").write_bytes(paper)
    (source / "sources.json").write_text(
        json.dumps([{
            "source_id": "source-001",
            "stored_filename": "paper.txt",
            "sha256": hashlib.sha256(paper).hexdigest(),
            "uploaded_by": "synthetic-reviewer",
        }]),
        encoding="utf-8",
    )
    (source / "extractions" / "source-001.json").write_text(
        json.dumps({"source_id": "source-001", "mcq_candidates": []}),
        encoding="utf-8",
    )
    return source


def test_inventory_is_dry_run_and_checks_source_hashes(tmp_path):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    (data / "question_banks").mkdir(parents=True)
    (data / "question_banks" / "past_papers_reviewed.json").write_text(
        json.dumps({"bank_id": "past-papers-review-bank", "questions": []}),
        encoding="utf-8",
    )
    sources, documents = migration.inventory(source, data)
    assert len(sources) == 1
    assert sources[0]["source_id"] == "source-001"
    assert len(documents) == 1
    assert documents[0]["key"] == "question-bank:past-papers-reviewed"


def test_inventory_rejects_tampered_source_and_path_traversal(tmp_path):
    source = make_source(tmp_path)
    (source / "paper.txt").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        migration.inventory(source, tmp_path / "data")

    record = json.loads((source / "sources.json").read_text(encoding="utf-8"))
    record[0]["stored_filename"] = "../outside.txt"
    (source / "sources.json").write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe"):
        migration.inventory(source, tmp_path / "data")


def test_backup_is_checksummed_and_preserves_originals(tmp_path):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    database = tmp_path / "usiphu.sqlite3"
    import sqlite3
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE synthetic (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO synthetic DEFAULT VALUES")

    archive, checksum = migration.backup_local_state(
        source, data, tmp_path / "backups", database
    )
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert checksum.read_text(encoding="ascii").split()[0] == expected
    assert (source / "paper.txt").read_bytes() == b"synthetic exam source"
