"""Private object storage adapters for Source Inbox documents.

The Supabase adapter uses the Storage HTTP API from the server only. Its secret key
must never be exposed to the browser or written to logs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class ObjectStorageError(RuntimeError):
    """Raised when a configured object-storage operation fails."""


class LocalObjectStorage:
    """Durable only within the local runtime; retained for development and tests."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if candidate != self.root.resolve() and self.root.resolve() not in candidate.parents:
            raise ValueError("Object key escapes the configured storage root")
        return candidate

    def upload(self, key: str, content: bytes, content_type: str, upsert: bool = False) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(content)
        temporary.replace(path)

    def download(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class SupabaseObjectStorage:
    """Private Supabase Storage access using a server-side secret key."""

    def __init__(
        self,
        *,
        project_url: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.project_url = (project_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.secret_key = (
            secret_key
            or os.getenv("SUPABASE_SECRET_KEY")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        )
        self.bucket = bucket or os.getenv("USIPHU_SUPABASE_STORAGE_BUCKET", "source-inbox")
        self.timeout = timeout
        if not self.project_url.startswith("https://"):
            raise RuntimeError("SUPABASE_URL must be an HTTPS project URL.")
        if not self.secret_key:
            raise RuntimeError(
                "Supabase Storage requires a server-side secret key (SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY)."
            )
        if not self.bucket or "/" in self.bucket:
            raise RuntimeError("USIPHU_SUPABASE_STORAGE_BUCKET must be a bucket name.")

    def _request(self, method: str, endpoint: str, *, body: bytes | None = None,
                 content_type: str | None = None, extra_headers: dict | None = None) -> bytes:
        headers = {"apikey": self.secret_key}
        # New sb_secret keys are opaque API keys, not JWTs. They must only be
        # sent as apikey; legacy service_role JWTs retain the Bearer header.
        if not self.secret_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.secret_key}"
        if content_type:
            headers["Content-Type"] = content_type
        headers.update(extra_headers or {})
        request = Request(
            f"{self.project_url}/storage/v1/{endpoint}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            status = getattr(exc, "code", "network")
            raise ObjectStorageError(
                f"Supabase Storage {method} failed ({status})."
            ) from exc

    def _object_path(self, key: str) -> str:
        parts = [part for part in key.split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            raise ValueError("Invalid object key")
        return "/".join(quote(part, safe="") for part in parts)

    def upload(self, key: str, content: bytes, content_type: str, upsert: bool = False) -> None:
        endpoint = f"object/{quote(self.bucket, safe='')}/{self._object_path(key)}"
        self._request(
            "POST",
            endpoint,
            body=content,
            content_type=content_type,
            extra_headers={"x-upsert": "true" if upsert else "false"},
        )

    def download(self, key: str) -> bytes:
        endpoint = (
            f"object/authenticated/{quote(self.bucket, safe='')}/"
            f"{self._object_path(key)}"
        )
        return self._request("GET", endpoint)

    def delete(self, key: str) -> None:
        endpoint = f"object/{quote(self.bucket, safe='')}"
        body = json.dumps({"prefixes": [key]}).encode("utf-8")
        self._request("DELETE", endpoint, body=body, content_type="application/json")

    def list_objects(self, prefix: str = "", limit: int = 1000, offset: int = 0) -> list[dict]:
        """List one Storage directory page using the authenticated server API."""
        if not 1 <= limit <= 1000 or offset < 0:
            raise ValueError("Storage listing limit must be 1-1000 and offset non-negative.")
        clean_prefix = prefix.strip("/")
        if clean_prefix and any(part in {".", ".."} for part in clean_prefix.split("/")):
            raise ValueError("Invalid Storage listing prefix.")
        body = json.dumps({
            "prefix": clean_prefix,
            "limit": limit,
            "offset": offset,
            "sortBy": {"column": "name", "order": "asc"},
        }).encode("utf-8")
        response = self._request(
            "POST",
            f"object/list/{quote(self.bucket, safe='')}",
            body=body,
            content_type="application/json",
        )
        payload = json.loads(response.decode("utf-8"))
        if not isinstance(payload, list):
            raise ObjectStorageError("Supabase Storage returned an invalid object listing.")
        return payload

    def create_signed_download_url(self, key: str, expires_in: int = 300) -> str:
        if not 1 <= expires_in <= 3600:
            raise ValueError("Signed download URLs must expire within one hour.")
        endpoint = (
            f"object/sign/{quote(self.bucket, safe='')}/"
            f"{self._object_path(key)}"
        )
        body = json.dumps({"expiresIn": expires_in}).encode("utf-8")
        response = self._request(
            "POST", endpoint, body=body, content_type="application/json"
        )
        payload = json.loads(response.decode("utf-8"))
        signed_path = payload.get("signedURL") or payload.get("signedUrl")
        if not signed_path:
            raise ObjectStorageError("Supabase did not return a signed download URL.")
        if signed_path.startswith("https://"):
            return signed_path
        if signed_path.startswith("/storage/v1/"):
            return f"{self.project_url}{signed_path}"
        if signed_path.startswith("/"):
            return f"{self.project_url}/storage/v1{signed_path}"
        return f"{self.project_url}/storage/v1/{signed_path}"


def get_object_storage(root: Path) -> LocalObjectStorage | SupabaseObjectStorage:
    backend = os.getenv("USIPHU_FILE_STORAGE_BACKEND", "local").strip().lower()
    if backend == "local":
        return LocalObjectStorage(root)
    if backend == "supabase":
        return SupabaseObjectStorage()
    raise RuntimeError(
        f"Unsupported USIPHU_FILE_STORAGE_BACKEND={backend!r}; choose 'local' or 'supabase'."
    )
