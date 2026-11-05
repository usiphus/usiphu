"""Durable JSON documents backed by private object storage and PostgreSQL metadata."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

from usiphu.object_storage import get_object_storage
from usiphu.storage import connect


def remote_documents_enabled() -> bool:
    """Return whether durable JSON documents must use PostgreSQL + private Storage."""
    backend = os.getenv("USIPHU_FILE_STORAGE_BACKEND", "local").strip().lower()
    if backend != "supabase":
        return False
    database = os.getenv("USIPHU_DATABASE_BACKEND", "sqlite").strip().lower()
    if database not in {"postgres", "postgresql"}:
        raise RuntimeError("Supabase document storage requires USIPHU_DATABASE_BACKEND=postgres.")
    return True


def _encode(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_json_document(
    document_key: str,
    local_path: Path,
    default: dict | None = None,
) -> dict:
    """Read a JSON document from private Storage or its local development path."""
    if not remote_documents_enabled():
        if not local_path.is_file():
            return dict(default or {})
        return json.loads(local_path.read_text(encoding="utf-8"))

    with connect() as db:
        row = db.execute(
            "SELECT object_key, content_sha256 FROM app_documents WHERE document_key = ?",
            (document_key,),
        ).fetchone()
    if row is None:
        return dict(default or {})
    encoded = get_object_storage(local_path.parent).download(row["object_key"])
    digest = hashlib.sha256(encoded).hexdigest()
    if digest != row["content_sha256"]:
        raise RuntimeError(f"Stored document checksum mismatch: {document_key}")
    payload = json.loads(encoded.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Stored document is not a JSON object: {document_key}")
    return payload


def save_json_document(document_key: str, payload: dict, local_path: Path) -> None:
    """Save locally or publish an immutable object then atomically update its DB pointer."""
    encoded = _encode(payload)
    if not remote_documents_enabled():
        local_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = local_path.with_suffix(local_path.suffix + ".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(local_path)
        return

    digest = hashlib.sha256(encoded).hexdigest()
    filename = re.sub(r"[^a-zA-Z0-9._-]", "-", Path(document_key).name) or "document.json"
    object_key = f"documents/{digest}/{filename}"
    storage = get_object_storage(local_path.parent)
    # Content-addressed object keys keep the old DB pointer valid if the DB write fails.
    storage.upload(object_key, encoded, "application/json", upsert=True)
    with connect() as db:
        db.execute(
            "INSERT INTO app_documents (document_key, object_key, content_sha256) "
            "VALUES (?, ?, ?) ON CONFLICT (document_key) DO UPDATE SET "
            "object_key = EXCLUDED.object_key, content_sha256 = EXCLUDED.content_sha256, "
            "updated_at = NOW()",
            (document_key, object_key, digest),
        )


def json_document_exists(document_key: str) -> bool:
    """Return whether a durable document pointer exists in the configured backend."""
    if not remote_documents_enabled():
        return False
    with connect() as db:
        row = db.execute(
            "SELECT 1 AS present FROM app_documents WHERE document_key = ?",
            (document_key,),
        ).fetchone()
    return row is not None
