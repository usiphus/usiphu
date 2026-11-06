"""Tests for the database backend boundary."""
import sqlite3

import pytest

from usiphu.database import SQLiteBackend, connect_database, get_database_backend
from usiphu.storage import connect as storage_connect


def test_default_backend_is_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv("USIPHU_DATABASE_BACKEND", raising=False)
    monkeypatch.setenv("USIPHU_DB_PATH", str(tmp_path / "default.sqlite3"))

    backend = get_database_backend()
    assert isinstance(backend, SQLiteBackend)

    with connect_database() as db:
        db.execute("CREATE TABLE backend_probe (id INTEGER PRIMARY KEY)")
        db.execute("INSERT INTO backend_probe DEFAULT VALUES")
        assert db.execute("SELECT COUNT(*) FROM backend_probe").fetchone()[0] == 1


def test_explicit_path_is_used_and_parent_is_created(tmp_path):
    database_path = tmp_path / "nested" / "local.sqlite3"

    with SQLiteBackend().connect(database_path) as db:
        assert isinstance(db, sqlite3.Connection)
        db.execute("CREATE TABLE probe (value TEXT)")
        db.execute("INSERT INTO probe VALUES ('ok')")

    with sqlite3.connect(database_path) as db:
        assert db.execute("SELECT value FROM probe").fetchone()[0] == "ok"


def test_sqlite_foreign_keys_remain_enabled(tmp_path):
    with SQLiteBackend().connect(tmp_path / "foreign-keys.sqlite3") as db:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_storage_connection_compatibility_wrapper(tmp_path):
    database_path = tmp_path / "compat.sqlite3"
    with storage_connect(database_path) as db:
        db.execute("CREATE TABLE compatibility_probe (value TEXT)")
        db.execute("INSERT INTO compatibility_probe VALUES ('preserved')")
        assert db.execute(
            "SELECT value FROM compatibility_probe"
        ).fetchone()["value"] == "preserved"


def test_unsupported_backend_fails_closed(monkeypatch):
    monkeypatch.setenv("USIPHU_DATABASE_BACKEND", "postgres")
    with pytest.raises(RuntimeError, match="not implemented yet"):
        get_database_backend()
