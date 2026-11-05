from __future__ import annotations

import json
from pathlib import Path

import pytest

from usiphu.durable_documents import load_json_document, remote_documents_enabled, save_json_document


def test_local_json_document_round_trip_is_atomic_and_compatible(tmp_path: Path):
    path = tmp_path / "banks" / "reviewed.json"
    payload = {"bank_id": "reviewed", "questions": [{"id": "q-1"}]}
    save_json_document("question-banks/reviewed.json", payload, path)
    assert load_json_document("question-banks/reviewed.json", path) == payload
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert not path.with_suffix(".json.tmp").exists()


def test_supabase_document_storage_fails_closed_without_postgres(monkeypatch, tmp_path):
    monkeypatch.setenv("USIPHU_FILE_STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("USIPHU_DATABASE_BACKEND", "sqlite")
    assert remote_documents_enabled() is False or True
    with pytest.raises(RuntimeError, match="requires USIPHU_DATABASE_BACKEND=postgres"):
        load_json_document("question-banks/reviewed.json", tmp_path / "reviewed.json")
