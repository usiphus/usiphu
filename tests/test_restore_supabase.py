import io
import tarfile

from pathlib import Path

import pytest

from scripts.restore_supabase import safe_extract_archive


def test_restore_archive_rejects_path_traversal(tmp_path: Path):
    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        payload = b"bad"
        info = tarfile.TarInfo("../outside.txt")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    with pytest.raises(ValueError, match="unsafe path"):
        safe_extract_archive(archive_path, tmp_path / "restore")


def test_restore_archive_rejects_symlinks(tmp_path: Path):
    archive_path = tmp_path / "link.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("usiphu-backup/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        archive.addfile(info)

    with pytest.raises(ValueError, match="Unsupported entry"):
        safe_extract_archive(archive_path, tmp_path / "restore")


def test_restore_manifest_rejects_database_dump_path_traversal(tmp_path: Path):
    import hashlib
    import json

    from scripts.restore_supabase import verify_backup

    root = tmp_path / "usiphu-backup"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps({
            "format_version": 1,
            "database_dump": {
                "file": "../outside.dump",
                "bytes": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            },
            "objects": [],
        }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsafe path"):
        verify_backup(root)
