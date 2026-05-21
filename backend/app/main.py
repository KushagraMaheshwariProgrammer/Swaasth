import json
import os
import re
from io import BytesIO
from typing import Any

import fitz
import pytesseract
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from PIL import Image

from app.cghs_rates import (
    get_cghs_store,
    resolve_rate_type,
    resolve_tier,
)


load_dotenv()

TESSERACT_PATH = "/opt/homebrew/bin/tesseract"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

app = FastAPI(title="MedBill Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def load_cghs_rates() -> None:
    try:
        store = get_cghs_store()
        print(
            f"Loaded {len(store.rows)} CGHS rates from {store.csv_path} "
            f"({len(store.tiers)} tiers)"
        )
    except Exception as exc:
        print(f"WARNING: CGHS rates CSV failed to load: {exc}")


@app.get("/health")
def health_check() -> str:
    return "Backend is running"


@app.get("/cghs/options")
def cghs_options() -> dict[str, Any]:
    try:
        store = get_cghs_store()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"CGHS rates data is unavailable: {exc}",
        ) from exc

    return {
        "tiers": [
            {"id": "tier_1", "label": "Tier I (X City)", "value": store.tiers[0] if store.tiers else ""},
            {"id": "tier_2", "label": "Tier II (Y City)", "value": store.tiers[1] if len(store.tiers) > 1 else ""},
            {"id": "tier_3", "label": "Tier III (Z City)", "value": store.tiers[2] if len(store.tiers) > 2 else ""},
        ],
        "rate_types": [
            {"id": "non_nabh", "label": "Non-NABH hospital"},
            {"id": "nabh", "label": "NABH accredited hospital"},
            {"id": "super_speciality", "label": "Super speciality rate"},
        ],
        "total_procedures": len(store.rows),
        "csv_source": str(store.csv_path),
    }


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid PDF file.") from exc

    pages_text: list[str] = []
    for page in doc:
        pages_text.append(page.get_text("text"))

    return "\n".join(pages_text).strip()


def _extract_text_from_image(file_bytes: bytes) -> str:
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


def _extract_json_from_text(raw_text: str) -> dict[str, Any]:
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


def _analyze_bill_text_with_groq(extracted_text: str) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not set in the environment.",
        )

    client = Groq(api_key=api_key)

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
- If unsure quantity/unit_price, infer reasonably from bill text.
- Keep numeric fields as numbers (not strings).
- category must be one of: medicine, test, procedure, other.
- If text is not a medical bill, set is_medical_bill=false and provide error.

Bill text:
{extracted_text}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=2000,
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

    parsed = _extract_json_from_text(response_text)
    return parsed


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _add_cghs_comparison(
    line_items: list[dict[str, Any]],
    *,
    tier: str,
    rate_type: str,
) -> list[dict[str, Any]]:
    try:
        store = get_cghs_store()
        canonical_tier = resolve_tier(tier)
        canonical_rate_type = resolve_rate_type(rate_type)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    compared_items: list[dict[str, Any]] = []

    for item in line_items:
        item_name = str(item.get("item_name", "")).strip()
        total_price = _to_float(item.get("total_price"))
        match = store.find_match(
            item_name, tier=canonical_tier, rate_type=canonical_rate_type
        )

        if match is None:
            item["cghs_rate"] = None
            item["price_difference"] = None
            item["flag"] = "no_reference"
            item["matched_reference_item"] = None
            item["approximate_match"] = False
            item["cghs_code"] = None
            item["tier"] = canonical_tier
            item["rate_type"] = canonical_rate_type
            item["non_nabh_rate"] = None
            item["nabh_rate"] = None
            item["super_speciality_rate"] = None
            item["speciality_classification"] = None
        else:
            cghs_rate = _to_float(match["rate"])
            price_difference = round(total_price - cghs_rate, 2)
            item["cghs_rate"] = cghs_rate
            item["price_difference"] = price_difference
            item["flag"] = "overpriced" if price_difference > 0 else "acceptable"
            item["matched_reference_item"] = match["reference_item"]
            item["approximate_match"] = bool(match["approximate_match"])
            item["cghs_code"] = match["cghs_code"]
            item["tier"] = match["tier"]
            item["rate_type"] = match["rate_type"]
            item["non_nabh_rate"] = match["non_nabh_rate"]
            item["nabh_rate"] = match["nabh_rate"]
            item["super_speciality_rate"] = match["super_speciality_rate"]
            item["speciality_classification"] = match["speciality_classification"]

        compared_items.append(item)

    return compared_items


@app.post("/upload-bill")
async def upload_bill(
    file: UploadFile = File(...),
    tier: str = Query(
        default="tier_1",
        description="City tier: tier_1, tier_2, or tier_3",
    ),
    rate_type: str = Query(
        default="nabh",
        description="Rate column: non_nabh, nabh, or super_speciality",
    ),
) -> dict[str, Any]:
    allowed_types = {
        "application/pdf": "pdf",
        "image/jpeg": "jpeg",
        "image/png": "png",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Allowed types: pdf, jpg, jpeg, png.",
        )

    try:
        canonical_tier = resolve_tier(tier)
        canonical_rate_type = resolve_rate_type(rate_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    file_type = allowed_types[file.content_type]

    if file_type == "pdf":
        extracted_text = _extract_text_from_pdf(file_bytes)
    else:
        extracted_text = _extract_text_from_image(file_bytes)

    if not extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No readable text found in the uploaded file.",
        )

    ai_result = _analyze_bill_text_with_groq(extracted_text)
    is_medical_bill = ai_result.get("is_medical_bill", False)
    if not is_medical_bill:
        raise HTTPException(
            status_code=400,
            detail=ai_result.get(
                "error", "Uploaded document does not appear to be a medical bill."
            ),
        )

    line_items = ai_result.get("line_items", [])
    if not isinstance(line_items, list):
        line_items = []

    compared_line_items = _add_cghs_comparison(
        line_items, tier=canonical_tier, rate_type=canonical_rate_type
    )

    store = get_cghs_store()

    return {
        "filename": file.filename or "unknown",
        "file_type": file_type,
        "message": "File received successfully",
        "comparison_settings": {
            "tier": canonical_tier,
            "tier_id": tier,
            "rate_type": canonical_rate_type,
        },
        "rates_source": {
            "file": str(store.csv_path.name),
            "total_procedures_loaded": len(store.rows),
        },
        "line_items": compared_line_items,
    }
