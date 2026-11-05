from pathlib import Path

import pytest

from usiphu.backup_tools import (
    list_storage_object_keys,
    safe_object_key,
    validate_archive_member,
    write_pg_service_file,
)


def test_storage_listing_walks_nested_directories_and_sorts_keys():
    class FakeStorage:
        def list_objects(self, prefix, limit, offset):
            entries = {
                "": [{"name": "documents", "id": None, "metadata": None},
                     {"name": "sources", "id": None, "metadata": None}],
                "documents": [{"name": "bank.json", "id": "obj-1", "metadata": {"size": 12}}],
                "sources": [{"name": "abc", "id": None, "metadata": None}],
                "sources/abc": [{"name": "paper.pdf", "id": "obj-2", "metadata": {"size": 20}}],
            }
            return entries.get(prefix, [])

    assert list_storage_object_keys(FakeStorage()) == [
        "documents/bank.json",
        "sources/abc/paper.pdf",
    ]


@pytest.mark.parametrize("key", ["../escape", "/absolute", "a//b", "a/./b", "a/../b", "a\\b"])
def test_safe_object_key_rejects_unsafe_paths(key):
    with pytest.raises(ValueError, match="Unsafe"):
        safe_object_key(key)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/windows", "root/../../escape"])
def test_archive_member_validation_rejects_path_traversal(name):
    with pytest.raises(ValueError, match="path"):
        validate_archive_member(name)


def test_pg_service_file_is_private_and_does_not_require_credentials_in_arguments(tmp_path: Path):
    path = write_pg_service_file(
        "postgresql://backup-user:very-secret@db.example.supabase.co:5432/postgres?sslmode=require",
        tmp_path / "pg_service.conf",
        "usiphu_backup",
    )
    assert path.stat().st_mode & 0o777 == 0o600
    content = path.read_text(encoding="utf-8")
    assert "[usiphu_backup]" in content
    assert "host=db.example.supabase.co" in content
    assert "password=very-secret" in content
    assert "sslmode=require" in content
