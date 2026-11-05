#!/usr/bin/env python3
"""Dry-run-first migration of legacy local Source Inbox data to private Supabase Storage."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

from usiphu.durable_documents import remote_documents_enabled
from usiphu.source_inbox import import_source_record


def inventory(source_dir: Path) -> list[tuple[dict, bytes, dict | None, Path, Path | None]]:
    manifest = source_dir / "sources.json"
    if not manifest.is_file():
        raise FileNotFoundError(f"Source Inbox manifest not found: {manifest}")
    records = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Source Inbox manifest must contain a JSON list.")
    seen = set()
    results = []
    for record in records:
        source_id = str(record.get("source_id", ""))
        stored_name = str(record.get("stored_filename", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", source_id):
            raise ValueError(f"Invalid source ID in manifest: {source_id!r}")
        if source_id in seen:
            raise ValueError(f"Duplicate source ID in manifest: {source_id}")
        seen.add(source_id)
        if not stored_name or Path(stored_name).name != stored_name:
            raise ValueError(f"Unsafe stored filename in manifest for {source_id}")
        original_path = source_dir / stored_name
        if not original_path.is_file():
            raise FileNotFoundError(f"Original source file is missing: {original_path}")
        original_bytes = original_path.read_bytes()
        digest = hashlib.sha256(original_bytes).hexdigest()
        if digest != record.get("sha256"):
            raise ValueError(f"Source checksum mismatch for {source_id}")

        extraction_path = source_dir / "extractions" / f"{source_id}.json"
        extraction = None
        if extraction_path.exists():
            extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
            if not isinstance(extraction, dict) or extraction.get("source_id") != source_id:
                raise ValueError(f"Extraction metadata mismatch for {source_id}")
        elif record.get("status") == "extracted_pending_review":
            raise FileNotFoundError(f"Manifest says extracted but candidate JSON is missing: {source_id}")
        results.append((record, original_bytes, extraction, original_path, extraction_path if extraction else None))
    return results


def migrate(
    source_dir: Path,
    *,
    apply: bool = False,
    replace_existing: bool = False,
    backup_root: Path | None = None,
) -> dict:
    records = inventory(source_dir)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "mode": "apply" if apply else "dry_run",
        "source_count": len(records),
        "extraction_count": sum(extraction is not None for _, _, extraction, _, _ in records),
        "sources": [],
        "errors": [],
        "completed": False,
    }
    if apply:
        if not remote_documents_enabled():
            raise RuntimeError(
                "Apply requires USIPHU_FILE_STORAGE_BACKEND=supabase and "
                "USIPHU_DATABASE_BACKEND=postgres."
            )
        if backup_root is None:
            raise ValueError("Apply requires --backup-dir before any remote writes.")
        backup_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_dir / "sources.json", backup_root / "sources.json")

    for record, original_bytes, extraction, original_path, extraction_path in records:
        source_id = record["source_id"]
        item = {
            "source_id": source_id,
            "filename": record.get("original_filename"),
            "sha256": record["sha256"],
            "bytes": len(original_bytes),
            "extraction_present": extraction is not None,
            "status": "would_import",
        }
        if apply:
            original_backup = backup_root / "originals" / original_path.name
            original_backup.parent.mkdir(parents=True, exist_ok=True)
            if not original_backup.exists():
                shutil.copy2(original_path, original_backup)
            if hashlib.sha256(original_backup.read_bytes()).hexdigest() != record["sha256"]:
                raise RuntimeError(f"Original backup checksum mismatch: {source_id}")

            if extraction_path:
                extraction_backup = backup_root / "extractions" / extraction_path.name
                extraction_backup.parent.mkdir(parents=True, exist_ok=True)
                if not extraction_backup.exists():
                    shutil.copy2(extraction_path, extraction_backup)
                if extraction_backup.read_bytes() != extraction_path.read_bytes():
                    raise RuntimeError(f"Extraction backup verification failed: {source_id}")

            import_source_record(
                record,
                original_bytes,
                extraction,
                source_dir=source_dir,
                replace_existing=replace_existing,
            )
            item["status"] = "imported_and_verified"
            item["backup_original"] = str(original_backup)
            if extraction_path:
                item["backup_extraction"] = str(extraction_backup)
        report["sources"].append(item)

    report["completed"] = True
    report["finished_at"] = datetime.now(UTC).isoformat()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path("data/source_inbox"))
    parser.add_argument("--apply", action="store_true", help="Write to remote; default is dry-run.")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--report", type=Path, default=Path("source-inbox-migration-report.json"))
    args = parser.parse_args()

    try:
        report = migrate(
            args.source_dir,
            apply=args.apply,
            replace_existing=args.replace_existing,
            backup_root=args.backup_dir,
        )
    except Exception as exc:
        report = {
            "mode": "apply" if args.apply else "dry_run",
            "completed": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
