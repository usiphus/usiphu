"""Source Inbox persistence: local files in development, private Supabase Storage in hosted mode."""
import hashlib
import json
import mimetypes
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx

from usiphu.database import is_postgres
from usiphu.storage import DEFAULT_DB, connect, initialize

DEFAULT_SOURCE_DIR = Path(os.getenv(
    "USIPHU_SOURCE_DIR", Path(__file__).resolve().parent.parent / "data" / "source_inbox"
))
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg"}
MAX_FILE_BYTES = 50 * 1024 * 1024
DEFAULT_BUCKET = "usiphu-source-inbox"


def _manifest_path(source_dir: Path) -> Path:
    return source_dir / "sources.json"


def _storage_settings() -> tuple[str, str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    bucket = os.getenv("USIPHU_STORAGE_BUCKET", DEFAULT_BUCKET)
    if not url or not key:
        raise RuntimeError(
            "Hosted source storage needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Streamlit Secrets."
        )
    return url, key, bucket


def _storage_headers(key: str) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def _upload_object(object_key: str, content: bytes, filename: str) -> None:
    url, key, bucket = _storage_settings()
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    response = httpx.post(
        f"{url}/storage/v1/object/{bucket}/{quote(object_key, safe='/')}",
        headers={**_storage_headers(key), "x-upsert": "true", "Content-Type": mime},
        content=content, timeout=60.0,
    )
    response.raise_for_status()


def _download_object(object_key: str) -> bytes:
    url, key, bucket = _storage_settings()
    response = httpx.get(
        f"{url}/storage/v1/object/{bucket}/{quote(object_key, safe='/')}",
        headers=_storage_headers(key), timeout=60.0,
    )
    response.raise_for_status()
    return response.content


def _delete_object(object_key: str) -> None:
    url, key, bucket = _storage_settings()
    response = httpx.delete(
        f"{url}/storage/v1/object/{bucket}",
        headers={**_storage_headers(key), "Content-Type": "application/json"},
        json={"prefixes": [object_key]}, timeout=30.0,
    )
    response.raise_for_status()


def list_sources(source_dir: Path = DEFAULT_SOURCE_DIR) -> list[dict]:
    """Return the source catalogue, newest first."""
    if is_postgres():
        initialize(DEFAULT_DB)
        with connect(DEFAULT_DB) as db:
            rows = db.execute(
                "SELECT metadata_json FROM source_documents ORDER BY uploaded_at DESC, source_id"
            ).fetchall()
        return [json.loads(row["metadata_json"]) for row in rows]
    manifest = _manifest_path(source_dir)
    if not manifest.exists():
        return []
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return sorted(payload, key=lambda item: item.get("uploaded_at", ""), reverse=True)


def get_source_record(source_id: str, source_dir: Path = DEFAULT_SOURCE_DIR) -> dict | None:
    return next((item for item in list_sources(source_dir) if item.get("source_id") == source_id), None)


def get_source_bytes(source_id: str, source_dir: Path = DEFAULT_SOURCE_DIR) -> bytes:
    """Read an original source file from private Storage or the local development directory."""
    record = get_source_record(source_id, source_dir)
    if record is None:
        raise FileNotFoundError(f"Unknown source ID: {source_id}")
    if is_postgres():
        return _download_object(record["object_key"])
    path = source_dir / record["stored_filename"]
    if not path.is_file():
        raise FileNotFoundError(f"Stored source file is missing: {record['original_filename']}")
    return path.read_bytes()


def save_source(
    filename: str, content: bytes, *, title: str | None = None,
    specialty: str = "Unassigned", exam_year: str = "", notes: str = "",
    source_dir: Path = DEFAULT_SOURCE_DIR,
) -> dict:
    """Store a source document and provenance metadata; cloud files use a private bucket."""
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
        "source_id": source_id, "original_filename": original_name[:255],
        "stored_filename": stored_name, "title": clean_title, "specialty": clean_specialty,
        "exam_year": exam_year.strip()[:20], "notes": notes.strip()[:2000],
        "size_bytes": len(content), "sha256": digest,
        "uploaded_at": datetime.now(UTC).isoformat(), "status": "awaiting_extraction",
        "question_count": 0,
    }
    if is_postgres():
        initialize(DEFAULT_DB)
        with connect(DEFAULT_DB) as db:
            existing = db.execute(
                "SELECT source_id FROM source_documents WHERE sha256=?", (digest,)
            ).fetchone()
        if existing:
            raise ValueError("This exact file is already in the source inbox")
        object_key = f"{source_id}/{stored_name}"
        record["object_key"] = object_key
        _upload_object(object_key, content, original_name)
        try:
            with connect(DEFAULT_DB) as db:
                inserted = db.execute(
                    """INSERT INTO source_documents(source_id,sha256,object_key,metadata_json,uploaded_at)
                       VALUES(?,?,?,?,?) ON CONFLICT(sha256) DO NOTHING RETURNING source_id""",
                    (source_id, digest, object_key, json.dumps(record, ensure_ascii=False), record["uploaded_at"]),
                ).fetchone()
            if not inserted:
                raise ValueError("This exact file is already in the source inbox")
        except Exception:
            try:
                _delete_object(object_key)
            except httpx.HTTPError:
                pass
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


