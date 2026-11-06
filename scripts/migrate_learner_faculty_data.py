"""One-time, dry-run-first migration of all SQLite learner/faculty state to PostgreSQL.

The target schema must already be installed with migrations 0001-0003. The
importer refuses non-empty target tables, preserves primary/identity IDs, and
verifies row counts plus deterministic content digests before commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

def _canonical(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value

def _digest(rows: list[tuple[Any, ...]]) -> str:
    encoded_rows = [
        json.dumps([_canonical(value) for value in row], ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        for row in rows
    ]
    encoded = json.dumps(sorted(encoded_rows), ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()

def inspect_source(database: Path) -> dict[str, Any]:
    if not database.is_file() or database.is_symlink():
        raise ValueError(f"SQLite database is missing or unsafe: {database}")
    report: dict[str, Any] = {"source": str(database), "tables": {}}
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as conn:
        for table in TABLES:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                report["tables"][table] = {"present": False, "rows": 0, "sha256": _digest([])}
                continue
            columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]
            quoted = ", ".join(f'"{name}"' for name in columns)
            rows = conn.execute(f'SELECT {quoted} FROM "{table}"').fetchall()
            report["tables"][table] = {
                "present": True, "columns": columns, "rows": len(rows), "sha256": _digest(rows)
            }
    report["total_rows"] = sum(item["rows"] for item in report["tables"].values())
    return report

def create_backup(database: Path, backup_dir: Path) -> tuple[Path, str]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    destination = backup_dir / f"usiphu-sqlite-before-postgres-{stamp}.sqlite3"
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as source:
        with sqlite3.connect(destination) as target:
            source.backup(target)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    (destination.with_suffix(".sqlite3.sha256")).write_text(
        f"{digest}  {destination.name}\n", encoding="utf-8"
    )
    return destination, digest

def _target_columns(conn: Any, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        (table,),
    ).fetchall()
    return [row[0] for row in rows]

def _identity_columns(conn: Any, table: str) -> set[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s AND is_identity='YES'",
        (table,),
    ).fetchall()
    return {row[0] for row in rows}


def migrate(database: Path, backup_dir: Path, apply: bool = False) -> dict[str, Any]:
    report = inspect_source(database)
    if not apply:
        report["mode"] = "dry_run"
        return report
    database_url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Set SUPABASE_DB_URL in the local environment before --apply.")
    backup, backup_sha256 = create_backup(database, backup_dir)
    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:
        raise RuntimeError("Install the project PostgreSQL dependency before --apply.") from exc

    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as source, psycopg.connect(
        database_url, sslmode=os.getenv("USIPHU_DATABASE_SSLMODE", "require"),
        application_name="usiphu-sqlite-migration"
    ) as target:
        # One transaction: any schema, conflict, or verification failure rolls
        # back the entire import. Never merge into an already-used destination.
        for table in TABLES:
            target_count = target.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier("public"), sql.Identifier(table))
            ).fetchone()[0]
            if target_count:
                raise RuntimeError(f"Target table public.{table} is not empty; refusing a merge.")
        for table in TABLES:
            item = report["tables"][table]
            if not item["present"] or not item["rows"]:
                continue
            columns = item["columns"]
            target_columns = _target_columns(target, table)
            if columns != target_columns:
                raise RuntimeError(
                    f"Column mismatch for {table}: SQLite={columns}, PostgreSQL={target_columns}"
                )
            quoted = ", ".join(f'"{name}"' for name in columns)
            rows = source.execute(f'SELECT {quoted} FROM "{table}"').fetchall()
            statement = sql.SQL("INSERT INTO public.{} ({}) VALUES ({})").format(
                sql.Identifier(table),
                sql.SQL(", ").join(sql.Identifier(name) for name in columns),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            )
            target.cursor().executemany(statement, rows)
            inserted = target.execute(
                sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table))
            ).fetchone()[0]
            target_rows = target.execute(
                sql.SQL("SELECT {} FROM public.{}").format(
                    sql.SQL(", ").join(sql.Identifier(name) for name in columns),
                    sql.Identifier(table),
                )
            ).fetchall()
            if inserted != item["rows"] or _digest(target_rows) != item["sha256"]:
                raise RuntimeError(f"Post-import verification failed for {table}.")
            item["imported"] = inserted
            item["verified_sha256"] = _digest(target_rows)
            if "id" in _identity_columns(target, table):
                target.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                    "GREATEST(COALESCE((SELECT MAX(id) FROM public." + table + "), 1), 1), "
                    "EXISTS(SELECT 1 FROM public." + table + "))",
                    (f"public.{table}",),
                )
        report["mode"] = "applied"
        report["backup"] = str(backup)
        report["backup_sha256"] = backup_sha256
        report["verified_total_rows"] = sum(
            item.get("imported", 0) for item in report["tables"].values()
        )
    report_path = backup_dir / f"usiphu-sqlite-migration-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    return report

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path(os.getenv("USIPHU_DB_PATH", "usiphu_data.sqlite3")))
    parser.add_argument("--backup-dir", type=Path, default=Path("migration-backups"))
    parser.add_argument("--apply", action="store_true", help="Back up and import into an empty PostgreSQL target.")
    args = parser.parse_args()
    result = migrate(args.database, args.backup_dir, apply=args.apply)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not args.apply:
        print("\nDRY RUN ONLY. Review row counts and hashes; use --apply only with a verified, empty target.")

if __name__ == "__main__":
    main()
