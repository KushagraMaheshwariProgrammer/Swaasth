#!/usr/bin/env python3
"""
Bulk-convert CGHS city-wise PDF rate tables to CSV.

Input:  backend/data/CGHS costs/<city>/*.pdf
Output: backend/data/CGHS costs/converted_csv/<city>/*.csv
        backend/data/CGHS costs/converted_csv/cghs_all_cities_combined.csv
        backend/data/CGHS costs/converted_csv/conversion_log.csv

Does not modify or delete original PDFs.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyMuPDF (fitz) is required. Install with: pip install PyMuPDF") from exc

try:
    import pdfplumber
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pdfplumber is required. Install with: pip install pdfplumber") from exc


_BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_ROOT = _BACKEND_ROOT / "data" / "CGHS costs"
DEFAULT_OUTPUT_ROOT = DEFAULT_INPUT_ROOT / "converted_csv"
LOG_FILENAME = "conversion_log.csv"
MASTER_FILENAME = "cghs_all_cities_combined.csv"

MULTISPACE = re.compile(r"\s{2,}")
NUMERICISH = re.compile(r"^[\d₹Rs.,/\-\s]+$", re.IGNORECASE)


@dataclass
class ExtractedTable:
    page_number: int
    table_index: int
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class PdfConversionResult:
    source_pdf: Path
    city_folder: str
    status: str
    rows_extracted: int = 0
    error_message: str = ""
    needs_manual_review: bool = False
    tables: list[ExtractedTable] = field(default_factory=list)
    output_csv: Path | None = None


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def _row_is_empty(row: Iterable[Any]) -> bool:
    return not any(_clean_cell(cell) for cell in row)


def _trim_blank_columns(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows
    max_cols = max(len(row) for row in rows)
    padded = [row + [""] * (max_cols - len(row)) for row in rows]
    keep_indices = [
        index
        for index in range(max_cols)
        if any(_clean_cell(row[index]) for row in padded)
    ]
    if not keep_indices:
        return []
    return [[row[index] for index in keep_indices] for row in padded]


def clean_table_rows(raw_rows: list[list[Any]]) -> list[list[str]]:
    cleaned: list[list[str]] = []
    for raw_row in raw_rows:
        row = [_clean_cell(cell) for cell in raw_row]
        if _row_is_empty(row):
            continue
        cleaned.append(row)
    return _trim_blank_columns(cleaned)


def _looks_like_header(row: list[str]) -> bool:
    non_empty = [cell for cell in row if cell]
    if len(non_empty) < 2:
        return False
    numeric_cells = sum(1 for cell in non_empty if NUMERICISH.match(cell))
    return numeric_cells < len(non_empty) / 2


def _normalize_table_columns(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    if not rows:
        return [], []
    rows = _trim_blank_columns(rows)
    if not rows:
        return [], []
    header = rows[0]
    data_rows = rows[1:]
    if _looks_like_header(header):
        columns = [cell or f"column_{index + 1}" for index, cell in enumerate(header)]
        return columns, data_rows
    width = max(len(row) for row in rows)
    columns = [f"column_{index + 1}" for index in range(width)]
    padded_rows = [row + [""] * (width - len(row)) for row in rows]
    return columns, padded_rows


def _pdf_has_extractable_text(pdf_path: Path) -> tuple[int, bool]:
    """Return (total_text_length, appears_scanned)."""
    doc = fitz.open(pdf_path)
    try:
        total_text = 0
        image_pages = 0
        for page in doc:
            text = page.get_text() or ""
            total_text += len(text.strip())
            if page.get_images():
                image_pages += 1
        appears_scanned = total_text < 50 and image_pages > 0
        return total_text, appears_scanned
    finally:
        doc.close()


def _extract_tables_with_pdfplumber(pdf_path: Path) -> list[ExtractedTable]:
    extracted: list[ExtractedTable] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table_index, raw_table in enumerate(tables, start=1):
                rows = clean_table_rows(raw_table or [])
                if not rows:
                    continue
                extracted.append(
                    ExtractedTable(
                        page_number=page_number,
                        table_index=table_index,
                        rows=rows,
                    )
                )
    return extracted


def _split_text_line(line: str) -> list[str]:
    if "\t" in line:
        parts = [part.strip() for part in line.split("\t")]
    else:
        parts = [part.strip() for part in MULTISPACE.split(line.strip())]
    return [part for part in parts if part]


def _extract_rows_from_plain_text(pdf_path: Path) -> list[ExtractedTable]:
    """Fallback: parse text lines that look tabular."""
    rows_by_page: dict[int, list[list[str]]] = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                continue
            page_rows: list[list[str]] = []
            for line in text.splitlines():
                line = line.strip()
                if not line or len(line) < 4:
                    continue
                parts = _split_text_line(line)
                if len(parts) < 2:
                    continue
                # Skip obvious headers/footers
                lower = line.lower()
                if lower.startswith("page ") or "government of india" in lower:
                    continue
                page_rows.append(parts)
            if page_rows:
                rows_by_page[page_number] = page_rows

    extracted: list[ExtractedTable] = []
    for page_number, rows in rows_by_page.items():
        cleaned = clean_table_rows(rows)
        if cleaned:
            extracted.append(
                ExtractedTable(page_number=page_number, table_index=1, rows=cleaned)
            )
    return extracted


def _write_pdf_csv(
    output_csv: Path,
    tables: list[ExtractedTable],
) -> int:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    total_rows = 0
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer: csv.writer | None = None
        columns_written: list[str] | None = None
        for table in tables:
            columns, data_rows = _normalize_table_columns(table.rows)
            if not data_rows and columns:
                data_rows = [columns]
                columns = [f"column_{index + 1}" for index in range(len(data_rows[0]))]
            if not data_rows:
                continue
            fieldnames = ["source_page", "extracted_table_index", *columns]
            if writer is None:
                writer = csv.writer(handle)
                writer.writerow(fieldnames)
                columns_written = fieldnames
            for row in data_rows:
                padded = row + [""] * (len(columns) - len(row))
                writer.writerow(
                    [table.page_number, table.table_index, *padded[: len(columns)]]
                )
                total_rows += 1
    return total_rows


def _append_master_rows(
    master_rows: list[dict[str, Any]],
    *,
    city_folder: str,
    source_pdf: Path,
    input_root: Path,
    table: ExtractedTable,
) -> None:
    columns, data_rows = _normalize_table_columns(table.rows)
    if not data_rows and columns:
        data_rows = [columns]
        columns = [f"column_{index + 1}" for index in range(len(data_rows[0]))]
    rel_pdf = source_pdf.relative_to(input_root)
    for row in data_rows:
        padded = row + [""] * (len(columns) - len(row))
        record: dict[str, Any] = {
            "city_folder": city_folder,
            "source_pdf": str(rel_pdf),
            "source_page": table.page_number,
            "extracted_table_index": table.table_index,
        }
        for index, column in enumerate(columns):
            record[column] = padded[index] if index < len(padded) else ""
        master_rows.append(record)


def convert_pdf(pdf_path: Path, input_root: Path, output_root: Path) -> PdfConversionResult:
    city_folder = pdf_path.parent.relative_to(input_root).as_posix()
    result = PdfConversionResult(source_pdf=pdf_path, city_folder=city_folder, status="failed")

    try:
        _, appears_scanned = _pdf_has_extractable_text(pdf_path)
        tables = _extract_tables_with_pdfplumber(pdf_path)
        used_text_fallback = False

        if not tables:
            tables = _extract_rows_from_plain_text(pdf_path)
            used_text_fallback = bool(tables)

        if not tables:
            if appears_scanned:
                result.status = "scanned_or_no_tables_detected"
                result.error_message = "Image-only/scanned PDF with no extractable text or tables"
            else:
                result.status = "failed"
                result.error_message = "No tables or parseable text rows detected"
            result.needs_manual_review = True
            return result

        relative = pdf_path.relative_to(input_root)
        output_csv = output_root / relative.with_suffix(".csv")
        rows_written = _write_pdf_csv(output_csv, tables)
        result.tables = tables
        result.output_csv = output_csv
        result.rows_extracted = rows_written

        if rows_written == 0:
            result.status = "failed"
            result.error_message = "Tables detected but no data rows after cleaning"
            result.needs_manual_review = True
        elif used_text_fallback:
            result.status = "partial_success"
            result.needs_manual_review = True
            result.error_message = "Extracted from plain text fallback; verify column alignment"
        else:
            result.status = "success"

        # Flag very small extractions for review
        if result.status == "success" and rows_written < 3:
            result.status = "partial_success"
            result.needs_manual_review = True
            result.error_message = "Very few rows extracted; verify output"

    except Exception as exc:
        result.status = "failed"
        result.error_message = str(exc)
        result.needs_manual_review = True
        logging.exception("Failed converting %s", pdf_path)

    return result


def discover_pdfs(input_root: Path, output_root: Path) -> list[Path]:
    pdfs: list[Path] = []
    for path in sorted(input_root.rglob("*.pdf")):
        if output_root in path.parents:
            continue
        pdfs.append(path)
    return pdfs


def _collect_master_fieldnames(master_rows: list[dict[str, Any]]) -> list[str]:
    base = ["city_folder", "source_pdf", "source_page", "extracted_table_index"]
    extras: list[str] = []
    seen = set(base)
    for row in master_rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                extras.append(key)
    return base + sorted(extras, key=lambda name: (name.startswith("column_"), name))


def write_master_csv(path: Path, master_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _collect_master_fieldnames(master_rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(master_rows)


def write_conversion_log(path: Path, results: list[PdfConversionResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_pdf",
                "city_folder",
                "status",
                "rows_extracted",
                "error_message",
                "needs_manual_review",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "source_pdf": str(result.source_pdf),
                    "city_folder": result.city_folder,
                    "status": result.status,
                    "rows_extracted": result.rows_extracted,
                    "error_message": result.error_message,
                    "needs_manual_review": result.needs_manual_review,
                }
            )


def run_conversion(input_root: Path, output_root: Path) -> dict[str, Any]:
    pdfs = discover_pdfs(input_root, output_root)
    results: list[PdfConversionResult] = []
    master_rows: list[dict[str, Any]] = []

    logging.info("Found %d PDF(s) under %s", len(pdfs), input_root)

    for pdf_path in pdfs:
        logging.info("Converting: %s", pdf_path.relative_to(input_root))
        result = convert_pdf(pdf_path, input_root, output_root)
        results.append(result)
        if result.tables and result.rows_extracted > 0:
            for table in result.tables:
                _append_master_rows(
                    master_rows,
                    city_folder=result.city_folder,
                    source_pdf=pdf_path,
                    input_root=input_root,
                    table=table,
                )

    log_path = output_root / LOG_FILENAME
    master_path = output_root / MASTER_FILENAME
    write_conversion_log(log_path, results)
    write_master_csv(master_path, master_rows)

    success_statuses = {"success", "partial_success"}
    successful = [r for r in results if r.status in success_statuses]
    failed = [r for r in results if r.status not in success_statuses]
    manual_review = [r for r in results if r.needs_manual_review]

    summary = {
        "total_pdfs": len(pdfs),
        "successful": len(successful),
        "failed": len(failed),
        "output_root": str(output_root),
        "master_csv": str(master_path),
        "log_csv": str(log_path),
        "manual_review": [str(r.source_pdf) for r in manual_review],
        "master_rows": len(master_rows),
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert CGHS city PDF tables to CSV")
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="Root folder containing city subfolders with PDFs",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Output folder for converted CSV files",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    if args.verbose:
        logging.getLogger("pdfminer").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)

    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()

    if not input_root.exists():
        logging.error("Input root does not exist: %s", input_root)
        return 1

    summary = run_conversion(input_root, output_root)

    print("\n=== CGHS PDF Conversion Summary ===")
    print(f"Total PDFs found:        {summary['total_pdfs']}")
    print(f"Converted successfully:  {summary['successful']}")
    print(f"Failed:                  {summary['failed']}")
    print(f"Master CSV rows:         {summary['master_rows']}")
    print(f"Output folder:           {summary['output_root']}")
    print(f"Master CSV:              {summary['master_csv']}")
    print(f"Log CSV:                 {summary['log_csv']}")
    print(f"Needs manual review:     {len(summary['manual_review'])}")
    if summary["manual_review"]:
        print("\nPDFs needing manual review:")
        for path in summary["manual_review"]:
            print(f"  - {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
