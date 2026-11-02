#!/usr/bin/env python3
"""Create a consistent SQLite online backup and prune expired local snapshots."""
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

source = Path(os.environ.get("USIPHU_DB_PATH", "/data/usiphu.sqlite3"))
backup_dir = Path(os.environ.get("USIPHU_BACKUP_DIR", "/backups"))
retention_days = max(1, int(os.environ.get("USIPHU_BACKUP_RETENTION_DAYS", "30")))
if not source.exists():
    raise SystemExit(f"Database does not exist: {source}")
backup_dir.mkdir(parents=True, exist_ok=True)
stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
target = backup_dir / f"usiphu-{stamp}.sqlite3"
with sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
with sqlite3.connect(target) as check:
    result = check.execute("PRAGMA integrity_check").fetchone()[0]
if result != "ok":
    target.unlink(missing_ok=True)
    raise SystemExit(f"Backup integrity check failed: {result}")
cutoff = datetime.now(UTC) - timedelta(days=retention_days)
for candidate in backup_dir.glob("usiphu-*.sqlite3"):
    if datetime.fromtimestamp(candidate.stat().st_mtime, UTC) < cutoff:
        candidate.unlink()
print(f"Backup verified: {target}")
