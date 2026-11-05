"""Tests for local and private Supabase object-storage adapters."""
from __future__ import annotations

from pathlib import Path

import pytest

from usiphu.object_storage import (
    LocalObjectStorage,
    SupabaseObjectStorage,
    get_object_storage,
)


def test_local_object_storage_round_trip_and_delete(tmp_path: Path):
    store = LocalObjectStorage(tmp_path)
    store.upload("sources/abc/paper.txt", b"paper", "text/plain")
    assert store.download("sources/abc/paper.txt") == b"paper"
    store.delete("sources/abc/paper.txt")
    with pytest.raises(FileNotFoundError):
        store.download("sources/abc/paper.txt")


def test_local_object_storage_rejects_path_traversal(tmp_path: Path):
    store = LocalObjectStorage(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        store.upload("../outside.txt", b"no", "text/plain")


def test_supabase_storage_requires_https_and_server_secret(monkeypatch):
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="HTTPS"):
        SupabaseObjectStorage(project_url="http://example.supabase.co", secret_key="x")
    with pytest.raises(RuntimeError, match="secret key"):
        SupabaseObjectStorage(project_url="https://example.supabase.co", secret_key="")


def test_supabase_upload_uses_authenticated_private_storage_request(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"Key":"source-inbox/sources/abc/paper.txt"}'

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.method
        seen["authorization"] = request.get_header("Authorization")
        seen["api_key"] = request.get_header("Apikey")
        seen["upsert"] = request.get_header("X-upsert")
        seen["body"] = request.data
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr("usiphu.object_storage.urlopen", fake_urlopen)
    store = SupabaseObjectStorage(
        project_url="https://example.supabase.co",
        secret_key="sb_secret_server-only-secret",
        bucket="source-inbox",
    )
    store.upload("sources/abc/paper.txt", b"paper", "text/plain")
    assert seen["url"] == (
        "https://example.supabase.co/storage/v1/object/source-inbox/sources/abc/paper.txt"
    )
    assert seen["method"] == "POST"
    assert seen["authorization"] is None
    assert seen["api_key"] == "sb_secret_server-only-secret"
    assert seen["upsert"] == "false"
    assert seen["body"] == b"paper"


def test_supabase_download_uses_authenticated_private_endpoint(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b"private paper"

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["api_key"] = request.get_header("Apikey")
        return Response()

    monkeypatch.setattr("usiphu.object_storage.urlopen", fake_urlopen)
    store = SupabaseObjectStorage(
        project_url="https://example.supabase.co",
        secret_key="sb_secret_server-only-secret",
    )
    assert store.download("sources/abc/paper.txt") == b"private paper"
    assert "/object/authenticated/source-inbox/" in seen["url"]
    assert seen["authorization"] is None
    assert seen["api_key"] == "sb_secret_server-only-secret"


def test_signed_url_is_short_lived_and_validated(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"signedURL":"/storage/v1/object/sign/source-inbox/sources/a/file?token=x"}'

    monkeypatch.setattr("usiphu.object_storage.urlopen", lambda *_args, **_kwargs: Response())
    store = SupabaseObjectStorage(
        project_url="https://example.supabase.co",
        secret_key="sb_secret_server-only-secret",
    )
    url = store.create_signed_download_url("sources/a/file", expires_in=300)
    assert url.startswith("https://example.supabase.co/storage/v1/object/sign/")
    with pytest.raises(ValueError, match="one hour"):
        store.create_signed_download_url("sources/a/file", expires_in=7200)


def test_file_backend_selection_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("USIPHU_FILE_STORAGE_BACKEND", "mystery")
    with pytest.raises(RuntimeError, match="Unsupported"):
        get_object_storage(tmp_path)
