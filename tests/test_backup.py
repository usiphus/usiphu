import hashlib
import importlib.util
import json
import sqlite3
import tarfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_sqlite.py"
SPEC = importlib.util.spec_from_file_location("backup_sqlite", SCRIPT)
backup = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(backup)


def test_backup_contains_database_and_complete_source_inbox(tmp_path, monkeypatch):
    database = tmp_path / "app.sqlite3"
    source_dir = tmp_path / "source-inbox"
    extraction_dir = source_dir / "extractions"
    extraction_dir.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE learners (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO learners(name) VALUES ('test learner')")

    original_pdf = source_dir / "paper.pdf"
    original_pdf.write_bytes(b"%PDF original paper")
    manifest = source_dir / "sources.json"
    manifest.write_text(json.dumps([{"stored_filename": "paper.pdf"}]), encoding="utf-8")
    extraction = extraction_dir / "candidate.json"
    extraction.write_text('{"candidate_id": "q-1"}', encoding="utf-8")

    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(backup, "source", database)
    monkeypatch.setattr(backup, "source_dir", source_dir)
    monkeypatch.setattr(backup, "backup_dir", backup_dir)
    monkeypatch.setattr(backup, "retention_days", 30)

    backup.main()

    database_backups = list(backup_dir.glob("usiphu-*.sqlite3"))
    source_archives = list(backup_dir.glob("usiphu-sources-*.tar.gz"))
    assert len(database_backups) == 1
    assert len(source_archives) == 1

    with sqlite3.connect(database_backups[0]) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT name FROM learners").fetchone()[0] == "test learner"

    archive_path = source_archives[0]
    checksum_path = Path(f"{archive_path}.sha256")
    expected_hash = checksum_path.read_text(encoding="ascii").split()[0]
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == expected_hash
    with tarfile.open(archive_path, "r:gz") as archive:
        assert archive.extractfile("source_inbox/paper.pdf").read() == b"%PDF original paper"
        assert archive.extractfile("source_inbox/sources.json").read() == manifest.read_bytes()
        assert archive.extractfile("source_inbox/extractions/candidate.json").read() == extraction.read_bytes()
