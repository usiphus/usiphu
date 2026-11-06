"""PostgreSQL backend selection and optional integration smoke tests."""
import os

import pytest

from usiphu.database import PostgresBackend, get_database_backend


def test_postgres_backend_requires_connection_secret(monkeypatch):
    monkeypatch.setenv("USIPHU_DATABASE_BACKEND", "postgres")
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_DB_URL"):
        get_database_backend()


def test_postgres_backend_is_selected(monkeypatch):
    monkeypatch.setenv("USIPHU_DATABASE_BACKEND", "postgres")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://example.invalid/db")
    assert isinstance(get_database_backend(), PostgresBackend)


@pytest.mark.skipif(not os.getenv("USIPHU_TEST_POSTGRES_URL"), reason="No disposable PostgreSQL test URL configured")
def test_postgres_connection_smoke(monkeypatch):
    monkeypatch.setenv("USIPHU_DATABASE_BACKEND", "postgres")
    monkeypatch.setenv("SUPABASE_DB_URL", os.environ["USIPHU_TEST_POSTGRES_URL"])
    from usiphu.database import connect_database

    with connect_database() as db:
        row = db.execute("SELECT 7 AS answer").fetchone()
        assert row["answer"] == 7
        assert row[0] == 7
