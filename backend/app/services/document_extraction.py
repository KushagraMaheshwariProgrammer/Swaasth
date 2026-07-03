"""OCR and Groq-based extraction for bills and prescriptions."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime
from io import BytesIO
from typing import Any

import fitz
import pytesseract
from fastapi import HTTPException
from PIL import Image

from app.services.groq_client import groq_json_chat
from app.services.json_utils import extract_json_from_text

_tess = shutil.which("tesseract")
if _tess:
    TESSERACT_PATH = _tess
elif sys.platform == "darwin":
    TESSERACT_PATH = "/opt/homebrew/bin/tesseract"
else:
    TESSERACT_PATH = "/usr/bin/tesseract"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

_AI_ERROR_HINT = (
    " If the document is the wrong type, set the is_* flag to false, set "
    "detected_document_type to the best matching type from: bill, prescription, "
    "lab_report, discharge_summary, preauth_letter, and set error to a short "
    "patient-friendly explanation (for example, 'This looks like a prescription, "
    "not a hospital bill.'). Never use HTTP status phrases like 'Bad Request'."
)

_LAB_REPORT_SCOPE = (
    "A lab report is any diagnostic test-results document that lists test names with "
    "measured values, units, reference ranges, or qualitative results (positive, "
    "negative, reactive, detected, etc.). This includes pathology, biochemistry, "
    "hematology, microbiology, serology, urine routine and microscopy, PSA, semen "
    "analysis, kidney function panels, and urology or other specialty clinic lab "
    "printouts. Do not reject a report because it is from urology, nephrology, or "
    "another specialty—if it contains test results, treat it as a lab report."
)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid PDF file.") from exc

    pages_text = [page.get_text("text") for page in doc]
    return "\n".join(pages_text).strip()


def extract_text_from_image(file_bytes: bytes) -> str:
    try:
        image = Image.open(BytesIO(file_bytes))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid image file.") from exc

    try:
        return pytesseract.image_to_string(image).strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Tesseract is not installed on this machine. "
                "Please install Tesseract OCR and try again."
            ),
        ) from exc


def extract_document_text(file_bytes: bytes, file_type: str) -> str:
    if file_type == "pdf":
        return extract_text_from_pdf(file_bytes)
    return extract_text_from_image(file_bytes)


_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%m/%d/%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d %b %Y",
    "%d %B %Y",
    "%d %b %y",
    "%d %B %y",
)


def normalize_document_date(value: str | None) -> str | None:
    """Best-effort ISO date (YYYY-MM-DD) from OCR or AI strings."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", raw)
    if match:
        return match.group(1)
    return None


def extract_bill_date_from_text(text: str) -> str | None:
    """Best-effort bill-date extraction from raw OCR text."""
    if not text:
        return None
    patterns = [
        r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\b",
        r"\b(\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2})\b",
        r"\b(\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{2,4})\b",
    ]
    for line in text.splitlines():
        if re.search(r"date", line, re.IGNORECASE):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    return normalize_document_date(match.group(1))
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_document_date(match.group(1))
    return None


def resolve_document_date(
    *,
    ai_date: str | None = None,
    ocr_text: str | None = None,
) -> str | None:
    """Prefer AI-extracted dates, then regex on OCR text."""
    normalized = normalize_document_date(ai_date)
    if normalized:
        return normalized
    if ocr_text:
        return extract_bill_date_from_text(ocr_text)
    return None


def _groq_chat(system: str, user: str, *, max_tokens: int = 2000) -> dict[str, Any]:
    return groq_json_chat(system, user, max_tokens=max_tokens)


def extract_bill_with_groq(extracted_text: str) -> dict[str, Any]:
    system = (
        "You are helping extract hospital bill line items for Indian patients. "
        "Return ONLY valid JSON with keys: is_medical_bill, error, hospital_name, "
        "bill_date, line_items. bill_date is the bill or invoice date in YYYY-MM-DD "
        "when visible; otherwise null. "
        "Each line item has item_name, quantity, unit_price, total_price, category "
        "(medicine|test|procedure|other). Keep numeric fields as numbers."
        f"{_AI_ERROR_HINT}"
    )
    user = f"Bill text:\n{extracted_text}"
    return _groq_chat(system, user)


def extract_prescription_with_groq(extracted_text: str) -> dict[str, Any]:
    system = (
        "You are helping extract prescription details for Indian patients. "
        "Return ONLY valid JSON with keys: is_prescription, error, diagnosis, "
        "diagnosis_confidence (high|low|missing), prescriber, prescription_date, "
        "medicines, tests, procedures, symptoms. "
        "If diagnosis is absent or unclear, set diagnosis=null and diagnosis_confidence=missing."
        f"{_AI_ERROR_HINT}"
    )
    user = f"Prescription text:\n{extracted_text}"
    return _groq_chat(system, user)


