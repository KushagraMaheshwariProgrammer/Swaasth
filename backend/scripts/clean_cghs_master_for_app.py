#!/usr/bin/env python3
"""
Clean CGHS full master CSV for production-safe app integration.

Reads:  converted_csv/cghs_all_cities_combined_full.csv
Writes: converted_csv/cghs_all_cities_cleaned_for_app.csv
        converted_csv/cghs_ocr_rows_needing_review.csv
        converted_csv/cghs_cleaning_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONVERTED_ROOT = _BACKEND_ROOT / "data" / "CGHS costs" / "converted_csv"
FULL_MASTER = DEFAULT_CONVERTED_ROOT / "cghs_all_cities_combined_full.csv"
CLEANED_OUTPUT = DEFAULT_CONVERTED_ROOT / "cghs_all_cities_cleaned_for_app.csv"
REVIEW_OUTPUT = DEFAULT_CONVERTED_ROOT / "cghs_ocr_rows_needing_review.csv"
SUMMARY_OUTPUT = DEFAULT_CONVERTED_ROOT / "cghs_cleaning_summary.csv"

OUTPUT_COLUMNS = [
    "city",
    "source_pdf",
    "source_page",
    "procedure_name",
    "nabh_rate",
    "non_nabh_rate",
    "cghs_rate",
    "rate_type",
    "remarks",
    "extraction_method",
    "needs_manual_review",
    "quality_status",
]

HEADER_TOKENS = re.compile(
    r"(?i)(s\.?\s*no|sr\.?\s*no|name of investigation|treatment procedure|"
    r"cghs treatment|rate for|nabh|non.?nabh|remarks|super specialty|delhi/ncr)"
)
MESSY_PROCEDURE = re.compile(r"^[\d\s|.\[\]_\-*+]+$")
OCR_ARTIFACTS = re.compile(r"_{3,}|sss_|\|\s*\|")
CURRENCY_CLEAN = re.compile(r"[₹]|Rs\.?|INR", re.IGNORECASE)


def normalize_city(name: str) -> str:
    return (name or "").strip()


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def normalize_rate(raw: Any) -> str:
    text = CURRENCY_CLEAN.sub("", str(raw or "")).strip()
    text = text.rstrip("/.").replace(",", "").replace(" ", "")
    if not text:
        return ""
    try:
        amount = float(text)
        if amount <= 0:
            return ""
        if amount == int(amount):
            return str(int(amount))
        return f"{amount:.2f}".rstrip("0").rstrip(".")
    except ValueError:
        return ""


def has_valid_rate(row: dict[str, Any]) -> bool:
    return any(row.get(field) for field in ("nabh_rate", "non_nabh_rate", "cghs_rate"))


def is_header_like(procedure: str) -> bool:
    text = (procedure or "").strip()
    if not text:
        return True
    if HEADER_TOKENS.search(text) and len(text) < 120:
        return True
    return False


def is_messy_procedure(procedure: str) -> bool:
    text = (procedure or "").strip()
    if len(text) < 3:
        return True
    if MESSY_PROCEDURE.match(text):
        return True
    if OCR_ARTIFACTS.search(text):
        return True
    if re.match(r"^[*|.\[\]_+\-]+\s*", text):
        return True
    if re.match(r"^\d{1,4}\s+[A-Z0-9]", text):
        return True
    pipe_count = text.count("|")
    bracket_noise = text.count("[") + text.count("]")
    if pipe_count >= 1 and re.search(r"\|\s*\d", text):
        return True
    if pipe_count >= 2 or bracket_noise >= 2:
        return True
    if re.match(r"^\d+\s*[|.\)]", text):
        return True
    return False


def _numeric_columns(columns: list[str]) -> list[str]:
    numeric: list[str] = []
    for col in columns:
        lower = col.lower()
        if col in {"source_page", "extracted_table_index"}:
            continue
        if "rate" in lower or re.fullmatch(r"column_\d+", col, re.I):
            numeric.append(col)
    return numeric


def _procedure_column(columns: list[str]) -> str | None:
    best: str | None = None
    best_score = -1
    for col in columns:
        lower = col.lower()
        if col in {"source_page", "extracted_table_index", "raw_text_line"}:
            continue
        if "rate" in lower or re.fullmatch(r"sr\.?\s*no\.?", col, re.I):
            continue
        if re.fullmatch(r"column_1", col, re.I):
            continue
        score = 0
        if any(token in lower for token in ("procedure", "investigation", "treatment", "cghs")):
            score += 5
        if re.fullmatch(r"column_2", col, re.I):
            score += 4
        score += min(len(col), 40) / 40
        if score > best_score:
            best_score = score
            best = col
    return best


def _rate_columns(columns: list[str]) -> tuple[str | None, str | None, str | None]:
    nabh = non_nabh = cghs = None
    for col in columns:
        lower = col.lower()
        if "super specialty" in lower:
            continue
        if "non" in lower and ("nabh" in lower or "nabl" in lower):
            non_nabh = col
        elif "nabh" in lower or "nabl" in lower:
            nabh = col
        elif "cghs" in lower and "rate" in lower:
            cghs = col
    if nabh or non_nabh or cghs:
        return nabh, non_nabh, cghs

    numeric_cols = [
        col
        for col in columns
        if re.fullmatch(r"column_\d+", col, re.I)
        or "rate" in col.lower()
    ]
    numeric_cols = sorted(
        numeric_cols,
        key=lambda name: int(re.search(r"\d+", name).group()) if re.search(r"\d+", name) else 0,
    )
    if len(numeric_cols) >= 2:
        # Common CGHS table order: non-NABH then NABH in trailing numeric columns.
        return numeric_cols[-1], numeric_cols[-2], numeric_cols[-3] if len(numeric_cols) >= 3 else None
    if len(numeric_cols) == 1:
        return None, None, numeric_cols[0]
    return None, None, None


def rows_from_pdfplumber_csv(csv_path: Path) -> list[dict[str, Any]]:
    try:
        raw_df = pd.read_csv(
            csv_path,
            dtype=str,
            engine="python",
            on_bad_lines="skip",
        ).fillna("")
    except Exception:
        return []

    if raw_df.empty:
        return []

    columns = list(raw_df.columns)
    procedure_col = _procedure_column(columns)
    nabh_col, non_nabh_col, cghs_col = _rate_columns(columns)
    city = normalize_city(csv_path.parent.name)
    source_pdf = csv_path.with_suffix(".pdf").name
    rows: list[dict[str, Any]] = []

    for _, raw in raw_df.iterrows():
        procedure = str(raw.get(procedure_col, "") if procedure_col else "").strip()
        if not procedure or is_header_like(procedure):
            continue
        record = {
            "city": city,
            "source_pdf": source_pdf,
            "source_page": str(raw.get("source_page", "")).strip(),
            "procedure_name": procedure,
            "nabh_rate": normalize_rate(raw.get(nabh_col, "") if nabh_col else ""),
            "non_nabh_rate": normalize_rate(raw.get(non_nabh_col, "") if non_nabh_col else ""),
            "cghs_rate": normalize_rate(raw.get(cghs_col, "") if cghs_col else ""),
            "rate_type": "",
            "remarks": str(raw.get("Remarks", raw.get("remarks", ""))).strip(),
            "extraction_method": "pdfplumber",
            "needs_manual_review": False,
        }
        if not has_valid_rate(record):
            continue
        if is_messy_procedure(record["procedure_name"]):
            continue
        record["quality_status"] = "clean"
        rows.append(record)
    return rows


def normalize_master_row(row: pd.Series) -> dict[str, Any]:
    return {
        "city": normalize_city(row.get("city_folder", "")),
        "source_pdf": str(row.get("source_pdf", "")).strip(),
        "source_page": str(row.get("source_page", "")).strip(),
        "procedure_name": re.sub(r"\s+", " ", str(row.get("procedure_name", ""))).strip(),
        "nabh_rate": normalize_rate(row.get("nabh_rate")),
        "non_nabh_rate": normalize_rate(row.get("non_nabh_rate")),
        "cghs_rate": normalize_rate(row.get("cghs_rate")),
        "rate_type": str(row.get("rate_type", "")).strip().lower(),
        "remarks": re.sub(r"\s+", " ", str(row.get("remarks", ""))).strip(),
        "extraction_method": str(row.get("extraction_method", "")).strip().lower(),
        "needs_manual_review": parse_bool(row.get("needs_manual_review")),
        "raw_text_line": str(row.get("raw_text_line", "")).strip(),
        "extraction_confidence": str(row.get("extraction_confidence", "")).strip(),
    }


def classify_row(row: dict[str, Any]) -> tuple[bool, str, str]:
    """Return (keep_for_app, quality_status, review_reason)."""
    method = row.get("extraction_method", "")
    procedure = row.get("procedure_name", "")
    reasons: list[str] = []

    if not procedure:
        reasons.append("missing_procedure_name")
    elif is_header_like(procedure):
        reasons.append("header_like_procedure")
    elif is_messy_procedure(procedure):
        reasons.append("messy_procedure")

    if not has_valid_rate(row):
        reasons.append("missing_or_invalid_rate")

    if method == "ocr":
        if row.get("needs_manual_review"):
            reasons.append("ocr_flagged_manual_review")
        try:
            confidence = float(row.get("extraction_confidence") or 0)
            if confidence < 0.7:
                reasons.append("low_ocr_confidence")
        except ValueError:
            reasons.append("invalid_ocr_confidence")

    if method == "pdfplumber":
        if reasons:
            return False, "needs_manual_review", "; ".join(reasons)
        return True, "clean", ""

    # OCR path
    if reasons:
        return False, "needs_manual_review", "; ".join(reasons)
    return True, "usable_ocr", ""


def load_pdfplumber_rows_from_sources(converted_root: Path) -> pd.DataFrame:
    ocr_root = converted_root / "ocr_converted"
    frames: list[pd.DataFrame] = []
    for csv_path in sorted(converted_root.rglob("*.csv")):
        if csv_path.name in {
            "conversion_log.csv",
            "ocr_conversion_log.csv",
            "cghs_all_cities_combined.csv",
            "cghs_all_cities_combined_full.csv",
            "cghs_all_cities_cleaned_for_app.csv",
            "cghs_ocr_rows_needing_review.csv",
            "cghs_cleaning_summary.csv",
            "cghs_conversion_validation_report.csv",
        }:
            continue
        if ocr_root in csv_path.parents:
            continue
        rows = rows_from_pdfplumber_csv(csv_path)
        if rows:
            frames.append(pd.DataFrame(rows))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def dedupe_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    subset = [
        "city",
        "source_pdf",
        "source_page",
        "procedure_name",
        "nabh_rate",
        "non_nabh_rate",
        "cghs_rate",
        "extraction_method",
    ]
    return df.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)


def build_summary(
    *,
    total_before: int,
    clean_df: pd.DataFrame,
    review_df: pd.DataFrame,
    pdfplumber_kept: int,
    ocr_kept: int,
) -> pd.DataFrame:
    cities_clean = sorted(clean_df["city"].dropna().unique()) if not clean_df.empty else []
    city_stats: list[dict[str, Any]] = []
    all_cities = sorted(set(clean_df["city"]) | set(review_df["city"])) if not clean_df.empty or not review_df.empty else []
    for city in all_cities:
        clean_count = len(clean_df[clean_df["city"] == city]) if not clean_df.empty else 0
        review_count = len(review_df[review_df["city"] == city]) if not review_df.empty else 0
        total = clean_count + review_count
        ocr_review = 0
        if not review_df.empty:
            ocr_review = len(
                review_df[
                    (review_df["city"] == city)
                    & (review_df["extraction_method"] == "ocr")
                ]
            )
        mostly_manual = ""
        if total > 0 and review_count / total >= 0.6:
            mostly_manual = "yes"
        city_stats.append(
            {
                "metric": f"city::{city}",
                "value": total,
                "details": (
                    f"clean={clean_count}; review={review_count}; "
                    f"ocr_in_review={ocr_review}; mostly_manual_review={mostly_manual or 'no'}"
                ),
            }
        )

    summary_rows = [
        {"metric": "total_rows_before_cleaning", "value": total_before, "details": ""},
        {"metric": "total_clean_rows", "value": len(clean_df), "details": ""},
        {"metric": "total_pdfplumber_rows_kept", "value": pdfplumber_kept, "details": ""},
        {"metric": "total_ocr_rows_kept", "value": ocr_kept, "details": ""},
        {"metric": "total_rows_moved_to_manual_review", "value": len(review_df), "details": ""},
        {"metric": "cities_covered_in_clean_file", "value": len(cities_clean), "details": ", ".join(cities_clean)},
        {
            "metric": "ready_for_app_integration",
            "value": "yes" if len(clean_df) > 0 else "no",
            "details": "Use cleaned file only; review file is not for automatic matching",
        },
    ]
    return pd.DataFrame(summary_rows + city_stats)


def run_cleaning(converted_root: Path) -> dict[str, Any]:
    full_path = converted_root / "cghs_all_cities_combined_full.csv"
    master = pd.read_csv(
        full_path,
        dtype=str,
        engine="python",
        on_bad_lines="skip",
    ).fillna("")
    total_before = len(master)

    pdfplumber_clean = load_pdfplumber_rows_from_sources(converted_root)
    ocr_master = master[master["extraction_method"].str.lower() == "ocr"].copy()

    clean_records: list[dict[str, Any]] = []
    review_records: list[dict[str, Any]] = []

    invalid_pdfplumber_from_master = 0
    for _, raw in master[master["extraction_method"].str.lower() == "pdfplumber"].iterrows():
        row = normalize_master_row(raw)
        keep, quality, reason = classify_row(row)
        if not keep:
            invalid_pdfplumber_from_master += 1
            row["quality_status"] = quality
            row["review_reason"] = reason or "invalid_pdfplumber_master_row"
            review_records.append(row)

    for _, raw in ocr_master.iterrows():
        row = normalize_master_row(raw)
        keep, quality, reason = classify_row(row)
        row["quality_status"] = quality
        if keep:
            clean_records.append({key: row.get(key, "") for key in OUTPUT_COLUMNS})
        else:
            row["review_reason"] = reason or "ocr_review_required"
            review_records.append(row)

    if not pdfplumber_clean.empty:
        pdfplumber_clean = dedupe_rows(pdfplumber_clean)
        for record in pdfplumber_clean.to_dict(orient="records"):
            clean_records.append({key: record.get(key, "") for key in OUTPUT_COLUMNS})

    clean_df = pd.DataFrame(clean_records, columns=OUTPUT_COLUMNS)
    clean_df = dedupe_rows(clean_df)

    review_df = pd.DataFrame(review_records)
    if not review_df.empty:
        review_cols = [
            "city",
            "source_pdf",
            "source_page",
            "procedure_name",
            "nabh_rate",
            "non_nabh_rate",
            "cghs_rate",
            "rate_type",
            "remarks",
            "extraction_method",
            "needs_manual_review",
            "quality_status",
            "review_reason",
            "raw_text_line",
            "extraction_confidence",
        ]
        for col in review_cols:
            if col not in review_df.columns:
                review_df[col] = ""
        review_df = review_df[review_cols].drop_duplicates().reset_index(drop=True)

    clean_path = converted_root / "cghs_all_cities_cleaned_for_app.csv"
    review_path = converted_root / "cghs_ocr_rows_needing_review.csv"
    summary_path = converted_root / "cghs_cleaning_summary.csv"

    clean_df.to_csv(clean_path, index=False)
    review_df.to_csv(review_path, index=False)

    pdfplumber_kept = len(clean_df[clean_df["extraction_method"] == "pdfplumber"]) if not clean_df.empty else 0
    ocr_kept = len(clean_df[clean_df["extraction_method"] == "ocr"]) if not clean_df.empty else 0

    summary_df = build_summary(
        total_before=total_before,
        clean_df=clean_df,
        review_df=review_df,
        pdfplumber_kept=pdfplumber_kept,
        ocr_kept=ocr_kept,
    )
    summary_df.to_csv(summary_path, index=False)

    return {
        "total_before": total_before,
        "clean_rows": len(clean_df),
        "review_rows": len(review_df),
        "pdfplumber_kept": pdfplumber_kept,
        "ocr_kept": ocr_kept,
        "invalid_pdfplumber_master_rows": invalid_pdfplumber_from_master,
        "clean_path": str(clean_path),
        "review_path": str(review_path),
        "summary_path": str(summary_path),
        "cities_clean": sorted(clean_df["city"].unique()) if not clean_df.empty else [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean CGHS master CSV for app integration")
    parser.add_argument("--converted-root", type=Path, default=DEFAULT_CONVERTED_ROOT)
    args = parser.parse_args(argv)

    summary = run_cleaning(args.converted_root.resolve())

    print("\n=== CGHS Cleaning Summary ===")
    print(f"Total rows in full master CSV:     {summary['total_before']}")
    print(f"Total rows in cleaned app CSV:     {summary['clean_rows']}")
    print(f"Total rows needing manual review:  {summary['review_rows']}")
    print(f"Pdfplumber rows kept:              {summary['pdfplumber_kept']}")
    print(f"OCR rows kept:                     {summary['ocr_kept']}")
    print(f"Cleaned CSV:                       {summary['clean_path']}")
    print(f"Review CSV:                        {summary['review_path']}")
    print(f"Summary CSV:                       {summary['summary_path']}")
    print(f"Cities in cleaned file:            {len(summary['cities_clean'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
