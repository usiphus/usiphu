from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.migrate_learner_faculty_data import TABLES, create_backup, inspect_source, migrate


def make_database(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE flashcards (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL)")
        db.execute("INSERT INTO flashcards VALUES ('card-a', 'https://issuer/:learner-a')")
        db.execute("CREATE TABLE review_states (card_id TEXT PRIMARY KEY, repetitions INTEGER)")
        db.execute("INSERT INTO review_states VALUES ('card-a', 4)")


def test_inventory_covers_every_learner_and_faculty_table(tmp_path: Path):
    database = tmp_path / "usiphu.sqlite3"
    make_database(database)
    result = inspect_source(database)
    assert tuple(result["tables"]) == TABLES
    assert result["tables"]["flashcards"]["rows"] == 1
    assert result["tables"]["review_states"]["rows"] == 1
    assert result["tables"]["faculty_reviewer_roles"]["present"] is False
    assert result["total_rows"] == 2


def test_backup_is_a_readable_sqlite_snapshot_with_checksum(tmp_path: Path):
    database = tmp_path / "usiphu.sqlite3"
    make_database(database)
    backup, digest = create_backup(database, tmp_path / "backups")
    assert len(digest) == 64
    assert backup.is_file()
    assert backup.with_suffix(".sqlite3.sha256").is_file()
    with sqlite3.connect(backup) as db:
        assert db.execute("SELECT count(*) FROM flashcards").fetchone()[0] == 1


def test_apply_refuses_to_run_without_postgres_url(monkeypatch, tmp_path: Path):
    database = tmp_path / "usiphu.sqlite3"
    make_database(database)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_DB_URL"):
        migrate(database, tmp_path / "backups", apply=True)