def extract_lab_report_with_groq(extracted_text: str) -> dict[str, Any]:
    system = (
        "You are helping extract laboratory and diagnostic test results for Indian "
        "patients. "
        f"{_LAB_REPORT_SCOPE} "
        "Return ONLY valid JSON with keys: is_lab_report, error, lab_name, report_date, "
        "test_results. Each test_results entry has test_name, value, unit, "
        "reference_range, and result (positive/negative/normal/abnormal/high/low when "
        "applicable). Set is_lab_report=true whenever the document primarily contains "
        "extractable test results. Only set is_lab_report=false when the document is "
        "clearly not a test-results report (for example a prescription, bill, discharge "
        "summary, or pre-authorization letter)."
        f"{_AI_ERROR_HINT}"
    )
    user = f"Lab report text:\n{extracted_text}"
    return normalize_lab_report_extraction(_groq_chat(system, user))


def extract_discharge_summary_with_groq(extracted_text: str) -> dict[str, Any]:
    system = (
        "You are helping extract discharge summary details for Indian patients. "
        "Return ONLY valid JSON with keys: is_discharge_summary, error, diagnosis, "
        "discharge_date, symptoms, test_results, procedures. "
        "discharge_date is the admission or discharge date in YYYY-MM-DD when visible; "
        "otherwise null."
        f"{_AI_ERROR_HINT}"
    )
    user = f"Discharge summary text:\n{extracted_text}"
    return _groq_chat(system, user)


VALID_DOCUMENT_TYPES = frozenset(
    {
        "bill",
        "prescription",
        "lab_report",
        "discharge_summary",
        "preauth_letter",
    }
)


def classify_document_with_groq(extracted_text: str) -> dict[str, Any]:
    system = (
        "You classify Indian medical documents. Return ONLY valid JSON with keys: "
        "document_type, confidence, error. "
        "document_type must be exactly one of: bill, prescription, lab_report, "
        "discharge_summary, preauth_letter. "
        "bill = hospital invoice or receipt with charges and line items. "
        "prescription = doctor prescription with medicines, tests, or procedures ordered. "
        "lab_report = pathology, diagnostic laboratory, or specialty clinic test results "
        "(including urology urine analysis, PSA, semen analysis, and similar reports). "
        "discharge_summary = hospital inpatient discharge note with admission or discharge details. "
        "preauth_letter = insurance, TPA, or government scheme pre-authorization or "
        "cashless approval letter. "
        "Set confidence to high when the document clearly matches one type; "
        "set confidence to low when the text is ambiguous, too short, illegible, "
        "or could reasonably match more than one type."
    )
    user = f"Document text:\n{extracted_text[:8000]}"
    return _groq_chat(system, user, max_tokens=300)


def normalize_detected_document_type(value: Any) -> str | None:
    doc_type = str(value or "").strip().lower()
    return doc_type if doc_type in VALID_DOCUMENT_TYPES else None


def normalize_document_classification(payload: dict[str, Any]) -> dict[str, Any]:
    doc_type = str(payload.get("document_type") or "bill").strip().lower()
    if doc_type not in VALID_DOCUMENT_TYPES:
        doc_type = "bill"
    confidence = str(payload.get("confidence") or "low").lower()
    if confidence not in {"high", "low"}:
        confidence = "low"
    return {
        "document_type": doc_type,
        "confidence": confidence,
        "error": payload.get("error"),
    }


def extract_preauth_with_groq(extracted_text: str) -> dict[str, Any]:
    system = (
        "You are helping extract insurance or government-scheme pre-authorization "
        "details for Indian patients. Return ONLY valid JSON with keys: "
        "is_preauth, error, authorization_id, authorization_date, insurer_or_scheme, "
        "hospital_name, patient_name, approved_amount, package_name, approved_items. "
        "authorization_date is the letter date in YYYY-MM-DD when visible; otherwise null. "
        "approved_items is an array of {name, approved_amount, notes}. "
        "Keep approved_amount numeric when visible; otherwise null."
        f"{_AI_ERROR_HINT}"
    )
    user = f"Pre-authorization or claim approval text:\n{extracted_text}"
    return _groq_chat(system, user)


VALID_TEST_RESULTS = {
    "positive",
    "negative",
    "normal",
    "abnormal",
    "high",
    "low",
    None,
}


