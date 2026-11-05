"""Source Inbox metadata and original-file persistence."""
import hashlib
import json
import mimetypes
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from usiphu.object_storage import get_object_storage
from usiphu.storage import connect

DEFAULT_SOURCE_DIR = Path(os.getenv(
    "USIPHU_SOURCE_DIR", Path(__file__).resolve().parent.parent / "data" / "source_inbox"
))
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg"}
MAX_FILE_BYTES = 50 * 1024 * 1024


def _remote_enabled() -> bool:
    enabled = os.getenv("USIPHU_FILE_STORAGE_BACKEND", "local").strip().lower() == "supabase"
    if enabled and os.getenv("USIPHU_DATABASE_BACKEND", "sqlite").strip().lower() not in {"postgres", "postgresql"}:
        raise RuntimeError("Supabase file storage requires USIPHU_DATABASE_BACKEND=postgres.")
    return enabled


def _manifest_path(source_dir: Path) -> Path:
    return source_dir / "sources.json"


def _remote_records() -> list[dict]:
    with connect() as db:
        rows = db.execute(
            "SELECT metadata_json FROM source_documents ORDER BY uploaded_at DESC"
        ).fetchall()
    return [json.loads(row["metadata_json"]) for row in rows]


def list_sources(source_dir: Path = DEFAULT_SOURCE_DIR) -> list[dict]:
    """Return the source inbox catalogue, newest first."""
    if _remote_enabled():
        return sorted(_remote_records(), key=lambda item: item.get("uploaded_at", ""), reverse=True)
    manifest = _manifest_path(source_dir)
    if not manifest.exists():
        return []
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return sorted(payload, key=lambda item: item.get("uploaded_at", ""), reverse=True)


def save_source(
    filename: str,
    content: bytes,
    *,
    title: str | None = None,
    specialty: str = "Unassigned",
    exam_year: str = "",
    notes: str = "",
    source_dir: Path = DEFAULT_SOURCE_DIR,
) -> dict:
    """Store an uploaded paper and provenance metadata without extracting questions."""
    original_name = Path(filename).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix or 'no extension'}")
    if not content:
        raise ValueError("The uploaded file is empty")
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("Files must be 50 MB or smaller")

    digest = hashlib.sha256(content).hexdigest()
    clean_title = (title or Path(original_name).stem).strip()[:200]
    clean_specialty = specialty.strip()[:100] or "Unassigned"
    source_id = uuid.uuid4().hex
    stored_name = f"{source_id}{suffix}"
    record = {
        "source_id": source_id,
        "original_filename": original_name[:255],
        "stored_filename": stored_name,
        "title": clean_title,
        "specialty": clean_specialty,
        "exam_year": exam_year.strip()[:20],
        "notes": notes.strip()[:2000],
        "size_bytes": len(content),
        "sha256": digest,
        "uploaded_at": datetime.now(UTC).isoformat(),
        "status": "awaiting_extraction",
        "question_count": 0,
    }

    if _remote_enabled():
        object_key = f"sources/{source_id}/{stored_name}"
        storage = get_object_storage(source_dir)
        with connect() as db:
            duplicate = db.execute(
                "SELECT source_id FROM source_documents WHERE sha256 = ?",
                (digest,),
            ).fetchone()
            if duplicate:
                raise ValueError("This exact file is already in the source inbox")
            storage.upload(
                object_key,
                content,
                mimetypes.guess_type(original_name)[0] or "application/octet-stream",
            )
            record["object_key"] = object_key
            try:
                db.execute(
                    "INSERT INTO source_documents "
                    "(source_id, sha256, object_key, metadata_json, uploaded_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (source_id, digest, object_key, json.dumps(record, ensure_ascii=False),
                     record["uploaded_at"]),
                )
            except Exception:
                storage.delete(object_key)
                raise
        return record

    source_dir.mkdir(parents=True, exist_ok=True)
    records = list_sources(source_dir)
    if any(item.get("sha256") == digest for item in records):
        raise ValueError("This exact file is already in the source inbox")
    destination = source_dir / stored_name
    temporary = source_dir / f".{stored_name}.tmp"
    temporary.write_bytes(content)
    temporary.replace(destination)
    records.append(record)
    manifest = _manifest_path(source_dir)
    temp_manifest = source_dir / ".sources.json.tmp"
    temp_manifest.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_manifest.replace(manifest)
    return record


def read_source_bytes(source: dict, source_dir: Path = DEFAULT_SOURCE_DIR) -> bytes:
    """Read original bytes from the selected backend."""
    if _remote_enabled():
        return get_object_storage(source_dir).download(source["object_key"])
    return (source_dir / source["stored_filename"]).read_bytes()


def _update_source(source_dir: Path, source_id: str, updates: dict) -> None:
    if _remote_enabled():
        with connect() as db:
            row = db.execute(
                "SELECT metadata_json FROM source_documents WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown source ID: {source_id}")
            record = json.loads(row["metadata_json"])
            record.update(updates)
            db.execute(
                "UPDATE source_documents SET metadata_json = ?, extraction_key = ?, "
                "updated_at = NOW() WHERE source_id = ?",
                (json.dumps(record, ensure_ascii=False), record.get("extraction_key"), source_id),
            )
        return
    manifest = _manifest_path(source_dir)
    records = json.loads(manifest.read_text(encoding="utf-8"))
    for record in records:
        if record.get("source_id") == source_id:
            record.update(updates)
            break
    temporary = source_dir / ".sources.json.tmp"
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest)


def save_extraction(source_id: str, payload: dict, source_dir: Path = DEFAULT_SOURCE_DIR) -> str:
    """Persist extraction JSON to local disk or the configured private object bucket."""
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if _remote_enabled():
        key = f"extractions/{source_id}.json"
        get_object_storage(source_dir).upload(key, encoded, "application/json", upsert=True)
        _update_source(source_dir, source_id, {"extraction_key": key})
        return key
    extraction_dir = source_dir / "extractions"
    extraction_dir.mkdir(parents=True, exist_ok=True)
    path = extraction_dir / f"{source_id}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)
    return str(path.relative_to(source_dir))


def load_extraction(source_id: str, source_dir: Path = DEFAULT_SOURCE_DIR) -> dict | None:
    if _remote_enabled():
        records = [item for item in _remote_records() if item.get("source_id") == source_id]
        if not records or not records[0].get("extraction_key"):
            return None
        content = get_object_storage(source_dir).download(records[0]["extraction_key"])
        return json.loads(content.decode("utf-8"))
    path = source_dir / "extractions" / f"{source_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_extractions(source_dir: Path = DEFAULT_SOURCE_DIR) -> list[tuple[dict, dict]]:
    """Return source metadata and extraction payloads, newest source first."""
    results = []
    for source in list_sources(source_dir):
        payload = load_extraction(source["source_id"], source_dir)
        if payload is not None:
            results.append((source, payload))
    return results


def write_extraction(source_id: str, payload: dict, source_dir: Path = DEFAULT_SOURCE_DIR) -> None:
    save_extraction(source_id, payload, source_dir)
