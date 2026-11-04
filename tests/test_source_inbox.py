from pathlib import Path

import pytest

from usiphu.source_inbox import list_sources, save_source


def test_save_source_records_metadata_and_file(tmp_path: Path) -> None:
    record = save_source(
        "Urology Past Paper.PDF",
        b"%PDF-test",
        title="Urology past paper",
        specialty="Urology",
        exam_year="2024",
        notes="Collected paper; answers need checking.",
        source_dir=tmp_path,
    )

    assert record["status"] == "awaiting_extraction"
    assert record["question_count"] == 0
    assert (tmp_path / record["stored_filename"]).read_bytes() == b"%PDF-test"
    assert list_sources(tmp_path)[0]["source_id"] == record["source_id"]


def test_duplicate_source_is_rejected(tmp_path: Path) -> None:
    save_source("paper.pdf", b"same bytes", source_dir=tmp_path)
    with pytest.raises(ValueError, match="already"):
        save_source("renamed.pdf", b"same bytes", source_dir=tmp_path)


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("paper.exe", b"data", "Unsupported"),
        ("empty.pdf", b"", "empty"),
        ("large.pdf", b"x" * (50 * 1024 * 1024 + 1), "50 MB"),
    ],
)
def test_invalid_uploads_are_rejected(
    tmp_path: Path, filename: str, content: bytes, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        save_source(filename, content, source_dir=tmp_path)