def normalize_lab_report_extraction(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept lab reports when Groq extracted test results but misclassified the type."""
    test_results = _normalize_test_results(payload.get("test_results") or [])
    is_lab_report = bool(payload.get("is_lab_report", False))
    if not is_lab_report and test_results:
        return {
            **payload,
            "is_lab_report": True,
            "error": None,
            "test_results": test_results,
        }
    return {**payload, "test_results": test_results}


def _normalize_symptoms(items: list[Any]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(
            {
                "name": name,
                "duration": str(item.get("duration") or "").strip() or None,
                "severity": str(item.get("severity") or "").strip() or None,
            }
        )
    return cleaned


def _normalize_test_results(items: list[Any]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        test_name = str(item.get("test_name") or item.get("name") or "").strip()
        if not test_name:
            continue
        key = test_name.lower()
        if key in seen:
            continue
        seen.add(key)
        result = item.get("result")
        if result is not None:
            result = str(result).strip().lower() or None
            if result not in VALID_TEST_RESULTS:
                result = None
        value = item.get("value")
        if value is not None:
            value = str(value).strip() or None
        unit = item.get("unit")
        if unit is not None:
            unit = str(unit).strip() or None
        reference_range = item.get("reference_range")
        if reference_range is not None:
            reference_range = str(reference_range).strip() or None
        cleaned.append(
            {
                "test_name": test_name,
                "value": value,
                "unit": unit,
                "result": result,
                "reference_range": reference_range,
            }
        )
    return cleaned


def normalize_clinical_context(
    *,
    symptoms: list[Any] | None = None,
    test_results: list[Any] | None = None,
    symptoms_source: str = "manual",
    test_results_source: str = "manual",
) -> dict[str, Any]:
    return {
        "symptoms": _normalize_symptoms(symptoms or []),
        "test_results": _normalize_test_results(test_results or []),
        "symptoms_source": symptoms_source,
        "test_results_source": test_results_source,
    }


def merge_clinical_contexts(
    *contexts: dict[str, Any],
    manual_symptoms: list[Any] | None = None,
    manual_test_results: list[Any] | None = None,
) -> dict[str, Any]:
    """Merge clinical contexts; manual entries override extracted duplicates."""
    symptoms: list[dict[str, Any]] = []
    test_results: list[dict[str, Any]] = []
    symptoms_source = "manual"
    test_results_source = "manual"

    for ctx in contexts:
        if not ctx:
            continue
        symptoms.extend(ctx.get("symptoms") or [])
        test_results.extend(ctx.get("test_results") or [])
        if ctx.get("symptoms"):
            symptoms_source = ctx.get("symptoms_source") or symptoms_source
        if ctx.get("test_results"):
            test_results_source = ctx.get("test_results_source") or test_results_source

    if manual_symptoms:
        symptoms = list(manual_symptoms) + symptoms
        symptoms_source = "manual"
    if manual_test_results:
        test_results = list(manual_test_results) + test_results
        test_results_source = "manual"

    return normalize_clinical_context(
        symptoms=symptoms,
        test_results=test_results,
        symptoms_source=symptoms_source,
        test_results_source=test_results_source,
    )


def normalize_prescription_items(payload: dict[str, Any]) -> dict[str, Any]:
    medicines = payload.get("medicines") or []
    tests = payload.get("tests") or []
    procedures = payload.get("procedures") or []

    def _clean_name_list(items: list[Any], key: str = "name") -> list[dict[str, str]]:
        cleaned: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get(key, "")).strip()
            if not name:
                continue
            cleaned.append({key: name, **{k: v for k, v in item.items() if k != key}})
        return cleaned

    diagnosis = payload.get("diagnosis")
    if diagnosis is not None:
        diagnosis = str(diagnosis).strip() or None

    confidence = str(payload.get("diagnosis_confidence") or "missing").lower()
    if confidence not in {"high", "low", "missing"}:
        confidence = "missing"

    return {
        "is_prescription": bool(payload.get("is_prescription", False)),
        "error": payload.get("error"),
        "diagnosis": diagnosis,
        "diagnosis_confidence": confidence,
        "prescriber": payload.get("prescriber"),
        "prescription_date": payload.get("prescription_date"),
        "medicines": _clean_name_list(medicines if isinstance(medicines, list) else []),
        "tests": _clean_name_list(tests if isinstance(tests, list) else []),
        "procedures": _clean_name_list(
            procedures if isinstance(procedures, list) else []
        ),
        "clinical_context": normalize_clinical_context(
            symptoms=payload.get("symptoms") or [],
            test_results=[],
            symptoms_source="prescription",
            test_results_source="manual",
        ),
    }
