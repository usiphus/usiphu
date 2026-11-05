"""Restore a USIPHU backup into an explicitly confirmed Supabase project."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

from usiphu.database import is_postgres
from usiphu.source_inbox import _storage_settings, _upload_object
from usiphu.storage import DEFAULT_DB, connect, initialize


def _connection_environment(database_url: str) -> dict[str, str]:
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise ValueError("USIPHU_DATABASE_URL must be a PostgreSQL connection URI.")
    environment = os.environ.copy()
    environment.update({
        "PGHOST": parsed.hostname,
        "PGPORT": str(parsed.port or 5432),
        "PGUSER": unquote(parsed.username or ""),
        "PGPASSWORD": unquote(parsed.password or ""),
        "PGDATABASE": unquote(parsed.path.lstrip("/")),
    })
    for item in parsed.query.split("&"):
        if item.startswith("sslmode="):
            environment["PGSSLMODE"] = item.split("=", 1)[1]
    return environment


def restore_backup(backup: Path, identity: Path, confirm_target: str) -> None:
    database_url = os.getenv("USIPHU_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        raise RuntimeError("Set USIPHU_DATABASE_URL to the target Supabase database.")
    parsed = urlsplit(database_url)
    if parsed.hostname != confirm_target:
        raise ValueError("The confirmation value must exactly match the target database hostname.")
    if not shutil.which("age") or not shutil.which("pg_restore"):
        raise RuntimeError("Install age and PostgreSQL client tools (pg_restore) before restoring.")
    if not is_postgres():
        raise RuntimeError("Set USIPHU_DATABASE_URL to the target PostgreSQL connection string.")
    initialize(DEFAULT_DB)
    app_tables = (
        "flashcards", "generated_drafts", "review_states", "review_events",
        "question_attempts", "topic_progress", "learner_topic_progress",
        "faculty_question_reviews", "faculty_question_review_events",
        "faculty_reviewer_roles", "faculty_role_events",
        "shared_assessment_reviews", "shared_assessment_review_events",
        "source_documents", "source_extractions",
        "approved_question_bank", "approved_assessment_bank",
    )
    with connect(DEFAULT_DB) as db:
        populated = [
            table for table in app_tables
            if db.execute(f"SELECT COUNT(*) FROM public.{table}").fetchone()[0] > 0
        ]
    if populated:
        raise RuntimeError(
            "Restore target is not empty. Restore only into a fresh project after applying the schema migration; "
            f"non-empty tables: {', '.join(populated)}"
        )
    with tempfile.TemporaryDirectory(prefix="usiphu-restore-") as temp_name:
        temp = Path(temp_name)
        archive = temp / "backup.tar.gz"
        subprocess.run(
            ["age", "--decrypt", "--identity", str(identity), "--output", str(archive), str(backup)],
            check=True,
        )
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                member_path = Path(member.name)
                if (
                    member_path.is_absolute()
                    or ".." in member_path.parts
                    or member.issym()
                    or member.islnk()
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError("Backup archive contains an unsafe path or link.")
            tar.extractall(temp, members=members)
        manifest = json.loads((temp / "manifest.json").read_text(encoding="utf-8"))
        _, _, configured_bucket = _storage_settings()
        if manifest.get("bucket") != configured_bucket:
            raise ValueError("Backup bucket does not match the configured target bucket.")
        environment = _connection_environment(database_url)
        subprocess.run(
            [
                "pg_restore", "--data-only", "--no-owner", "--no-privileges",
                "--single-transaction", "--exit-on-error",
                "--host", environment["PGHOST"],
                "--port", environment["PGPORT"],
                "--username", environment["PGUSER"],
                "--dbname", environment["PGDATABASE"],
                str(temp / "public.dump"),
            ],
            env=environment, check=True,
        )
        objects_dir = temp / "objects"
        for item in manifest.get("objects", []):
            source = objects_dir / item["key"]
            content = source.read_bytes()
            if len(content) != item["size"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError(f"Backup object checksum failed: {item['key']}")
            _upload_object(item["key"], content, Path(item["key"]).name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True, help="Offline age private identity file.")
    parser.add_argument("--confirm-target", required=True, help="Exact hostname of the target Supabase database.")
    parser.add_argument("--apply", action="store_true", help="Required because restore replaces public-schema objects.")
    args = parser.parse_args()
    if not args.apply:
        parser.error("Restore is destructive; pass --apply only after verifying the target and backup.")
    restore_backup(args.backup, args.identity, args.confirm_target)
    print("Database and Storage restore completed. Run application acceptance checks before opening access.")


if __name__ == "__main__":
    main()
