import hashlib
import io
import importlib.util
import json
import sqlite3
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


migration = load_script("migrate_source_inbox", "migrate_source_inbox.py")
restore = load_script("restore_backup", "restore_backup.py")


def test_source_migration_is_verified_resumable_and_preserves_original(tmp_path):
    source = tmp_path / "old-source-inbox"
    (source / "extractions").mkdir(parents=True)
    (source / "paper.pdf").write_bytes(b"original paper")
    (source / "sources.json").write_text('[{"source_id":"abc"}]', encoding="utf-8")
    (source / "extractions" / "questions.json").write_text('{"questions":[]}', encoding="utf-8")
    destination = tmp_path / "persistent-volume"
    destination.mkdir()

    copied, skipped = migration.migrate(source, destination, dry_run=True)
    assert (copied, skipped) == (3, 0)
    assert list(destination.iterdir()) == []

    copied, skipped = migration.migrate(source, destination)
    assert (copied, skipped) == (3, 0)
    assert (destination / "paper.pdf").read_bytes() == b"original paper"
    assert (source / "paper.pdf").read_bytes() == b"original paper"

    copied, skipped = migration.migrate(source, destination)
    assert (copied, skipped) == (0, 3)


def test_source_migration_refuses_conflicting_destination_file(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "paper.pdf").write_bytes(b"correct original")
    (destination / "paper.pdf").write_bytes(b"different contents")

    try:
        migration.migrate(source, destination)
    except ValueError as error:
        assert "differs from source" in str(error)
    else:
        raise AssertionError("Conflicting destination should be rejected")


def test_source_migration_rejects_symlinks(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    (source / "linked.txt").symlink_to(target)

    try:
        migration.migrate(source, destination)
    except ValueError as error:
        assert "Symlinks" in str(error)
    else:
        raise AssertionError("Symlink should be rejected")


def make_backup_pair(tmp_path: Path) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    database = tmp_path / "backup.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE learners (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO learners(name) VALUES ('restore-drill-user')")
    source_dir = tmp_path / "source-inbox"
    (source_dir / "extractions").mkdir(parents=True)
    (source_dir / "paper.pdf").write_bytes(b"%PDF test paper")
    (source_dir / "sources.json").write_text(
        json.dumps([{"stored_filename": "paper.pdf"}]), encoding="utf-8"
    )
    (source_dir / "extractions" / "candidate.json").write_text(
        '{"candidate_id":"candidate-1"}', encoding="utf-8"
    )
    archive = tmp_path / "sources.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        output.add(source_dir, arcname="source_inbox")
    checksum = tmp_path / "sources.tar.gz.sha256"
    checksum.write_text(
        f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n",
        encoding="ascii",
    )
    return database, archive, checksum


def test_restore_round_trip_restores_database_and_all_source_files(tmp_path):
    database_backup, source_archive, checksum = make_backup_pair(tmp_path)
    restored_database = tmp_path / "restore" / "usiphu.sqlite3"
    restored_sources = tmp_path / "restore" / "source-inbox"

    restore.restore(
        database_backup, source_archive, checksum, restored_database, restored_sources
    )

    with sqlite3.connect(restored_database) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT name FROM learners").fetchone()[0] == "restore-drill-user"
    assert (restored_sources / "paper.pdf").read_bytes() == b"%PDF test paper"
    assert json.loads((restored_sources / "sources.json").read_text(encoding="utf-8"))[0][
        "stored_filename"
    ] == "paper.pdf"
    assert (restored_sources / "extractions" / "candidate.json").exists()


def test_restore_rejects_tampered_archive_and_nonempty_source_target(tmp_path):
    database_backup, source_archive, checksum = make_backup_pair(tmp_path)
    source_archive.write_bytes(source_archive.read_bytes() + b"tamper")
    try:
        restore.restore(
            database_backup,
            source_archive,
            checksum,
            tmp_path / "db.sqlite3",
            tmp_path / "source-inbox",
        )
    except ValueError as error:
        assert "SHA-256" in str(error)
    else:
        raise AssertionError("Tampered source archive should be rejected")

    database_backup, source_archive, checksum = make_backup_pair(tmp_path / "second")
    source_target = tmp_path / "occupied"
    source_target.mkdir()
    (source_target / "keep.txt").write_text("do not overwrite", encoding="utf-8")
    try:
        restore.restore(
            database_backup,
            source_archive,
            checksum,
            tmp_path / "second" / "restored.sqlite3",
            source_target,
        )
    except ValueError as error:
        assert "non-empty" in str(error)
    else:
        raise AssertionError("Non-empty source target should be rejected")


def test_restore_rejects_path_traversal_even_with_valid_checksum(tmp_path):
    database_backup = tmp_path / "valid.sqlite3"
    with sqlite3.connect(database_backup) as connection:
        connection.execute("CREATE TABLE safe (id INTEGER)")
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        import tarfile as tf

        payload = b"do not write outside"
        member = tf.TarInfo("source_inbox/../../escaped.txt")
        member.size = len(payload)
        output.addfile(member, io.BytesIO(payload))
    checksum = tmp_path / "unsafe.sha256"
    checksum.write_text(
        f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n",
        encoding="ascii",
    )
    try:
        restore.restore(
            database_backup,
            archive,
            checksum,
            tmp_path / "restore" / "restored.sqlite3",
            tmp_path / "restore" / "source-inbox",
        )
    except ValueError as error:
        assert "Unsafe archive path" in str(error)
    else:
        raise AssertionError("Path traversal archive should be rejected")
    assert not (tmp_path / "escaped.txt").exists()
