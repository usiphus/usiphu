"""Small DB-API compatibility layer for SQLite development and Supabase Postgres hosting."""
from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def database_url() -> str | None:
    return os.getenv("USIPHU_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")


def is_postgres() -> bool:
    return bool(database_url())


class Row(dict):
    """Mapping row that also supports SQLite-style numeric indexing."""
    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class Cursor:
    def __init__(self, cursor: Any):
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self) -> Row | None:
        row = self._cursor.fetchone()
        return Row(row) if row is not None else None

    def fetchall(self) -> list[Row]:
        return [Row(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        for row in self._cursor:
            yield Row(row)


def translate_sql(statement: str) -> str:
    """Translate the small SQLite SQL subset used by USIPHU into PostgreSQL SQL."""
    sql = statement.strip()
    ignore_insert = bool(re.match(r"(?is)^INSERT\s+OR\s+IGNORE\s+INTO\b", sql))
    if ignore_insert:
        sql = re.sub(r"(?is)^INSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", sql, count=1)
    sql = re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql)
    sql = sql.replace("?", "%s")
    if ignore_insert and not re.search(r"(?is)\bON\s+CONFLICT\b", sql):
        sql = sql.rstrip(";") + " ON CONFLICT DO NOTHING"
    return sql


class PostgresConnection:
    def __init__(self, connection: Any):
        self._connection = connection

    def __enter__(self) -> PostgresConnection:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()

    def execute(self, statement: str, parameters: Any = None) -> Cursor:
        sql = translate_sql(statement)
        if parameters is None:
            cursor = self._connection.execute(sql)
        elif isinstance(parameters, Mapping):
            cursor = self._connection.execute(sql, parameters)
        elif isinstance(parameters, Sequence) and not isinstance(parameters, (str, bytes, bytearray)):
            cursor = self._connection.execute(sql, tuple(parameters))
        else:
            cursor = self._connection.execute(sql, parameters)
        return Cursor(cursor)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)


def connect_postgres() -> PostgresConnection:
    url = database_url()
    if not url:
        raise RuntimeError("USIPHU_DATABASE_URL is not configured.")
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("PostgreSQL hosting requires the psycopg dependency.") from exc
    connection = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)
    return PostgresConnection(connection)


def connect_sqlite(path: Path):
    import sqlite3
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db
