#!/usr/bin/env python3
"""Back up SQLite and the complete Source Inbox, then prune expired snapshots."""
import hashlib
import os
import sqlite3
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

source = Path(os.environ.get("USIPHU_DB_PATH", "/data/usiphu.sqlite3"))
source_dir = Path(os.environ.get("USIPHU_SOURCE_DIR", "/source-inbox"))
backup_dir = Path(os.environ.get("USIPHU_BACKUP_DIR", "/backups"))
retention_days = max(1, int(os.environ.get("USIPHU_BACKUP_RETENTION_DAYS", "30")))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not source.exists():
        raise SystemExit(f"Database does not exist: {source}")
    if not source_dir.exists() or not source_dir.is_dir():
        raise SystemExit(f"Source Inbox directory does not exist: {source_dir}")

    for item in source_dir.rglob("*"):
        if item.is_symlink() or not (item.is_dir() or item.is_file()):
            raise RuntimeError(f"Unsupported Source Inbox filesystem entry: {item}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    database_target = backup_dir / f"usiphu-{stamp}.sqlite3"
    database_temporary = backup_dir / f".{database_target.name}.tmp"
    archive_target = backup_dir / f"usiphu-sources-{stamp}.tar.gz"
    archive_temporary = backup_dir / f".{archive_target.name}.tmp"

    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30) as src:
            with sqlite3.connect(database_temporary) as dst:
                src.backup(dst)
        with sqlite3.connect(database_temporary) as check:
            result = check.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"Database backup integrity check failed: {result}")

        with tarfile.open(archive_temporary, "w:gz") as archive:
            archive.add(source_dir, arcname="source_inbox")
        with tarfile.open(archive_temporary, "r:gz") as check:
            members = check.getnames()
            if not members or not all(
                (member.name == "source_inbox" or member.name.startswith("source_inbox/"))
                and (member.isdir() or member.isfile())
                for member in check.getmembers()
            ):
                raise RuntimeError("Source Inbox archive contains unexpected paths or file types")
            manifest = source_dir / "sources.json"
            if manifest.exists() and "source_inbox/sources.json" not in members:
                raise RuntimeError("Source Inbox manifest is missing from archive")

        database_temporary.replace(database_target)
        archive_temporary.replace(archive_target)
        checksum_target = backup_dir / f"usiphu-sources-{stamp}.tar.gz.sha256"
        checksum_temporary = backup_dir / f".{checksum_target.name}.tmp"
        checksum_temporary.write_text(
            f"{sha256_file(archive_target)}  {archive_target.name}\n",
            encoding="ascii",
        )
        checksum_temporary.replace(checksum_target)
    except Exception:
        database_temporary.unlink(missing_ok=True)
        archive_temporary.unlink(missing_ok=True)
        raise

    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    for pattern in ("usiphu-*.sqlite3", "usiphu-sources-*.tar.gz", "usiphu-sources-*.tar.gz.sha256"):
        for candidate in backup_dir.glob(pattern):
            if datetime.fromtimestamp(candidate.stat().st_mtime, UTC) < cutoff:
                candidate.unlink()

    print(f"Verified database backup: {database_target}")
    print(f"Source Inbox archive: {archive_target}")
    print(f"Source archive SHA-256: {sha256_file(archive_target)}")


if __name__ == "__main__":
    main()
