"""Shared safety helpers for encrypted Supabase backup and restore commands."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


def write_pg_service_file(database_url: str, path: Path, service: str) -> Path:
    """Write libpq connection settings to a mode-0600 temporary service file."""
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname or not parsed.path.strip("/"):
        raise ValueError("SUPABASE_DB_URL must be a valid PostgreSQL connection URL.")
    query = parse_qs(parsed.query)
    sslmode = query.get("sslmode", ["require"])[0]
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("Backup connections must use TLS with sslmode=require or stronger.")
    values = {
        "host": parsed.hostname,
        "port": str(parsed.port or 5432),
        "dbname": unquote(parsed.path.lstrip("/")),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "sslmode": sslmode,
    }
    if not values["user"] or not values["password"]:
        raise ValueError("The PostgreSQL connection URL must include a username and password.")
    for key, value in values.items():
        if "\n" in value or "\r" in value:
            raise ValueError("Invalid newline in PostgreSQL connection settings.")
    def quote_value(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    path.write_text(
        f"[{service}]\n" + "".join(
            f"{key}={quote_value(value)}\n" for key, value in values.items()
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def safe_object_key(key: str) -> str:
    """Validate a Storage key before mapping it to a local backup path."""
    if not key or key.startswith("/") or "\\" in key:
        raise ValueError("Unsafe Storage object key.")
    parts = key.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Unsafe Storage object key.")
    return "/".join(parts)


def list_storage_object_keys(storage) -> list[str]:
    """Recursively list all object keys in one bucket, handling paginated folders."""
    found: set[str] = set()
    visited: set[str] = set()

    def walk(prefix: str) -> None:
        if prefix in visited:
            return
        visited.add(prefix)
        offset = 0
        while True:
            entries = storage.list_objects(prefix, limit=1000, offset=offset)
            for entry in entries:
                name = str(entry.get("name") or "")
                if not name or "/" in name or name in {".", ".."}:
                    raise ValueError(f"Invalid name in Storage listing under {prefix!r}.")
                key = safe_object_key(f"{prefix}/{name}" if prefix else name)
                if entry.get("id") is None and not entry.get("metadata"):
                    walk(key)
                else:
                    found.add(key)
            if len(entries) < 1000:
                break
            offset += len(entries)

    walk("")
    return sorted(found)


def validate_archive_member(name: str) -> str:
    """Reject archive paths that could escape the restore staging directory."""
    normalized = name.replace("\\", "/").rstrip("/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError("Backup archive contains an absolute path.")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Backup archive contains an unsafe path.")
    return normalized
