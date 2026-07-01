"""OCR and Groq-based extraction for bills and prescriptions."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
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

GROQ_MODEL = "llama-3.3-70b-versatile"


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


def _groq_chat(system: str, user: str, *, max_tokens: int = 2000) -> dict[str, Any]:
    return groq_json_chat(system, user, max_tokens=max_tokens)


def extract_bill_with_groq(extracted_text: str) -> dict[str, Any]:
    system = (
        "You are helping extract hospital bill line items for Indian patients. "
        "Return ONLY valid JSON with keys: is_medical_bill, error, hospital_name, line_items. "
        "Each line item has item_name, quantity, unit_price, total_price, category "
        "(medicine|test|procedure|other). Keep numeric fields as numbers."
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
    )
    user = f"Prescription text:\n{extracted_text}"
    return _groq_chat(system, user)


def extract_lab_report_with_groq(extracted_text: str) -> dict[str, Any]:
    system = (
        "You are helping extract laboratory test results for Indian patients. "
        "Return ONLY valid JSON with keys: is_lab_report, error, lab_name, report_date, "
        "test_results. Use result=positive/negative for antigen/antibody/microscopy results."
    )
    user = f"Lab report text:\n{extracted_text}"
    return _groq_chat(system, user)


def extract_discharge_summary_with_groq(extracted_text: str) -> dict[str, Any]:
    system = (
        "You are helping extract discharge summary details for Indian patients. "
        "Return ONLY valid JSON with keys: is_discharge_summary, error, diagnosis, "
        "symptoms, test_results, procedures."
    )
    user = f"Discharge summary text:\n{extracted_text}"
    return _groq_chat(system, user)


def extract_preauth_with_groq(extracted_text: str) -> dict[str, Any]:
    system = (
        "You are helping extract insurance or government-scheme pre-authorization "
        "details for Indian patients. Return ONLY valid JSON with keys: "
        "is_preauth, error, authorization_id, insurer_or_scheme, hospital_name, "
        "patient_name, approved_amount, package_name, approved_items. "
        "approved_items is an array of {name, approved_amount, notes}. "
        "Keep approved_amount numeric when visible; otherwise null."
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
