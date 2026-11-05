#!/usr/bin/env python3
"""Restore an encrypted USIPHU backup into a designated Supabase project."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from usiphu.backup_tools import validate_archive_member, write_pg_service_file
from usiphu.durable_documents import remote_documents_enabled
from usiphu.object_storage import SupabaseObjectStorage


def safe_extract_archive(archive_path: Path, destination: Path) -> Path:
    """Extract only regular files/directories under the expected archive root."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            relative = validate_archive_member(member.name)
            if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsupported entry in backup archive: {relative}")
            target = destination.joinpath(*relative.split("/"))
            if destination.resolve() not in target.resolve().parents and target.resolve() != destination.resolve():
                raise ValueError("Backup archive entry escapes the restore directory.")
        archive.extractall(destination, members=members)
    root = destination / "usiphu-backup"
    if not root.is_dir():
        raise ValueError("Backup archive is missing its USIPHU root directory.")
    return root


def verify_backup(root: Path) -> dict:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format_version") != 1:
        raise ValueError("Unsupported USIPHU backup format.")
    dump_info = manifest["database_dump"]
    dump_name = validate_archive_member(str(dump_info["file"]))
    dump_path = root.joinpath(*dump_name.split("/"))
    if root.resolve() not in dump_path.resolve().parents:
        raise ValueError("Backup manifest database dump path escapes its root.")
    dump_bytes = dump_path.read_bytes()
    if hashlib.sha256(dump_bytes).hexdigest() != dump_info["sha256"]:
        raise ValueError("PostgreSQL dump checksum mismatch.")
    if len(dump_bytes) != dump_info["bytes"]:
        raise ValueError("PostgreSQL dump size mismatch.")
    for item in manifest.get("objects", []):
        key = validate_archive_member(item["key"])
        object_path = root / "storage" / key
        content = object_path.read_bytes()
        if len(content) != item["bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"Storage object checksum mismatch: {key}")
    return manifest


def restore_backup(backup_path: Path, age_identity: Path, *, confirm_overwrite: bool) -> dict:
    if not confirm_overwrite:
        raise ValueError("Pass --confirm-overwrite only when the target project is disposable or intentionally replaceable.")
    if not remote_documents_enabled():
        raise RuntimeError(
            "Restore requires USIPHU_FILE_STORAGE_BACKEND=supabase and "
            "USIPHU_DATABASE_BACKEND=postgres."
        )
    database_url = os.getenv("SUPABASE_DB_URL", "")
    if not database_url:
        raise RuntimeError("SUPABASE_DB_URL must point to the restore target database.")
    if not age_identity.is_file():
        raise FileNotFoundError("The age identity file was not found.")

    with tempfile.TemporaryDirectory(prefix="usiphu-restore-") as temporary:
        root = Path(temporary)
        archive_path = root / "backup.tar.gz"
        try:
            subprocess.run(
                [
                    "age",
                    "--decrypt",
                    "--identity",
                    str(age_identity),
                    "--output",
                    str(archive_path),
                    str(backup_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("age is required; install the age encryption utility.") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"age decryption failed with exit code {exc.returncode}.") from exc

        backup_root = safe_extract_archive(archive_path, root / "extracted")
        manifest = verify_backup(backup_root)
        storage = SupabaseObjectStorage()
        restored_objects = 0
        for item in manifest.get("objects", []):
            key = validate_archive_member(item["key"])
            object_path = backup_root / "storage" / key
            content = object_path.read_bytes()
            content_type = mimetypes.guess_type(object_path.name)[0] or "application/octet-stream"
            storage.upload(key, content, content_type, upsert=True)
            if hashlib.sha256(storage.download(key)).hexdigest() != item["sha256"]:
                raise RuntimeError(f"Storage restore verification failed: {key}")
            restored_objects += 1

        service_file = write_pg_service_file(
            database_url, root / "pg_service.conf", "usiphu_restore"
        )
        env = os.environ.copy()
        env["PGSERVICEFILE"] = str(service_file)
        dump_path = backup_root / manifest["database_dump"]["file"]
        try:
            subprocess.run(
                [
                    "pg_restore",
                    "--dbname=service=usiphu_restore",
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--no-acl",
                    "--exit-on-error",
                    str(dump_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("pg_restore is required; install PostgreSQL client tools.") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"pg_restore failed with exit code {exc.returncode}.") from exc

    return {
        "restored_at": datetime.now(UTC).isoformat(),
        "source_backup_created_at": manifest.get("created_at"),
        "source_bucket": manifest.get("bucket"),
        "target_bucket": storage.bucket,
        "storage_objects_verified": restored_objects,
        "database_dump_sha256": manifest["database_dump"]["sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--age-identity", type=Path, required=True)
    parser.add_argument(
        "--confirm-overwrite",
        action="store_true",
        help="Confirm the target Supabase database is disposable or intentionally replaceable.",
    )
    args = parser.parse_args()
    try:
        result = restore_backup(
            args.backup,
            args.age_identity,
            confirm_overwrite=args.confirm_overwrite,
        )
    except Exception as exc:
        print(f"Restore failed: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
