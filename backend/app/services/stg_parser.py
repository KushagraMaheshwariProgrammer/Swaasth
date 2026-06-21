"""Parse CRC Standard Treatment Guidelines PDF into TOC entries and chunks."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STG_PDF = (
    _BACKEND_ROOT / "data" / "Standard Treatment Guidelines" / "STG.pdf"
)

SECTION_HEADERS = (
    "Diagnosis",
    "Diagnostic tests",
    "Investigations",
    "Treatment",
    "Non-pharmacological",
    "Pharmacological",
    "Referral",
    "Follow-up",
    "Prevention",
    "Complications",
    "Management",
)

BOOK_PAGE_OFFSET = 57  # pdf_page_index (0-based) = book_page + BOOK_PAGE_OFFSET


@dataclass
class TocEntry:
    condition: str
    book_page: int
    chapter: str = ""


@dataclass
class StgChunk:
    chunk_id: str
    condition: str
    chapter: str
    section_type: str
    page_start: int
    page_end: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_condition(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name.strip())
    return cleaned


def _book_page_from_pdf_index(pdf_index: int) -> int:
    return pdf_index - BOOK_PAGE_OFFSET


def _pdf_index_from_book_page(book_page: int) -> int:
    return book_page + BOOK_PAGE_OFFSET


def extract_toc_from_pages(pages_text: list[str]) -> list[TocEntry]:
    """Extract condition → book page mappings from Contents pages."""
    entries: list[TocEntry] = []
    current_chapter = ""
    in_contents = False
    pending_condition: str | None = None

    chapter_re = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$")
    page_re = re.compile(r"^\s*(\d{1,4})\s*$")
    inline_entry_re = re.compile(
        r"^([A-Za-z][A-Za-z0-9\s/\-(),.'']+?)\s+(\d{1,4})\s*$"
    )
    skip_prefixes = (
        "message from",
        "preface",
        "acknowledgement",
        "editorial",
        "guidelines contributor",
        "introduction to",
        "safe and rational",
        "abbreviations",
        "contents",
        "xx",
        "xxi",
        "xxii",
    )

    def _is_skip_line(line: str) -> bool:
        lowered = line.lower()
        return any(lowered.startswith(prefix) for prefix in skip_prefixes)

    def _append_entry(condition: str, book_page: int) -> None:
        nonlocal current_chapter
        cleaned = _normalize_condition(condition)
        if len(cleaned) < 3 or book_page <= 0 or _is_skip_line(cleaned):
            return
        entries.append(
            TocEntry(
                condition=cleaned,
                book_page=book_page,
                chapter=current_chapter,
            )
        )

    for page_text in pages_text[:120]:
        if "Contents" in page_text:
            in_contents = True
        if not in_contents:
            continue

        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line or _is_skip_line(line):
                continue

            chapter_match = chapter_re.match(line)
            if chapter_match:
                current_chapter = chapter_match.group(2).strip()
                pending_condition = None
                continue

            page_match = page_re.match(line)
            if page_match and pending_condition:
                _append_entry(pending_condition, int(page_match.group(1)))
                pending_condition = None
                continue

            inline_match = inline_entry_re.match(line)
            if inline_match:
                _append_entry(inline_match.group(1), int(inline_match.group(2)))
                pending_condition = None
                continue

            if re.match(r"^\d+\.$", line):
                continue

            if line.endswith("\t") or (
                not page_re.match(line) and not inline_entry_re.match(line)
            ):
                candidate = line.rstrip("\t").strip()
                if candidate and not candidate.isdigit():
                    if pending_condition:
                        pending_condition = f"{pending_condition} {candidate}".strip()
                    else:
                        pending_condition = candidate

    deduped: list[TocEntry] = []
    seen: set[str] = set()
    for entry in entries:
        key = entry.condition.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _detect_section_type(text_block: str) -> str:
    first_line = text_block.split("\n", 1)[0].strip()
    for header in SECTION_HEADERS:
        if first_line.lower().startswith(header.lower()):
            return header
    return "general"


def _split_page_into_sections(page_text: str) -> list[tuple[str, str]]:
    """Split page text into (section_type, text) pairs."""
    section_pattern = re.compile(
        r"(?m)^(" + "|".join(re.escape(h) for h in SECTION_HEADERS) + r")\s*$"
    )
    parts = section_pattern.split(page_text)
    if len(parts) <= 1:
        return [("general", page_text.strip())] if page_text.strip() else []

    sections: list[tuple[str, str]] = []
    if parts[0].strip():
        sections.append(("general", parts[0].strip()))
    for index in range(1, len(parts), 2):
        header = parts[index].strip()
        body = parts[index + 1].strip() if index + 1 < len(parts) else ""
        if body:
            sections.append((header, body))
    return sections


def _merge_small_chunks(chunks: list[StgChunk], min_chars: int = 200) -> list[StgChunk]:
    if not chunks:
        return []
    merged: list[StgChunk] = []
    buffer: StgChunk | None = None
    for chunk in chunks:
        if buffer is None:
            buffer = chunk
            continue
        same_condition = buffer.condition == chunk.condition
        combined_len = len(buffer.text) + len(chunk.text)
        if same_condition and combined_len < 3500 and (
            len(buffer.text) < min_chars or len(chunk.text) < min_chars
        ):
            buffer = StgChunk(
                chunk_id=buffer.chunk_id,
                condition=buffer.condition,
                chapter=buffer.chapter,
                section_type=buffer.section_type,
                page_start=buffer.page_start,
                page_end=chunk.page_end,
                text=f"{buffer.text}\n\n{chunk.text}".strip(),
            )
        else:
            merged.append(buffer)
            buffer = chunk
    if buffer:
        merged.append(buffer)
    return merged


def build_chunks_from_pdf(pdf_path: Path | None = None) -> tuple[list[TocEntry], list[StgChunk]]:
    pdf_path = pdf_path or DEFAULT_STG_PDF
    if not pdf_path.exists():
        raise FileNotFoundError(f"STG PDF not found at {pdf_path}")

    doc = fitz.open(str(pdf_path))
    pages_text = [doc[index].get_text("text") for index in range(doc.page_count)]
    doc.close()

    toc = extract_toc_from_pages(pages_text)
    if not toc:
        raise ValueError("Could not parse STG table of contents.")

    sorted_toc = sorted(toc, key=lambda entry: entry.book_page)
    condition_ranges: list[tuple[TocEntry, int, int]] = []
    for index, entry in enumerate(sorted_toc):
        start_index = _pdf_index_from_book_page(entry.book_page)
        if index + 1 < len(sorted_toc):
            end_index = _pdf_index_from_book_page(sorted_toc[index + 1].book_page) - 1
        else:
            end_index = len(pages_text) - 1
        start_index = max(start_index, 0)
        end_index = max(start_index, min(end_index, len(pages_text) - 1))
        if start_index >= len(pages_text):
            continue
        condition_ranges.append((entry, start_index, end_index))

    raw_chunks: list[StgChunk] = []
    chunk_counter = 0

    for entry, start_index, end_index in condition_ranges:
        for page_index in range(start_index, end_index + 1):
            page_text = pages_text[page_index].strip()
            if not page_text or len(page_text) < 40:
                continue
            sections = _split_page_into_sections(page_text)
            for section_type, section_text in sections:
                if len(section_text) < 40:
                    continue
                chunk_counter += 1
                raw_chunks.append(
                    StgChunk(
                        chunk_id=f"stg-{chunk_counter:05d}",
                        condition=entry.condition,
                        chapter=entry.chapter,
                        section_type=section_type,
                        page_start=_book_page_from_pdf_index(page_index),
                        page_end=_book_page_from_pdf_index(page_index),
                        text=section_text[:8000],
                    )
                )

    return toc, _merge_small_chunks(raw_chunks)


def write_parsed_artifacts(
    toc: list[TocEntry],
    chunks: list[StgChunk],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    toc_payload = [asdict(entry) for entry in toc]
    (output_dir / "toc.json").write_text(
        json.dumps(toc_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest = [chunk.to_dict() for chunk in chunks]
    (output_dir / "chunks_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
