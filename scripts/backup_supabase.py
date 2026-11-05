"""Encrypted manual backup of USIPHU Postgres data and private Source Inbox objects."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from usiphu.source_inbox import DEFAULT_BUCKET, _storage_headers


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


def _storage_config() -> tuple[str, str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    bucket = os.getenv("USIPHU_STORAGE_BUCKET", DEFAULT_BUCKET)
    if not url or not key:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the local environment.")
    return url, key, bucket


def _list_bucket_objects() -> list[str]:
    url, key, bucket = _storage_config()
    headers = {**_storage_headers(key), "Content-Type": "application/json"}
    pending = [""]
    objects: list[str] = []
    while pending:
        prefix = pending.pop()
        offset = 0
        while True:
            response = httpx.post(
                f"{url}/storage/v1/object/list/{bucket}",
                headers=headers,
                json={
                    "prefix": prefix,
                    "limit": 1000,
                    "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"},
                },
                timeout=60.0,
            )
            response.raise_for_status()
            entries = response.json()
            for entry in entries:
                name = entry["name"]
                object_key = f"{prefix}/{name}" if prefix else name
                if entry.get("id") is None:
                    pending.append(object_key)
                else:
                    objects.append(object_key)
            if len(entries) < 1000:
                break
            offset += len(entries)
    return sorted(objects)


def create_backup(output_dir: Path, recipient: str) -> Path:
    database_url = os.getenv("USIPHU_DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        raise RuntimeError("Set USIPHU_DATABASE_URL in the local environment.")
    url, key, bucket = _storage_config()
    if not shutil.which("pg_dump") or not shutil.which("age"):
        raise RuntimeError("Install PostgreSQL client tools (pg_dump) and age before backing up.")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    final_path = output_dir / f"usiphu-supabase-{stamp}.tar.gz.age"
    environment = _connection_environment(database_url)
    with tempfile.TemporaryDirectory(prefix="usiphu-backup-") as temp_name:
        temp = Path(temp_name)
        dump_path = temp / "public.dump"
        app_tables = (
            "flashcards", "generated_drafts", "review_states", "review_events",
            "question_attempts", "topic_progress", "learner_topic_progress",
            "faculty_question_reviews", "faculty_question_review_events",
            "faculty_reviewer_roles", "faculty_role_events",
            "shared_assessment_reviews", "shared_assessment_review_events",
            "source_documents", "source_extractions",
            "approved_question_bank", "approved_assessment_bank",
        )
        dump_command = [
            "pg_dump", "--format=custom", "--data-only", "--no-owner", "--no-privileges",
            "--file", str(dump_path),
        ]
        for table in app_tables:
            dump_command.extend(["--table", f"public.{table}"])
        subprocess.run(dump_command, env=environment, check=True)
        objects_dir = temp / "objects"
        objects_dir.mkdir()
        manifest_objects = []
        headers = _storage_headers(key)
        for object_key in _list_bucket_objects():
            response = httpx.get(
                f"{url}/storage/v1/object/{bucket}/{object_key}",
                headers=headers, timeout=120.0,
            )
            response.raise_for_status()
            destination = objects_dir / object_key
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)
            manifest_objects.append({
                "key": object_key,
                "size": len(response.content),
                "sha256": hashlib.sha256(response.content).hexdigest(),
            })
        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "bucket": bucket,
            "database_scope": "public schema only",
            "objects": manifest_objects,
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        archive = temp / "backup.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(dump_path, arcname="public.dump")
            tar.add(temp / "manifest.json", arcname="manifest.json")
            tar.add(objects_dir, arcname="objects")
        subprocess.run(
            ["age", "--recipient", recipient, "--output", str(final_path), str(archive)],
            check=True,
        )
    digest = hashlib.sha256(final_path.read_bytes()).hexdigest()
    final_path.with_suffix(final_path.suffix + ".sha256").write_text(
        f"{digest}  {final_path.name}\n", encoding="utf-8"
    )
    return final_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("backups"))
    parser.add_argument("--age-recipient", default=os.getenv("USIPHU_BACKUP_AGE_RECIPIENT"))
    args = parser.parse_args()
    if not args.age_recipient:
        parser.error("Provide --age-recipient or USIPHU_BACKUP_AGE_RECIPIENT.")
    result = create_backup(args.output_dir, args.age_recipient)
    print(f"Encrypted backup created: {result}")
    print("Copy the encrypted archive and .sha256 file to a separate, protected location.")


if __name__ == "__main__":
    main()
