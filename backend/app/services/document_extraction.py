"""OCR and Groq-based extraction for bills and prescriptions."""

from __future__ import annotations

import json
import os
import re
from io import BytesIO
from typing import Any

import fitz
import pytesseract
from fastapi import HTTPException
from groq import Groq
from PIL import Image

TESSERACT_PATH = "/opt/homebrew/bin/tesseract"
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


def extract_json_from_text(raw_text: str) -> dict[str, Any]:
    cleaned_text = raw_text.strip()
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned_text, re.DOTALL)
        if not match:
            raise HTTPException(
                status_code=500,
                detail="Groq returned an invalid response format.",
            )
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=500,
                detail="Groq returned malformed JSON.",
            ) from exc


def _groq_chat(prompt: str, *, max_tokens: int = 2000) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not set in the environment.",
        )

    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Groq API request failed: {str(exc)}",
        ) from exc

    response_text = (response.choices[0].message.content or "").strip()
    if not response_text:
        raise HTTPException(status_code=502, detail="Groq returned an empty response.")
    return extract_json_from_text(response_text)


def extract_bill_with_groq(extracted_text: str) -> dict[str, Any]:
    prompt = f"""
You are helping extract hospital bill line items for Indian patients.

Task:
1) Decide if the text looks like a medical/hospital bill.
2) If yes, extract line items into structured JSON.
3) If no, return an error message.

Return ONLY valid JSON with this exact shape:
{{
  "is_medical_bill": true or false,
  "error": null or "reason text",
  "hospital_name": null or "string",
  "line_items": [
    {{
      "item_name": "string",
      "quantity": number,
      "unit_price": number,
      "total_price": number,
      "category": "medicine" | "test" | "procedure" | "other"
    }}
  ]
}}

Rules:
- Extract the hospital or healthcare provider name from the bill header if present.
- If unsure quantity/unit_price, infer reasonably from bill text.
- Keep numeric fields as numbers (not strings).
- category must be one of: medicine, test, procedure, other.
- If text is not a medical bill, set is_medical_bill=false and provide error.

Bill text:
{extracted_text}
"""
    return _groq_chat(prompt)


def extract_prescription_with_groq(extracted_text: str) -> dict[str, Any]:
    prompt = f"""
You are helping extract prescription details for Indian patients.

Task:
1) Decide if the text looks like a medical prescription or doctor's order.
2) If yes, extract structured prescription data.
3) If no, return an error message.

Return ONLY valid JSON with this exact shape:
{{
  "is_prescription": true or false,
  "error": null or "reason text",
  "diagnosis": null or "string",
  "diagnosis_confidence": "high" | "low" | "missing",
  "prescriber": null or "string",
  "prescription_date": null or "string",
  "medicines": [
    {{
      "name": "string",
      "dose": null or "string",
      "frequency": null or "string",
      "duration": null or "string"
    }}
  ],
  "tests": [{{ "name": "string" }}],
  "procedures": [{{ "name": "string" }}],
  "symptoms": [
    {{
      "name": "string",
      "duration": null or "string",
      "severity": null or "string"
    }}
  ]
}}

Rules:
- If diagnosis is absent, unclear, or only implied, set diagnosis=null and diagnosis_confidence="missing".
- If diagnosis is explicit, set diagnosis_confidence="high" or "low".
- Include advised lab tests, imaging, and procedures separately in tests/procedures arrays.
- Extract symptoms if mentioned on the prescription (chief complaints, clinical notes).
- Keep medicine names as written on the prescription.
- If text is not a prescription, set is_prescription=false and provide error.

Prescription text:
{extracted_text}
"""
    return _groq_chat(prompt)


    return _groq_chat(prompt)


def extract_lab_report_with_groq(extracted_text: str) -> dict[str, Any]:
    prompt = f"""
You are helping extract laboratory test results for Indian patients.

Task:
1) Decide if the text looks like a medical lab report or investigation report.
2) If yes, extract structured test results.
3) If no, return an error message.

Return ONLY valid JSON with this exact shape:
{{
  "is_lab_report": true or false,
  "error": null or "reason text",
  "lab_name": null or "string",
  "report_date": null or "string",
  "test_results": [
    {{
      "test_name": "string",
      "value": null or "string",
      "unit": null or "string",
      "result": "positive" | "negative" | "normal" | "abnormal" | "high" | "low" | null,
      "reference_range": null or "string"
    }}
  ]
}}

Rules:
- Extract all reported investigations with values or qualitative results.
- Use result=positive/negative for antigen/antibody/microscopy style results when stated.
- If text is not a lab report, set is_lab_report=false and provide error.

Lab report text:
{extracted_text}
"""
    return _groq_chat(prompt)


def extract_discharge_summary_with_groq(extracted_text: str) -> dict[str, Any]:
    prompt = f"""
You are helping extract discharge summary details for Indian patients.

Task:
1) Decide if the text looks like a hospital discharge summary or clinical note.
2) If yes, extract diagnosis, symptoms, test results, and procedures.
3) If no, return an error message.

Return ONLY valid JSON with this exact shape:
{{
  "is_discharge_summary": true or false,
  "error": null or "reason text",
  "diagnosis": null or "string",
  "symptoms": [
    {{ "name": "string", "duration": null or "string", "severity": null or "string" }}
  ],
  "test_results": [
    {{
      "test_name": "string",
      "value": null or "string",
      "unit": null or "string",
      "result": "positive" | "negative" | "normal" | "abnormal" | "high" | "low" | null,
      "reference_range": null or "string"
    }}
  ],
  "procedures": [{{ "name": "string" }}]
}}

Rules:
- Extract final or provisional diagnosis if present.
- Include presenting symptoms and significant investigation results from the summary.
- If text is not a discharge summary, set is_discharge_summary=false and provide error.

Discharge summary text:
{extracted_text}
"""
    return _groq_chat(prompt)


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
