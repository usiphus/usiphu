"""Dry-run-first import of local Source Inbox and reviewed JSON documents to Supabase."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sqlite3
import tarfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(source_dir: Path, data_dir: Path) -> tuple[list[dict], list[dict]]:
    if source_dir.exists():
        for path in source_dir.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Symlinks are not supported in Source Inbox: {path}")
    manifest = source_dir / "sources.json"
    sources = []
    if manifest.is_file():
        records = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("Source manifest must be a JSON list.")
        seen_ids, seen_hashes = set(), set()
        for record in records:
            source_id = str(record.get("source_id", "")).strip()
            filename = str(record.get("stored_filename", "")).strip()
            expected = str(record.get("sha256", "")).strip()
            relative = PurePosixPath(filename)
            if not source_id or not expected or relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe or incomplete source manifest record.")
            if source_id in seen_ids or expected in seen_hashes:
                raise ValueError("Duplicate source ID or checksum in source manifest.")
            seen_ids.add(source_id)
            seen_hashes.add(expected)
            original = source_dir.joinpath(*relative.parts)
            if not original.is_file() or original.is_symlink():
                raise ValueError(f"Missing or unsafe source file: {filename}")
            content = original.read_bytes()
            if digest(content) != expected:
                raise ValueError(f"SHA-256 mismatch for source: {filename}")
            extraction = source_dir / "extractions" / f"{source_id}.json"
            if extraction.exists():
                if extraction.is_symlink() or not extraction.is_file():
                    raise ValueError(f"Unsafe extraction: {extraction}")
                json.loads(extraction.read_text(encoding="utf-8"))
            sources.append({"record": record, "source_id": source_id,
                            "sha256": expected, "original": original,
                            "extraction": extraction if extraction.is_file() else None})

    documents = []
    for key, rel in (
        ("question-bank:past-papers-reviewed", "question_banks/past_papers_reviewed.json"),
        ("assessment-bank:reviewed-assessments", "question_banks/reviewed_assessments.json"),
        ("pilot-validation:latest", "reports/pilot-validation-latest.json"),
    ):
        path = data_dir / rel
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"Expected a JSON object: {path}")
            encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
            documents.append({"key": key, "path": path, "payload": payload,
                              "sha256": digest(encoded)})
    return sources, documents


def backup_local_state(source_dir: Path, data_dir: Path, backup_dir: Path,
                       database: Path) -> tuple[Path, Path]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_path = backup_dir / f"usiphu-before-supabase-{stamp}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        if source_dir.is_dir():
            archive.add(source_dir, arcname="source_inbox")
        for rel in ("question_banks/past_papers_reviewed.json",
                    "question_banks/reviewed_assessments.json",
                    "reports/pilot-validation-latest.json"):
            path = data_dir / rel
            if path.is_file():
                archive.add(path, arcname=f"data/{rel}")
        if database.is_file():
            snapshot = backup_dir / f".usiphu-before-supabase-{stamp}.sqlite3"
            with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as src:
                with sqlite3.connect(snapshot) as dst:
                    src.backup(dst)
            archive.add(snapshot, arcname="usiphu.sqlite3")
            snapshot.unlink()
    checksum_path = Path(f"{archive_path}.sha256")
    checksum_path.write_text(f"{digest(archive_path.read_bytes())}  {archive_path.name}\n")
    if checksum_path.read_text().split()[0] != digest(archive_path.read_bytes()):
        raise RuntimeError("Local pre-import backup checksum verification failed.")
    return archive_path, checksum_path


def apply_import(sources: list[dict], documents: list[dict], source_dir: Path) -> tuple[int, int]:
    from usiphu.durable_documents import save_json_document
    from usiphu.object_storage import get_object_storage
    from usiphu.storage import connect

    if os.getenv("USIPHU_DATABASE_BACKEND", "").lower() not in {"postgres", "postgresql"}:
        raise RuntimeError("Set USIPHU_DATABASE_BACKEND=postgres before applying.")
    if os.getenv("USIPHU_FILE_STORAGE_BACKEND", "").lower() != "supabase":
        raise RuntimeError("Set USIPHU_FILE_STORAGE_BACKEND=supabase before applying.")
    storage = get_object_storage(source_dir)
    imported = skipped = 0

    with connect() as db:
        for item in sources:
            row = db.execute(
                "SELECT source_id, sha256, extraction_key, metadata_json "
                "FROM source_documents WHERE source_id = ? OR sha256 = ?",
                (item["source_id"], item["sha256"]),
            ).fetchone()
            if row and (row["source_id"] != item["source_id"] or row["sha256"] != item["sha256"]):
                raise ValueError(f"Remote source conflicts with {item['source_id']}.")
            item["present"] = bool(row)
            item["needs_extraction"] = bool(
                row and item["extraction"] and not row["extraction_key"]
            )
        for item in documents:
            row = db.execute(
                "SELECT content_sha256 FROM app_documents WHERE document_key = ?",
                (item["key"],),
            ).fetchone()
            if row and row["content_sha256"] != item["sha256"]:
                raise ValueError(f"Remote document differs: {item['key']}; refusing overwrite.")
            item["present"] = bool(row)

    for item in sources:
        if item["present"]:
            if item["needs_extraction"]:
                extraction_key = f"extractions/{item['source_id']}.json"
                storage.upload(
                    extraction_key,
                    item["extraction"].read_bytes(),
                    "application/json",
                    upsert=True,
                )
                with connect() as db:
                    row = db.execute(
                        "SELECT metadata_json FROM source_documents WHERE source_id = ?",
                        (item["source_id"],),
                    ).fetchone()
                    metadata = json.loads(row["metadata_json"])
                    metadata["extraction_key"] = extraction_key
                    db.execute(
                        "UPDATE source_documents SET extraction_key = ?, metadata_json = ?, "
                        "updated_at = NOW() WHERE source_id = ?",
                        (extraction_key, json.dumps(metadata, ensure_ascii=False), item["source_id"]),
                    )
                imported += 1
            else:
                skipped += 1
            continue
        record = dict(item["record"])
        source_id = item["source_id"]
        original_key = f"sources/{source_id}/{item['original'].name}"
        extraction_key = f"extractions/{source_id}.json" if item["extraction"] else None
        content_type = mimetypes.guess_type(item["original"].name)[0] or "application/octet-stream"
        storage.upload(
            original_key, item["original"].read_bytes(), content_type, upsert=True
        )
        if item["extraction"] and extraction_key:
            storage.upload(extraction_key, item["extraction"].read_bytes(), "application/json", upsert=True)
        record["object_key"] = original_key
        if extraction_key:
            record["extraction_key"] = extraction_key
        with connect() as db:
            db.execute(
                "INSERT INTO source_documents "
                "(source_id, sha256, object_key, extraction_key, metadata_json, uploaded_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source_id, item["sha256"], original_key, extraction_key,
                 json.dumps(record, ensure_ascii=False),
                 record.get("uploaded_at") or datetime.now(UTC).isoformat()),
            )
        imported += 1

    for item in documents:
        if item["present"]:
            skipped += 1
            continue
        save_json_document(item["key"], item["payload"], item["path"])
        imported += 1
    return imported, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path(os.getenv("USIPHU_SOURCE_DIR", "data/source_inbox")))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--backup-dir", type=Path, default=Path(os.getenv("USIPHU_BACKUP_DIR", "data/backups")))
    parser.add_argument("--database", type=Path, default=Path(os.getenv("USIPHU_DB_PATH", "usiphu_data.sqlite3")))
    parser.add_argument("--apply", action="store_true", help="Import after a verified local backup.")
    args = parser.parse_args()
    sources, documents = inventory(args.source_dir, args.data_dir)
    print(f"Validated {len(sources)} source files and {len(documents)} JSON documents.")
    if not args.apply:
        print("DRY RUN: no database or Storage writes. Review the inventory, then rerun with --apply.")
        return
    archive, checksum = backup_local_state(args.source_dir, args.data_dir, args.backup_dir, args.database)
    print(f"Verified pre-import backup: {archive} ({checksum})")
    imported, skipped = apply_import(sources, documents, args.source_dir)
    print(f"Imported {imported}; skipped already-present {skipped}. Original local data is unchanged.")


if __name__ == "__main__":
    main()
