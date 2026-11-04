#!/usr/bin/env python3
"""Restore a paired SQLite + Source Inbox backup into empty mounted volumes."""
import argparse
import hashlib
import os
import shutil
import sqlite3
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_database(path: Path) -> None:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise ValueError(f"Database integrity check failed: {result}")


def verify_archive(archive_path: Path, checksum_path: Path) -> None:
    fields = checksum_path.read_text(encoding="ascii").strip().split()
    if len(fields) < 1 or fields[0] != sha256_file(archive_path):
        raise ValueError("Source archive SHA-256 does not match its checksum file")


def extract_safe(archive_path: Path, staging: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise ValueError("Source archive is empty")
        for member in members:
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe archive path: {member.name}")
            if not relative.parts or relative.parts[0] != "source_inbox":
                raise ValueError(f"Unexpected archive root: {member.name}")
            if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                raise ValueError(f"Unsupported archive entry: {member.name}")
            if member.isfile():
                target = staging.joinpath(*relative.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError(f"Unable to read archive member: {member.name}")
                with stream, target.open("xb") as output:
                    shutil.copyfileobj(stream, output)
            elif len(relative.parts) > 1:
                staging.joinpath(*relative.parts[1:]).mkdir(parents=True, exist_ok=True)


def restore(
    database_backup: Path,
    source_archive: Path,
    checksum_file: Path,
    database_target: Path,
    source_target: Path,
) -> None:
    for path in (database_backup, source_archive, checksum_file):
        if not path.is_file():
            raise ValueError(f"Backup input does not exist: {path}")
    if database_target.exists():
        raise ValueError(f"Refusing to overwrite database target: {database_target}")
    source_target.mkdir(parents=True, exist_ok=True)
    if any(source_target.iterdir()):
        raise ValueError(f"Refusing to restore into a non-empty Source Inbox: {source_target}")

    verify_database(database_backup)
    verify_archive(source_archive, checksum_file)
    database_target.parent.mkdir(parents=True, exist_ok=True)
    temporary_database = database_target.with_name(f".{database_target.name}.restore-tmp")
    staging = Path(tempfile.mkdtemp(prefix=".usiphu-restore-", dir=source_target))
    installed_database = False
    installed_source_items: list[Path] = []
    try:
        shutil.copy2(database_backup, temporary_database)
        verify_database(temporary_database)
        extract_safe(source_archive, staging)
        unexpected = [item for item in source_target.iterdir() if item != staging]
        if database_target.exists() or unexpected:
            raise ValueError("Restore targets changed during validation; refusing to overwrite")
        os.link(temporary_database, database_target)
        installed_database = True
        temporary_database.unlink()
        for item in list(staging.iterdir()):
            target = source_target / item.name
            if target.exists():
                raise ValueError(f"Refusing to overwrite restored source path: {target}")
            item.rename(target)
            installed_source_items.append(target)
    except Exception:
        for item in reversed(installed_source_items):
            if item.exists():
                item.replace(staging / item.name)
        if installed_database:
            database_target.unlink(missing_ok=True)
        raise
    finally:
        temporary_database.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-backup", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--checksum", type=Path, required=True)
    parser.add_argument("--database-target", type=Path, default=Path("/data/usiphu.sqlite3"))
    parser.add_argument("--source-target", type=Path, default=Path("/source-inbox"))
    args = parser.parse_args()
    restore(
        args.database_backup,
        args.source_archive,
        args.checksum,
        args.database_target,
        args.source_target,
    )
    print(f"Restored and verified SQLite database: {args.database_target}")
    print(f"Restored Source Inbox files into: {args.source_target}")


if __name__ == "__main__":
    main()