def update_source_metadata(source_id: str, updates: dict, source_dir: Path = DEFAULT_SOURCE_DIR) -> dict:
    """Update source status/provenance without rewriting the original file."""
    if is_postgres():
        initialize(DEFAULT_DB)
        with connect(DEFAULT_DB) as db:
            row = db.execute(
                "SELECT metadata_json FROM source_documents WHERE source_id=? FOR UPDATE", (source_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown source ID: {source_id}")
            record = json.loads(row["metadata_json"])
            record.update(updates)
            db.execute(
                "UPDATE source_documents SET metadata_json=? WHERE source_id=?",
                (json.dumps(record, ensure_ascii=False), source_id),
            )
        return record
    manifest = _manifest_path(source_dir)
    records = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    for record in records:
        if record.get("source_id") == source_id:
            record.update(updates)
            break
    else:
        raise KeyError(f"Unknown source ID: {source_id}")
    temporary = source_dir / ".sources.json.tmp"
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest)
    return record


def save_extraction(source_id: str, payload: dict, source_dir: Path = DEFAULT_SOURCE_DIR) -> None:
    """Persist extraction candidates in Postgres or the local JSON workspace."""
    if is_postgres():
        initialize(DEFAULT_DB)
        with connect(DEFAULT_DB) as db:
            db.execute(
                """INSERT INTO source_extractions(source_id,payload_json,updated_at)
                   VALUES(?,?,now()) ON CONFLICT(source_id) DO UPDATE SET
                   payload_json=excluded.payload_json, updated_at=now()""",
                (source_id, json.dumps(payload, ensure_ascii=False)),
            )
        return
    extraction_dir = source_dir / "extractions"
    extraction_dir.mkdir(parents=True, exist_ok=True)
    path = extraction_dir / f"{source_id}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_extraction(source_id: str, source_dir: Path = DEFAULT_SOURCE_DIR) -> dict | None:
    if is_postgres():
        initialize(DEFAULT_DB)
        with connect(DEFAULT_DB) as db:
            row = db.execute(
                "SELECT payload_json FROM source_extractions WHERE source_id=?", (source_id,)
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None
    path = source_dir / "extractions" / f"{source_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_extractions(source_dir: Path = DEFAULT_SOURCE_DIR) -> list[dict]:
    if is_postgres():
        return [payload for source in list_sources(source_dir)
                if (payload := load_extraction(source["source_id"], source_dir)) is not None]
    extraction_dir = source_dir / "extractions"
    if not extraction_dir.is_dir():
        return []
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(extraction_dir.glob("*.json"), key=lambda item: item.stat().st_mtime)]
