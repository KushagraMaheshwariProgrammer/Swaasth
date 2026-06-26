"""Parse ICMR and Clinical Establishments guideline documents into RAG chunks."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html import unescape
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
import pytesseract
from PIL import Image

from app.services.document_extraction import TESSERACT_PATH
from app.services.stg_parser import SECTION_HEADERS, _merge_small_chunks, _split_page_into_sections

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
ICMR_DIR = _BACKEND_ROOT / "data" / "Standard Treatment Guidelines" / "ICMR"
CEA_DIR = (
    _BACKEND_ROOT
    / "data"
    / "Standard Treatment Guidelines"
    / "Clinical Estabilishments Act STG"
)
LEGACY_ICMR_MANIFEST = _BACKEND_ROOT / "data" / "icmr_index" / "chunks_manifest.json"

MIN_NATIVE_TEXT_CHARS = 80
OCR_RENDER_DPI = 150
SUPPORTED_SUFFIXES = {".pdf", ".html", ".htm"}


@dataclass
class GuidelineDocument:
    condition: str
    corpus: str
    source_file: str
    chapter: str = ""


@dataclass
class GuidelineChunk:
    chunk_id: str
    condition: str
    corpus: str
    document: str
    source_file: str
    chapter: str
    section_type: str
    page_start: int
    page_end: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_stg_chunk(self) -> Any:
        from app.services.stg_parser import StgChunk

        return StgChunk(
            chunk_id=self.chunk_id,
            condition=self.condition,
            chapter=self.chapter,
            section_type=self.section_type,
            page_start=self.page_start,
            page_end=self.page_end,
            text=self.text,
        )


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[\s_]+", "-", cleaned).strip("-") or "document"


def _title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = re.sub(r"[_]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or filename


def _ocr_page_image(page: fitz.Page) -> str:
    try:
        pixmap = page.get_pixmap(dpi=OCR_RENDER_DPI, alpha=False)
        image = Image.open(BytesIO(pixmap.tobytes("png")))
        return pytesseract.image_to_string(image).strip()
    except Exception:
        return ""


def extract_page_text(page: fitz.Page, *, use_ocr_fallback: bool = True) -> str:
    native = (page.get_text("text") or "").strip()
    if len(native) >= MIN_NATIVE_TEXT_CHARS or not use_ocr_fallback:
        return native
    ocr_text = _ocr_page_image(page)
    if len(ocr_text) > len(native):
        return ocr_text
    return native


def extract_pdf_pages(
    pdf_path: Path,
    *,
    use_ocr_fallback: bool = True,
) -> list[tuple[int, str]]:
    doc = fitz.open(str(pdf_path))
    pages: list[tuple[int, str]] = []
    for index in range(doc.page_count):
        page_number = index + 1
        text = extract_page_text(doc[index], use_ocr_fallback=use_ocr_fallback)
        if text.strip():
            pages.append((page_number, text.strip()))
    doc.close()
    return pages


def extract_html_text(html_path: Path) -> list[tuple[int, str]]:
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</p>", "\n\n", raw)
    text = unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    return [(1, text)]


def _chunks_from_pages(
    *,
    corpus: str,
    document_title: str,
    source_file: str,
    pages: list[tuple[int, str]],
    chapter: str = "",
) -> list[GuidelineChunk]:
    slug = _slugify(document_title)
    raw_chunks: list[GuidelineChunk] = []
    counter = 0

    for page_number, page_text in pages:
        if len(page_text) < 40:
            continue
        sections = _split_page_into_sections(page_text)
        for section_type, section_text in sections:
            if len(section_text) < 40:
                continue
            counter += 1
            raw_chunks.append(
                GuidelineChunk(
                    chunk_id=f"{corpus}-{slug}-p{page_number:04d}-{counter:04d}",
                    condition=document_title,
                    corpus=corpus,
                    document=document_title,
                    source_file=source_file,
                    chapter=chapter,
                    section_type=section_type,
                    page_start=page_number,
                    page_end=page_number,
                    text=section_text[:8000],
                )
            )

    if not raw_chunks:
        return []

    merged = _merge_small_chunks([chunk.to_stg_chunk() for chunk in raw_chunks])
    rebuilt: list[GuidelineChunk] = []
    for chunk in merged:
        rebuilt.append(
            GuidelineChunk(
                chunk_id=chunk.chunk_id,
                condition=document_title,
                corpus=corpus,
                document=document_title,
                source_file=source_file,
                chapter=chapter,
                section_type=chunk.section_type,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                text=chunk.text,
            )
        )
    return rebuilt


def build_chunks_from_file(
    file_path: Path,
    *,
    corpus: str,
    use_ocr_fallback: bool = True,
) -> list[GuidelineChunk]:
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return []

    document_title = _title_from_filename(file_path.name)
    if suffix == ".pdf":
        pages = extract_pdf_pages(file_path, use_ocr_fallback=use_ocr_fallback)
    else:
        pages = extract_html_text(file_path)

    return _chunks_from_pages(
        corpus=corpus,
        document_title=document_title,
        source_file=file_path.name,
        pages=pages,
        chapter=corpus.replace("_", " ").title(),
    )


def build_chunks_from_directory(
    directory: Path,
    *,
    corpus: str,
    use_ocr_fallback: bool = True,
    max_files: int | None = None,
) -> list[GuidelineChunk]:
    if not directory.exists():
        return []

    files = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if max_files is not None:
        files = files[:max_files]

    chunks: list[GuidelineChunk] = []
    for file_path in files:
        chunks.extend(
            build_chunks_from_file(
                file_path,
                corpus=corpus,
                use_ocr_fallback=use_ocr_fallback,
            )
        )
    return chunks


def load_legacy_icmr_chunks() -> list[GuidelineChunk]:
    if not LEGACY_ICMR_MANIFEST.exists():
        return []

    payload = json.loads(LEGACY_ICMR_MANIFEST.read_text(encoding="utf-8"))
    chunks: list[GuidelineChunk] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if len(text) < 40:
            continue
        chunks.append(
            GuidelineChunk(
                chunk_id=str(item.get("chunk_id") or ""),
                condition=str(item.get("document") or item.get("condition") or ""),
                corpus="icmr",
                document=str(item.get("document") or item.get("condition") or ""),
                source_file=str(item.get("source_file") or ""),
                chapter="ICMR",
                section_type=str(item.get("section_type") or "general"),
                page_start=int(item.get("page_start") or 0),
                page_end=int(item.get("page_end") or 0),
                text=text[:8000],
            )
        )
    return chunks


def build_primary_guideline_corpus(
    *,
    use_ocr_fallback: bool = True,
    reuse_icmr_manifest: bool = True,
) -> tuple[list[GuidelineDocument], list[GuidelineChunk]]:
    documents: list[GuidelineDocument] = []
    chunks: list[GuidelineChunk] = []

    if reuse_icmr_manifest:
        icmr_chunks = load_legacy_icmr_chunks()
        if icmr_chunks:
            chunks.extend(icmr_chunks)
            seen: set[str] = set()
            for chunk in icmr_chunks:
                if chunk.source_file in seen:
                    continue
                seen.add(chunk.source_file)
                documents.append(
                    GuidelineDocument(
                        condition=chunk.document,
                        corpus="icmr",
                        source_file=chunk.source_file,
                        chapter="ICMR",
                    )
                )
    elif ICMR_DIR.exists():
        icmr_chunks = build_chunks_from_directory(
            ICMR_DIR,
            corpus="icmr",
            use_ocr_fallback=use_ocr_fallback,
        )
        chunks.extend(icmr_chunks)
        for file_path in sorted(ICMR_DIR.iterdir()):
            if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            documents.append(
                GuidelineDocument(
                    condition=_title_from_filename(file_path.name),
                    corpus="icmr",
                    source_file=file_path.name,
                    chapter="ICMR",
                )
            )

    cea_chunks = build_chunks_from_directory(
        CEA_DIR,
        corpus="clinical_establishments",
        use_ocr_fallback=use_ocr_fallback,
    )
    chunks.extend(cea_chunks)
    for file_path in sorted(CEA_DIR.iterdir()):
        if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        documents.append(
            GuidelineDocument(
                condition=_title_from_filename(file_path.name),
                corpus="clinical_establishments",
                source_file=file_path.name,
                chapter="Clinical Establishments Act STG",
            )
        )

    deduped_docs: list[GuidelineDocument] = []
    seen_docs: set[tuple[str, str]] = set()
    for doc in documents:
        key = (doc.corpus, doc.source_file)
        if key in seen_docs:
            continue
        seen_docs.add(key)
        deduped_docs.append(doc)

    return deduped_docs, chunks


def write_primary_guideline_artifacts(
    documents: list[GuidelineDocument],
    chunks: list[GuidelineChunk],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    toc_payload = [asdict(doc) for doc in documents]
    (output_dir / "toc.json").write_text(
        json.dumps(toc_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest = [chunk.to_dict() for chunk in chunks]
    (output_dir / "chunks_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    document_names = sorted({doc.condition for doc in documents if doc.condition})
    (output_dir / "documents.json").write_text(
        json.dumps(document_names, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
