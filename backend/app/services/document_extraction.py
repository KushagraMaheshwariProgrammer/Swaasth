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
  "procedures": [{{ "name": "string" }}]
}}

Rules:
- If diagnosis is absent, unclear, or only implied, set diagnosis=null and diagnosis_confidence="missing".
- If diagnosis is explicit, set diagnosis_confidence="high" or "low".
- Include advised lab tests, imaging, and procedures separately in tests/procedures arrays.
- Keep medicine names as written on the prescription.
- If text is not a prescription, set is_prescription=false and provide error.

Prescription text:
{extracted_text}
"""
    return _groq_chat(prompt)


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
    }
