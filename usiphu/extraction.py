"""Extract question candidates from uploaded source documents without inventing answers."""
import io
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

from usiphu.source_inbox import (
    DEFAULT_SOURCE_DIR,
    get_source_bytes,
    list_sources,
    load_extraction,
    save_extraction,
    update_source_metadata,
)

QUESTION_START = re.compile(r"^\s*(\d{1,3})[).]\s+\S", re.M)
OPTION_LINE = re.compile(r"^\s*([A-E])[.)]\s*(.+?)\s*$", re.M)
QUESTION_CUE = re.compile(
    r"\?|\b(which|what|when|where|why|how|name|mention|define|describe|"
    r"classify|enumerate|discuss|outline|state|list|diagnos|management|"
    r"investigation|treatment|complication|cause|most common|next step)\b",
    re.I,
)
FOOTER = re.compile(r"Back to index|Model Answer|Collage TBL|Manual - MEQ Book", re.I)


def _document_pages(filename: str, content: bytes) -> list[str]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        return [page.extract_text() or "" for page in reader.pages]
    if suffix == ".txt":
        return [content.decode("utf-8-sig", errors="replace")]
    if suffix == ".docx":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in root.findall(".//w:p", ns):
            paragraphs.append("".join(node.text or "" for node in paragraph.findall(".//w:t", ns)))
        return ["\n".join(paragraphs)]
    raise ValueError("Automatic text extraction supports PDF, DOCX and TXT. This file needs manual extraction or OCR.")


def parse_question_text(pages: list[str], source: dict) -> dict:
    """Create page-cited draft candidates; answer keys are deliberately left empty."""
    lines = []
    meq_pages = []
    meq_page_numbers = set()
    for page_number, page_text in enumerate(pages, start=1):
        if re.search(r"\bMEQ\s*\d*|modified essay question", page_text, re.I):
            meq_page_numbers.add(page_number)
            cleaned = [line.rstrip() for line in page_text.splitlines()
                       if line.strip() and not FOOTER.search(line)]
            if cleaned:
                meq_pages.append({
                    "candidate_id": f"{source['source_id']}-meq-{len(meq_pages) + 1:03d}",
                    "source_page": page_number,
                    "source_page_end": page_number,
                    "question_type": "modified_essay_question",
                    "raw_text": "\n".join(cleaned).strip(),
                    "extraction_status": "transcribed_needs_human_review",
                    "answer_status": "not_extracted_or_verified",
                })
        for line in page_text.splitlines():
            lines.append((page_number, line.rstrip()))

    starts = [index for index, (_, line) in enumerate(lines)
              if QUESTION_START.match(line)]
    candidates = []
    for start_index, line_index in enumerate(starts):
        stop_index = starts[start_index + 1] if start_index + 1 < len(starts) else len(lines)
        block = lines[line_index:stop_index]
        if block[0][0] in meq_page_numbers:
            continue
        raw_lines = [line for _, line in block if line.strip() and not FOOTER.search(line)]
        raw_text = "\n".join(raw_lines).strip()
        if not raw_text:
            continue
        # Do not treat MEQ sub-questions as MCQs unless they contain actual option lines.
        options = [
            {"id": match.group(1).lower(), "text": match.group(2).strip()}
            for match in OPTION_LINE.finditer(raw_text)
        ]
        first_line = raw_lines[0].strip()
        number_match = re.match(r"^(\d{1,3})[).]", first_line)
        if not number_match:
            continue
        if len(options) < 2 and not QUESTION_CUE.search(raw_text):
            continue
        source_pages = [page for page, line in block if line.strip()]
        ordinal = len(candidates) + 1
        candidates.append({
            "candidate_id": f"{source['source_id']}-q-{ordinal:04d}",
            "source_page": source_pages[0],
            "source_page_end": source_pages[-1],
            "question_number_in_source": int(number_match.group(1)),
            "question_type": "single_best_answer" if len(options) >= 2 else "short_answer_candidate",
            "stem_extracted": raw_text,
            "options": options,
            "correct_option_id": None,
            "explanation": None,
            "raw_text": raw_text,
            "extraction_status": "transcribed_needs_human_review",
            "answer_status": "not_extracted_or_verified",
        })

    return {
        "schema_version": "1.0",
        "source_id": source["source_id"],
        "source_title": source["title"],
        "source_filename": source["original_filename"],
        "source_sha256": source["sha256"],
        "specialty": source.get("specialty", "Unassigned"),
        "extraction_method": "PDF/DOCX/TXT text extraction and numbered-question segmentation",
        "extraction_status": "draft_transcription_needs_human_review",
        "answer_policy": "No answer key or explanation is inferred. Human verification is required.",
        "mcq_candidates": candidates,
        "meq_page_candidates": meq_pages,
        "summary": {
            "question_candidates": len(candidates),
            "mcq_candidates": sum(item["question_type"] == "single_best_answer" for item in candidates),
            "short_answer_candidates": sum(item["question_type"] == "short_answer_candidate" for item in candidates),
            "meq_page_candidates": len(meq_pages),
        },
    }


def extract_source(source_id: str, source_dir: Path = DEFAULT_SOURCE_DIR) -> dict:
    """Extract one inbox source and save reviewable candidates in the configured backend."""
    source = next((item for item in list_sources(source_dir) if item.get("source_id") == source_id), None)
    if source is None:
        raise ValueError(f"Unknown source ID: {source_id}")
    try:
        pages = _document_pages(source["original_filename"], get_source_bytes(source_id, source_dir))
        if not any(page.strip() for page in pages):
            raise ValueError("No selectable text found. This may be a scanned PDF and needs OCR.")
        payload = parse_question_text(pages, source)
    except Exception as exc:
        update_source_metadata(source_id, {
            "status": "needs_manual_extraction",
            "extraction_error": str(exc)[:500],
        }, source_dir)
        raise

    save_extraction(source_id, payload, source_dir)
    question_count = payload["summary"]["question_candidates"] + payload["summary"]["meq_page_candidates"]
    update_source_metadata(source_id, {
        "status": "extracted_pending_review",
        "question_count": question_count,
        "extraction_file": f"extractions/{source_id}.json",
        "extracted_at": datetime.now(UTC).isoformat(),
        "extraction_error": None,
    }, source_dir)
    return payload


def _update_source(source_dir: Path, source_id: str, updates: dict) -> None:
    update_source_metadata(source_id, updates, source_dir)


