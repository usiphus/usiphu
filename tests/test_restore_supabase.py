import io
from pathlib import Path
import tarfile

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
