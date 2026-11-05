#!/usr/bin/env python3
"""Dry-run-first import of promoted banks and pilot reports into private Supabase Storage."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys

from usiphu.durable_documents import (
    json_document_exists,
    load_json_document,
    remote_documents_enabled,
    save_json_document,
)

BANK_FILES = {
    "question-banks/past-papers-reviewed.json": Path("question_banks/past_papers_reviewed.json"),
    "question-banks/reviewed-assessments.json": Path("question_banks/reviewed_assessments.json"),
}


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(data_root: Path) -> list[tuple[str, Path]]:
    documents = []
    for key, relative in BANK_FILES.items():
        path = data_root / relative
        if path.is_file():
            documents.append((key, path))
    report_root = data_root / "source_inbox" / "reports"
    if report_root.is_dir():
        for path in sorted(report_root.rglob("*.json")):
            relative = path.relative_to(report_root).as_posix()
            documents.append((f"reports/pilot-validation/{relative}", path))
    keys = [key for key, _path in documents]
    if len(keys) != len(set(keys)):
        raise ValueError("Document inventory contains duplicate logical keys")
    for _key, path in documents:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object: {path}")
    return documents


def migrate(
    data_root: Path,
    *,
    apply: bool = False,
    replace_existing: bool = False,
    backup_root: Path | None = None,
) -> dict:
    documents = inventory(data_root)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "mode": "apply" if apply else "dry_run",
        "source_files": len(documents),
        "documents": [],
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
            raise ValueError("Apply requires --backup-dir so source files are backed up before writes.")
        backup_root.mkdir(parents=True, exist_ok=True)

    for key, path in documents:
        payload = json.loads(path.read_text(encoding="utf-8"))
        canonical = (json.dumps(payload, ensure_ascii=False, indent=2) + "\\n").encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        item = {
            "document_key": key,
            "source_path": str(path),
            "sha256": digest,
            "bytes": path.stat().st_size,
            "status": "would_import",
        }
        if apply:
            backup = backup_root / key
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(path, backup)
            elif checksum(backup) != digest:
                raise RuntimeError(f"Backup path already contains different content: {backup}")

            exists = json_document_exists(key)
            if exists:
                current = load_json_document(key, path)
                current_digest = hashlib.sha256(
                    (json.dumps(current, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                ).hexdigest()
                if current_digest == digest:
                    item["status"] = "already_current"
                    item["backup_path"] = str(backup)
                    report["documents"].append(item)
                    continue
                if not replace_existing:
                    raise RuntimeError(
                        f"Remote document differs from local source: {key}; rerun with --replace-existing after review."
                    )

            save_json_document(key, payload, path)
            verified = load_json_document(key, path)
            verified_digest = hashlib.sha256(
                (json.dumps(verified, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            ).hexdigest()
            if verified_digest != digest:
                raise RuntimeError(f"Post-import verification failed: {key}")
            item["status"] = "imported_and_verified"
            item["backup_path"] = str(backup)
        report["documents"].append(item)

    report["completed"] = True
    report["finished_at"] = datetime.now(UTC).isoformat()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--apply", action="store_true", help="Write to remote storage; default is dry-run.")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--report", type=Path, default=Path("document-migration-report.json"))
    args = parser.parse_args()

    try:
        report = migrate(
            args.data_root,
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
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
