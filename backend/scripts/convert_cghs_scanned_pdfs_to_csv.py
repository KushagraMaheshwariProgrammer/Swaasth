#!/usr/bin/env python3
"""
OCR conversion for scanned CGHS PDFs that pdfplumber could not extract.

Reads pending PDFs from converted_csv/conversion_log.csv, runs Tesseract OCR,
writes CSVs to converted_csv/ocr_converted/, rebuilds full master CSV and
validation report. Does not modify original PDFs or overwrite pdfplumber CSVs.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyMuPDF required: pip install pymupdf") from exc

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pandas required: pip install pandas") from exc

try:
    import pytesseract
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pytesseract and Pillow required: pip install pytesseract pillow") from exc


_BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_ROOT = _BACKEND_ROOT / "data" / "CGHS costs"
DEFAULT_CONVERTED_ROOT = DEFAULT_INPUT_ROOT / "converted_csv"
DEFAULT_OCR_ROOT = DEFAULT_CONVERTED_ROOT / "ocr_converted"
CONVERSION_LOG = DEFAULT_CONVERTED_ROOT / "conversion_log.csv"
OCR_LOG = DEFAULT_CONVERTED_ROOT / "ocr_conversion_log.csv"
MASTER_FULL = DEFAULT_CONVERTED_ROOT / "cghs_all_cities_combined_full.csv"
VALIDATION_REPORT = DEFAULT_CONVERTED_ROOT / "cghs_conversion_validation_report.csv"

OCR_COLUMNS = [
    "city_folder",
    "source_pdf",
    "source_page",
    "raw_text_line",
    "procedure_name",
    "nabh_rate",
    "non_nabh_rate",
    "cghs_rate",
    "rate_type",
    "remarks",
    "extraction_confidence",
    "needs_manual_review",
]

AMOUNT_PATTERN = r"(?:Rs\.?\s*)?(?:₹\s*)?[\d][\d,]*(?:\.\d+)?"
SERIAL_START = re.compile(r"^\s*(\d{1,4})\s*[|.)]\s*(.*)$")
TWO_RATES_END = re.compile(
    rf"^(.+?)\s+({AMOUNT_PATTERN})\s+({AMOUNT_PATTERN})\s*/?\s*$",
    re.IGNORECASE,
)
ONE_RATE_END = re.compile(
    rf"^(.+?)\s+({AMOUNT_PATTERN})\s*/?\s*$",
    re.IGNORECASE,
)
SERIAL_ONE_RATE = re.compile(
    rf"^\s*(\d{1,4})[.)]\s*(.+?)\s+({AMOUNT_PATTERN})\s*/?\s*$",
    re.IGNORECASE,
)
SKIP_LINE = re.compile(
    r"(?i)^(page\s+\d+|file no\.|government of india|ministry of|directorate|"
    r"office memorandum|dated the|sub:|this issues|nodal officer|digitally signed|"
    r"s\.no\.|sr\.?\s*no\.?\s*$|name of investigation|rate for|remarks\s*$)"
)
CURRENCY_CLEAN = re.compile(r"[₹]|Rs\.?|INR", re.IGNORECASE)


def normalize_city_folder(name: str) -> str:
    return (name or "").strip()


def normalize_amount(raw: str) -> str:
    text = CURRENCY_CLEAN.sub("", raw or "").strip()
    text = text.rstrip("/.").replace(",", "")
    text = re.sub(r"\s+", "", text)
    if not text:
        return ""
    # Fix common OCR confusions inside numeric strings only
    fixed = []
    for index, char in enumerate(text):
        if char in "OolI":
            prev_is_digit = index > 0 and fixed[-1].isdigit()
            next_is_digit = index + 1 < len(text) and text[index + 1].isdigit()
            if char in "Oo" and (prev_is_digit or next_is_digit):
                fixed.append("0")
            elif char in "lI" and (prev_is_digit or next_is_digit):
                fixed.append("1")
            else:
                fixed.append(char)
        else:
            fixed.append(char)
    return "".join(fixed)


def clean_line(text: str) -> str:
    line = (text or "").replace("\x0c", " ")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def _parse_row_from_line(line: str) -> dict[str, Any]:
    raw = line
    needs_review = True
    confidence = 0.25
    serial = ""
    procedure = ""
    nabh = ""
    non_nabh = ""
    cghs = ""
    rate_type = ""
    remarks = ""

    if not line or SKIP_LINE.search(line):
        return {}

    serial_match = SERIAL_START.match(line)
    body = line
    if serial_match:
        serial = serial_match.group(1)
        body = serial_match.group(2).strip()
        confidence = 0.45

    two = TWO_RATES_END.match(body)
    if two:
        procedure = two.group(1).strip(" |[]")
        non_nabh = normalize_amount(two.group(2))
        nabh = normalize_amount(two.group(3))
        confidence = 0.88 if serial else 0.72
        needs_review = False
    else:
        one = SERIAL_ONE_RATE.match(line) or ONE_RATE_END.match(body)
        if one:
            if one.re is SERIAL_ONE_RATE:
                serial = one.group(1)
                procedure = one.group(2).strip(" |[]")
                cghs = normalize_amount(one.group(3))
            else:
                procedure = one.group(1).strip(" |[]")
                cghs = normalize_amount(one.group(2))
            confidence = 0.65 if serial else 0.5
            needs_review = True
        elif len(body) >= 8 and re.search(r"\d", body):
            procedure = body.strip(" |[]")
            confidence = 0.35
            needs_review = True
        else:
            return {}

    if serial and not procedure:
        return {}

    if re.search(r"(?i)nabh", line):
        rate_type = "nabh"
    elif re.search(r"(?i)non.?nabh", line):
        rate_type = "non_nabh"

    if confidence < 0.7:
        needs_review = True

    return {
        "raw_text_line": raw,
        "procedure_name": procedure,
        "nabh_rate": nabh,
        "non_nabh_rate": non_nabh,
        "cghs_rate": cghs,
        "rate_type": rate_type,
        "remarks": remarks,
        "extraction_confidence": round(confidence, 2),
        "needs_manual_review": needs_review,
        "_serial": serial,
    }


def merge_broken_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    buffer = ""
    for line in lines:
        line = clean_line(line)
        if not line:
            continue
        if SERIAL_START.match(line) or re.match(r"^\d{1,4}[.)]\s", line):
            if buffer:
                merged.append(buffer)
            buffer = line
        elif buffer and not re.search(r"\d{3,}", line):
            buffer = f"{buffer} {line}"
        else:
            if buffer:
                merged.append(buffer)
                buffer = line
            else:
                merged.append(line)
    if buffer:
        merged.append(buffer)
    return merged


def ocr_page_text(page: fitz.Page, zoom: float = 2.0) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    if image.mode != "L":
        image = image.convert("L")
    return pytesseract.image_to_string(
        image,
        config="--psm 6 -c preserve_interword_spaces=1",
    )


def extract_rows_from_pdf(
    pdf_path: Path,
    city_folder: str,
    zoom: float = 2.0,
) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    doc = fitz.open(pdf_path)
    pages_processed = 0
    try:
        total_pages = len(doc)
        rel_pdf = pdf_path.name
        for page_index in range(total_pages):
            text = ocr_page_text(doc[page_index], zoom=zoom)
            if not text.strip():
                continue
            pages_processed += 1
            merged_lines = merge_broken_lines(text.splitlines())
            for line in merged_lines:
                parsed = _parse_row_from_line(line)
                if not parsed:
                    continue
                rows.append(
                    {
                        "city_folder": city_folder,
                        "source_pdf": rel_pdf,
                        "source_page": page_index + 1,
                        **{key: parsed[key] for key in OCR_COLUMNS if key in parsed},
                    }
                )
        return rows, total_pages, pages_processed
    finally:
        doc.close()


@dataclass
class OcrResult:
    source_pdf: Path
    city_folder: str
    total_pages: int = 0
    ocr_pages_processed: int = 0
    rows_extracted: int = 0
    status: str = "failed"
    error_message: str = ""
    needs_manual_review: bool = True
    output_csv: Path | None = None


def load_pending_pdfs(conversion_log: Path) -> list[dict[str, str]]:
    pending: list[dict[str, str]] = []
    with conversion_log.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            status = (row.get("status") or "").strip()
            manual = str(row.get("needs_manual_review", "")).lower() in {"true", "1", "yes"}
            if status in {"scanned_or_no_tables_detected", "failed"} or manual:
                if status == "success":
                    continue
                pending.append(row)
    return pending


def write_ocr_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OCR_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in OCR_COLUMNS})


def convert_pdf_ocr(
    pdf_path: Path,
    city_folder: str,
    output_root: Path,
    zoom: float,
) -> OcrResult:
    normalized_city = normalize_city_folder(city_folder)
    result = OcrResult(
        source_pdf=pdf_path,
        city_folder=normalized_city,
    )
    try:
        rows, total_pages, pages_processed = extract_rows_from_pdf(
            pdf_path,
            normalized_city,
            zoom=zoom,
        )
        result.total_pages = total_pages
        result.ocr_pages_processed = pages_processed

        if pages_processed == 0:
            result.status = "no_text_detected"
            result.error_message = "OCR returned no text on any page"
            result.needs_manual_review = True
            return result

        if not rows:
            # Save raw OCR lines as fallback rows
            doc = fitz.open(pdf_path)
            try:
                for page_index in range(len(doc)):
                    text = ocr_page_text(doc[page_index], zoom=zoom)
                    for line in merge_broken_lines(text.splitlines()):
                        if clean_line(line):
                            rows.append(
                                {
                                    "city_folder": normalized_city,
                                    "source_pdf": pdf_path.name,
                                    "source_page": page_index + 1,
                                    "raw_text_line": line,
                                    "procedure_name": "",
                                    "nabh_rate": "",
                                    "non_nabh_rate": "",
                                    "cghs_rate": "",
                                    "rate_type": "",
                                    "remarks": "",
                                    "extraction_confidence": 0.2,
                                    "needs_manual_review": True,
                                }
                            )
            finally:
                doc.close()

        output_csv = output_root / normalized_city / f"{pdf_path.stem}.csv"
        write_ocr_csv(output_csv, rows)
        result.output_csv = output_csv
        result.rows_extracted = len(rows)
        review_rows = sum(1 for row in rows if row.get("needs_manual_review"))
        parsed_rows = sum(1 for row in rows if row.get("procedure_name"))

        if parsed_rows == 0:
            result.status = "needs_manual_review"
            result.error_message = "OCR text captured but no structured rows parsed"
            result.needs_manual_review = True
        elif review_rows > parsed_rows * 0.3:
            result.status = "partial_success"
            result.needs_manual_review = True
            result.error_message = f"{review_rows}/{len(rows)} rows flagged for manual review"
        else:
            result.status = "success"
            result.needs_manual_review = review_rows > 0

    except Exception as exc:
        result.status = "failed"
        result.error_message = str(exc)
        result.needs_manual_review = True
        logging.exception("OCR failed for %s", pdf_path)

    return result


def write_ocr_log(path: Path, results: list[OcrResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_pdf",
                "city_folder",
                "total_pages",
                "ocr_pages_processed",
                "rows_extracted",
                "status",
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
                    "total_pages": result.total_pages,
                    "ocr_pages_processed": result.ocr_pages_processed,
                    "rows_extracted": result.rows_extracted,
                    "status": result.status,
                    "error_message": result.error_message,
                    "needs_manual_review": result.needs_manual_review,
                }
            )


def _find_procedure_columns(columns: list[str]) -> tuple[str | None, str | None, str | None]:
    nabh = non_nabh = procedure = None
    for col in columns:
        lower = col.lower()
        if "nabh" in lower and "non" not in lower and nabh is None:
            nabh = col
        elif "non" in lower and "nabh" in lower and non_nabh is None:
            non_nabh = col
        elif any(token in lower for token in ("procedure", "investigation", "treatment", "cghs")):
            if procedure is None or len(col) > len(procedure):
                procedure = col
    if procedure is None:
        text_cols = [
            col
            for col in columns
            if col
            not in {"source_page", "extracted_table_index", "city_folder", "source_pdf"}
            and "rate" not in col.lower()
            and not re.fullmatch(r"column_\d+", col, re.I)
            and not re.fullmatch(r"sr\.?\s*no\.?", col, re.I)
        ]
        if text_cols:
            procedure = max(text_cols, key=len)
    return procedure, nabh, non_nabh


def load_pdfplumber_csvs(converted_root: Path, ocr_root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for csv_path in sorted(converted_root.rglob("*.csv")):
        if csv_path.name in {
            "conversion_log.csv",
            "ocr_conversion_log.csv",
            "cghs_all_cities_combined.csv",
            "cghs_all_cities_combined_full.csv",
            "cghs_conversion_validation_report.csv",
        }:
            continue
        if ocr_root in csv_path.parents:
            continue
        try:
            df = pd.read_csv(
                csv_path,
                dtype=str,
                engine="python",
                on_bad_lines="skip",
            ).fillna("")
        except Exception:
            logging.warning("Skipping unreadable CSV: %s", csv_path)
            continue
        if df.empty:
            continue
        city = normalize_city_folder(csv_path.parent.name)
        rel_pdf = csv_path.with_suffix(".pdf").name
        procedure_col, nabh_col, non_nabh_col = _find_procedure_columns(list(df.columns))
        normalized = pd.DataFrame(
            {
                "extraction_method": "pdfplumber",
                "city_folder": city,
                "source_pdf": rel_pdf,
                "source_page": df.get("source_page", ""),
                "extracted_table_index": df.get("extracted_table_index", ""),
                "raw_text_line": "",
                "procedure_name": df[procedure_col] if procedure_col else "",
                "nabh_rate": df[nabh_col] if nabh_col else "",
                "non_nabh_rate": df[non_nabh_col] if non_nabh_col else "",
                "cghs_rate": "",
                "rate_type": "",
                "remarks": df.get("Remarks", df.get("remarks", "")),
                "extraction_confidence": "0.95",
                "needs_manual_review": False,
            }
        )
        frames.append(normalized)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_ocr_csvs(ocr_root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for csv_path in sorted(ocr_root.rglob("*.csv")):
        try:
            df = pd.read_csv(
                csv_path,
                dtype=str,
                engine="python",
                on_bad_lines="skip",
            ).fillna("")
        except Exception:
            logging.warning("Skipping unreadable OCR CSV: %s", csv_path)
            continue
        if df.empty:
            continue
        df = df.copy()
        df["extraction_method"] = "ocr"
        df["city_folder"] = df["city_folder"].map(normalize_city_folder)
        df["extracted_table_index"] = ""
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    for col in [
        "extraction_method",
        "extracted_table_index",
        "raw_text_line",
        "procedure_name",
        "nabh_rate",
        "non_nabh_rate",
        "cghs_rate",
        "rate_type",
        "remarks",
        "extraction_confidence",
        "needs_manual_review",
    ]:
        if col not in combined.columns:
            combined[col] = ""
    return combined


def rebuild_master_full(converted_root: Path, ocr_root: Path, master_path: Path) -> pd.DataFrame:
    pdfplumber_df = load_pdfplumber_csvs(converted_root, ocr_root)
    ocr_df = load_ocr_csvs(ocr_root)
    if pdfplumber_df.empty and ocr_df.empty:
        master = pd.DataFrame()
    elif pdfplumber_df.empty:
        master = ocr_df
    elif ocr_df.empty:
        master = pdfplumber_df
    else:
        master = pd.concat([pdfplumber_df, ocr_df], ignore_index=True, sort=False)
    master_path.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(master_path, index=False)
    return master


def write_validation_report(
    path: Path,
    *,
    input_root: Path,
    converted_root: Path,
    conversion_log: Path,
    ocr_log: Path,
    master_df: pd.DataFrame,
) -> None:
    all_pdfs = sorted(
        p for p in input_root.rglob("*.pdf") if converted_root not in p.parents
    )
    conversion_rows = list(csv.DictReader(conversion_log.open(encoding="utf-8")))
    ocr_rows = (
        list(csv.DictReader(ocr_log.open(encoding="utf-8")))
        if ocr_log.exists()
        else []
    )

    pdfplumber_ok = {
        Path(row["source_pdf"]).name
        for row in conversion_rows
        if row.get("status") == "success"
    }
    ocr_ok = {
        Path(row["source_pdf"]).name
        for row in ocr_rows
        if row.get("status") in {"success", "partial_success", "needs_manual_review"}
        and int(row.get("rows_extracted") or 0) > 0
    }
    ocr_failed = {
        Path(row["source_pdf"]).name
        for row in ocr_rows
        if row.get("status") in {"failed", "no_text_detected"}
    }
    still_failed = [p for p in all_pdfs if p.name not in pdfplumber_ok and p.name not in ocr_ok]

    duplicate_sources = master_df.groupby(["city_folder", "source_pdf"]).size()
    duplicate_sources = duplicate_sources[duplicate_sources > 1]

    empty_ocr_csvs = sorted(
        str(p)
        for p in (converted_root / "ocr_converted").rglob("*.csv")
        if p.stat().st_size <= len(",".join(OCR_COLUMNS)) + 2
    ) if (converted_root / "ocr_converted").exists() else []

    cities_covered = sorted(master_df["city_folder"].dropna().unique()) if not master_df.empty else []
    manual_review_pdfs = sorted(
        {
            row["source_pdf"]
            for row in ocr_rows
            if str(row.get("needs_manual_review", "")).lower() in {"true", "1", "yes"}
        }
    )

    summary_rows = [
        {"metric": "total_pdfs_found", "value": len(all_pdfs), "details": ""},
        {"metric": "pdfplumber_converted_count", "value": len(pdfplumber_ok), "details": ""},
        {"metric": "ocr_converted_count", "value": len(ocr_ok), "details": ""},
        {"metric": "still_failed_count", "value": len(still_failed), "details": "; ".join(p.name for p in still_failed[:20])},
        {"metric": "total_rows_in_final_master_csv", "value": len(master_df), "details": ""},
        {"metric": "cities_covered_count", "value": len(cities_covered), "details": ", ".join(cities_covered)},
        {"metric": "pdfs_still_needing_manual_review", "value": len(manual_review_pdfs), "details": "; ".join(Path(p).name for p in manual_review_pdfs[:20])},
        {"metric": "duplicate_source_pdf_groups", "value": len(duplicate_sources), "details": ""},
        {"metric": "empty_csv_count", "value": len(empty_ocr_csvs), "details": "; ".join(empty_ocr_csvs[:10])},
        {
            "metric": "ready_for_app_integration",
            "value": "yes" if len(still_failed) == 0 else "partial",
            "details": "All PDFs processed with at least raw OCR rows" if len(still_failed) == 0 else f"{len(still_failed)} PDF(s) still have no CSV output",
        },
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(path, index=False)


def run_ocr_pipeline(
    input_root: Path,
    converted_root: Path,
    ocr_root: Path,
    zoom: float,
    limit: int | None = None,
) -> dict[str, Any]:
    pending = load_pending_pdfs(converted_root / "conversion_log.csv")
    if limit:
        pending = pending[:limit]

    results: list[OcrResult] = []
    for index, row in enumerate(pending, start=1):
        pdf_path = Path(row["source_pdf"])
        if not pdf_path.is_absolute():
            pdf_path = input_root.parent.parent / pdf_path
        if not pdf_path.exists():
            pdf_path = input_root / normalize_city_folder(row["city_folder"]) / Path(row["source_pdf"]).name
        city = normalize_city_folder(row.get("city_folder", pdf_path.parent.name))
        logging.info("[%d/%d] OCR converting %s", index, len(pending), pdf_path.name)
        results.append(convert_pdf_ocr(pdf_path, city, ocr_root, zoom=zoom))

    write_ocr_log(converted_root / "ocr_conversion_log.csv", results)
    master_df = rebuild_master_full(converted_root, ocr_root, converted_root / "cghs_all_cities_combined_full.csv")
    write_validation_report(
        converted_root / "cghs_conversion_validation_report.csv",
        input_root=input_root,
        converted_root=converted_root,
        conversion_log=converted_root / "conversion_log.csv",
        ocr_log=converted_root / "ocr_conversion_log.csv",
        master_df=master_df,
    )

    ocr_success = [r for r in results if r.status in {"success", "partial_success", "needs_manual_review"} and r.rows_extracted > 0]
    ocr_failed = [r for r in results if r.status in {"failed", "no_text_detected"} or r.rows_extracted == 0]

    return {
        "pending_count": len(pending),
        "ocr_converted": len(ocr_success),
        "ocr_failed": len(ocr_failed),
        "master_rows": len(master_df),
        "master_path": str(converted_root / "cghs_all_cities_combined_full.csv"),
        "validation_path": str(converted_root / "cghs_conversion_validation_report.csv"),
        "ocr_log_path": str(converted_root / "ocr_conversion_log.csv"),
        "still_failed": [str(r.source_pdf) for r in ocr_failed],
        "manual_review": [str(r.source_pdf) for r in results if r.needs_manual_review],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OCR-convert scanned CGHS PDFs to CSV")
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--converted-root", type=Path, default=DEFAULT_CONVERTED_ROOT)
    parser.add_argument("--ocr-root", type=Path, default=DEFAULT_OCR_ROOT)
    parser.add_argument("--zoom", type=float, default=2.0, help="Render zoom factor for OCR")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N pending PDFs")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        pytesseract.get_tesseract_version()
    except Exception:
        logging.error("Tesseract not found. Install with: brew install tesseract")
        return 1

    summary = run_ocr_pipeline(
        args.input_root.resolve(),
        args.converted_root.resolve(),
        args.ocr_root.resolve(),
        zoom=args.zoom,
        limit=args.limit,
    )

    print("\n=== CGHS OCR Conversion Summary ===")
    print(f"Pending PDFs processed:  {summary['pending_count']}")
    print(f"OCR converted:           {summary['ocr_converted']}")
    print(f"OCR failed:              {summary['ocr_failed']}")
    print(f"Master CSV rows:         {summary['master_rows']}")
    print(f"Full master CSV:         {summary['master_path']}")
    print(f"Validation report:       {summary['validation_path']}")
    print(f"OCR log:                 {summary['ocr_log_path']}")
    if summary["still_failed"]:
        print("\nStill failed:")
        for path in summary["still_failed"]:
            print(f"  - {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
