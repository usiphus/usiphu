import json
from pathlib import Path

from scripts.migrate_durable_documents import migrate


def test_durable_document_migration_defaults_to_non_destructive_dry_run(tmp_path: Path):
    data_root = tmp_path / "data"
    bank = data_root / "question_banks" / "past_papers_reviewed.json"
    report = data_root / "source_inbox" / "reports" / "pilot-validation" / "latest.json"
    bank.parent.mkdir(parents=True)
    report.parent.mkdir(parents=True)
    bank.write_text(json.dumps({"questions": [{"id": "q-1"}]}), encoding="utf-8")
    report.write_text(json.dumps({"totals": {"mcq_candidates": 1}}), encoding="utf-8")

    result = migrate(data_root)

    assert result["mode"] == "dry_run"
    assert result["completed"] is True
    assert result["source_files"] == 2
    assert {item["status"] for item in result["documents"]} == {"would_import"}
    assert bank.is_file()
    assert report.is_file()
    assert not (data_root / "backups").exists()
