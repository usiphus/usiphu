"""Local source inbox for examination papers awaiting extraction and review."""
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_SOURCE_DIR = Path(os.getenv(
    "USIPHU_SOURCE_DIR", Path(__file__).resolve().parent.parent / "data" / "source_inbox"
))
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg"}
MAX_FILE_BYTES = 50 * 1024 * 1024


def _manifest_path(source_dir: Path) -> Path:
    return source_dir / "sources.json"


def list_sources(source_dir: Path = DEFAULT_SOURCE_DIR) -> list[dict]:
    """Return the source inbox catalogue, newest first."""
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
    source_dir.mkdir(parents=True, exist_ok=True)
    records = list_sources(source_dir)
    if any(item.get("sha256") == digest for item in records):
        raise ValueError("This exact file is already in the source inbox")

    source_id = uuid.uuid4().hex
    stored_name = f"{source_id}{suffix}"
    destination = source_dir / stored_name
    temporary = source_dir / f".{stored_name}.tmp"
    temporary.write_bytes(content)
    temporary.replace(destination)

    clean_title = (title or Path(original_name).stem).strip()[:200]
    clean_specialty = specialty.strip()[:100] or "Unassigned"
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
    records.append(record)
    manifest = _manifest_path(source_dir)
    temp_manifest = source_dir / ".sources.json.tmp"
    temp_manifest.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_manifest.replace(manifest)
    return record
