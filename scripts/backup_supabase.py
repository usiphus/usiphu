#!/usr/bin/env python3
"""Create an encrypted off-provider backup of Supabase PostgreSQL and private Storage."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from usiphu.backup_tools import list_storage_object_keys, write_pg_service_file
from usiphu.durable_documents import remote_documents_enabled
from usiphu.object_storage import SupabaseObjectStorage


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_backup(output_dir: Path, age_recipient: str) -> Path:
    if not remote_documents_enabled():
        raise RuntimeError(
            "Backup requires USIPHU_FILE_STORAGE_BACKEND=supabase and "
            "USIPHU_DATABASE_BACKEND=postgres."
        )
    database_url = os.getenv("SUPABASE_DB_URL", "")
    if not database_url:
        raise RuntimeError("SUPABASE_DB_URL is required for PostgreSQL backup.")
    if not age_recipient.strip():
        raise ValueError("An age public recipient is required.")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    encrypted_output = output_dir / f"usiphu-backup-{stamp}.tar.gz.age"

    storage = SupabaseObjectStorage()
    bucket = storage.bucket
    with tempfile.TemporaryDirectory(prefix="usiphu-backup-") as temporary:
        root = Path(temporary)
        stage = root / "usiphu-backup"
        storage_root = stage / "storage"
        storage_root.mkdir(parents=True)
        dump_path = stage / "database.dump"

        service_file = write_pg_service_file(
            database_url, root / "pg_service.conf", "usiphu_backup"
        )
        env = os.environ.copy()
        env["PGSERVICEFILE"] = str(service_file)
        try:
            subprocess.run(
                [
                    "pg_dump",
                    "--dbname=service=usiphu_backup",
                    "--no-owner",
                    "--no-acl",
                    "--format=custom",
                    "--file",
                    str(dump_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("pg_dump is required; install PostgreSQL client tools.") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"pg_dump failed with exit code {exc.returncode}.") from exc

        objects = []
        for key in list_storage_object_keys(storage):
            safe_parts = key.split("/")
            local_path = storage_root.joinpath(*safe_parts)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            content = storage.download(key)
            local_path.write_bytes(content)
            objects.append({
                "key": key,
                "bytes": len(content),
                "sha256": sha256(content),
            })

        manifest = {
            "format_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "bucket": bucket,
            "database_dump": {
                "file": "database.dump",
                "bytes": dump_path.stat().st_size,
                "sha256": sha256(dump_path.read_bytes()),
            },
            "objects": objects,
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        archive_path = root / "usiphu-backup.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(stage, arcname="usiphu-backup")

        try:
            subprocess.run(
                [
                    "age",
                    "--recipient",
                    age_recipient,
                    "--output",
                    str(encrypted_output),
                    str(archive_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("age is required; install the age encryption utility.") from exc
        except subprocess.CalledProcessError as exc:
            encrypted_output.unlink(missing_ok=True)
            raise RuntimeError(f"age encryption failed with exit code {exc.returncode}.") from exc

    if not encrypted_output.is_file() or encrypted_output.stat().st_size == 0:
        raise RuntimeError("Encrypted backup output was not created.")
    return encrypted_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("backups"))
    parser.add_argument("--age-recipient", required=True, help="Public age recipient; private key stays offline.")
    args = parser.parse_args()
    try:
        result = create_backup(args.output_dir, args.age_recipient)
    except Exception as exc:
        print(f"Backup failed: {type(exc).__name__}: {exc}")
        return 1
    print(f"Encrypted backup created: {result}")
    print("Store this file off-provider. Keep the matching age identity offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
