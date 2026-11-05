"""Database backend boundary for USIPHU persistence.

The first backend intentionally remains SQLite so local development and existing
tests keep their current behavior. Application repositories should obtain
connections through this module (currently re-exported by usiphu.storage).
A PostgreSQL backend will be added only after SQL dialect/schema migrations are
implemented; selecting an unsupported backend fails closed rather than silently
writing to a local SQLite file.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

DEFAULT_SQLITE_PATH = Path(os.getenv("USIPHU_DB_PATH", "usiphu_data.sqlite3"))


@runtime_checkable
class DatabaseBackend(Protocol):
    """Minimal connection-factory contract shared by persistence backends."""

    def connect(self, path: Path | None = None) -> sqlite3.Connection:
        """Return a DB-API connection usable as a context manager."""


class SQLiteBackend:
    """SQLite implementation preserving the application's current semantics."""

    def __init__(self, default_path: Path = DEFAULT_SQLITE_PATH) -> None:
        self.default_path = default_path

    def connect(self, path: Path | None = None) -> sqlite3.Connection:
        database_path = path or self.default_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection


def get_database_backend() -> DatabaseBackend:
    """Return the configured backend; unsupported choices fail closed."""
    backend_name = os.getenv("USIPHU_DATABASE_BACKEND", "sqlite").strip().lower()
    if backend_name != "sqlite":
        raise RuntimeError(
            f"Database backend {backend_name!r} is not implemented yet. "
            "USIPHU currently supports only 'sqlite'; do not set a PostgreSQL "
            "backend until the PostgreSQL adapter and schema migrations are merged."
        )
    return SQLiteBackend()


def connect_database(path: Path | None = None) -> sqlite3.Connection:
    """Open a connection through the selected backend."""
    return get_database_backend().connect(path=path)
