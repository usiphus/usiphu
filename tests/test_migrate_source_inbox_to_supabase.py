import json
from pathlib import Path

import pytest

from scripts.migrate_source_inbox_to_supabase import inventory, migrate
from usiphu.source_inbox import save_source


def test_source_inbox_migration_is_non_destructive_by_default(tmp_path: Path):
    source_dir = tmp_path / "source_inbox"
    record = save_source(
        "legacy-paper.txt",
        b"1) What is the diagnosis?\nA) Option one\nB) Option two\n",
        title="Legacy paper",
        specialty="Urology",
        source_dir=source_dir,
    )
    extraction_dir = source_dir / "extractions"
    extraction_dir.mkdir()
    extraction = {
        "source_id": record["source_id"],
        "mcq_candidates": [{"candidate_id": "legacy-q-1"}],
    }
    (extraction_dir / f"{record['source_id']}.json").write_text(
        json.dumps(extraction), encoding="utf-8"
    )

    result = migrate(source_dir)

    assert result["mode"] == "dry_run"
    assert result["completed"] is True
    assert result["source_count"] == 1
    assert result["extraction_count"] == 1
    assert result["sources"][0]["status"] == "would_import"
    assert (source_dir / record["stored_filename"]).is_file()
    assert (source_dir / "sources.json").is_file()


def test_source_inbox_inventory_rejects_checksum_mismatch(tmp_path: Path):
    source_dir = tmp_path / "source_inbox"
    record = save_source("legacy-paper.txt", b"original", source_dir=source_dir)
    (source_dir / record["stored_filename"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        inventory(source_dir)
