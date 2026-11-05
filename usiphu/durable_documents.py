"""Durable JSON documents backed by private Supabase Storage and PostgreSQL metadata."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from usiphu.object_storage import get_object_storage
from usiphu.storage import connect


def remote_documents_enabled() -> bool:
    """Require both remote persistence backends before using durable cloud documents."""
    file_backend = os.getenv("USIPHU_FILE_STORAGE_BACKEND", "local").strip().lower()
    if file_backend != "supabase":
        return False
    database_backend = os.getenv("USIPHU_DATABASE_BACKEND", "sqlite").strip().lower()
    if database_backend not in {"postgres", "postgresql"}:
        raise RuntimeError(
            "Supabase document storage requires USIPHU_DATABASE_BACKEND=postgres."
        )
    return True


def _encode(payload: dict[str, Any]) -> bytes:
    if not isinstance(payload, dict):
        raise TypeError("Durable JSON documents must be JSON objects.")
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_json_document(
    document_key: str,
    local_path: Path,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read a JSON document from private Storage or its local development path."""
    if not document_key.strip():
        raise ValueError("A document key is required.")
    if not remote_documents_enabled():
        if not local_path.is_file():
            return dict(default or {})
        payload = json.loads(local_path.read_text(encoding="utf-8"))
    else:
        with connect() as db:
            row = db.execute(
                "SELECT object_key, content_sha256 FROM app_documents WHERE document_key = ?",
                (document_key,),
            ).fetchone()
        if row is None:
            return dict(default or {})
        encoded = get_object_storage(local_path.parent).download(row["object_key"])
        if hashlib.sha256(encoded).hexdigest() != row["content_sha256"]:
            raise RuntimeError(f"Stored document checksum mismatch: {document_key}")
        payload = json.loads(encoded.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Stored document is not a JSON object: {document_key}")
    return payload


def save_json_document(document_key: str, payload: dict[str, Any], local_path: Path) -> None:
    """Publish an immutable object then atomically update its PostgreSQL pointer."""
    if not document_key.strip():
        raise ValueError("A document key is required.")
    encoded = _encode(payload)
    if not remote_documents_enabled():
        local_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = local_path.with_suffix(local_path.suffix + ".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(local_path)
        return

    digest = hashlib.sha256(encoded).hexdigest()
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "-", Path(document_key).name) or "document.json"
    object_key = f"documents/{digest}/{safe_name}"
    storage = get_object_storage(local_path.parent)
    # Content-addressed keys leave the old DB pointer intact if the DB write fails.
    storage.upload(object_key, encoded, "application/json", upsert=True)
    with connect() as db:
        db.execute(
            "INSERT INTO app_documents (document_key, object_key, content_sha256) "
            "VALUES (?, ?, ?) ON CONFLICT (document_key) DO UPDATE SET "
            "object_key = EXCLUDED.object_key, content_sha256 = EXCLUDED.content_sha256, "
            "updated_at = NOW()",
            (document_key, object_key, digest),
        )
