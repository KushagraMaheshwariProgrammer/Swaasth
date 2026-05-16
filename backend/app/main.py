import json
import os
import re
from difflib import SequenceMatcher
from io import BytesIO
from typing import Any

import fitz
import pytesseract
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from PIL import Image


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

CGHS_REFERENCE_RATES: dict[str, float] = {
    # Room and bed charges
    "general ward bed charges": 1500.0,
    "semi private room charges": 2500.0,
    "private room charges": 4000.0,
    "deluxe room charges": 5500.0,
    "super deluxe room charges": 7000.0,
    "icu bed charges": 7500.0,
    "nicu bed charges": 8000.0,
    "hdu bed charges": 6000.0,
    "day care bed charges": 1200.0,
    "isolation room charges": 5000.0,
    "attendant bed charges": 700.0,
    "admission charges": 600.0,
    "discharge charges": 400.0,
    "file opening charges": 150.0,
    "room shifting charges": 500.0,
    "bed transfer charges": 350.0,
    "hospital service charges": 500.0,
    "ward consumables charges": 450.0,
    "linen charges": 250.0,
    "sanitization charges": 300.0,
    # Nursing and monitoring
    "nursing charges day": 900.0,
    "nursing charges night": 1000.0,
    "special nursing charges": 1800.0,
    "rmo charges": 900.0,
    "duty doctor charges": 850.0,
    "doctor visit charges": 700.0,
    "consultant visit charges": 1200.0,
    "senior consultant visit charges": 1800.0,
    "resident doctor charges": 750.0,
    "monitoring charges": 600.0,
    "cardiac monitoring charges": 850.0,
    "pulse oximeter monitoring": 250.0,
    "central monitoring charges": 700.0,
    # Laboratory hematology
    "complete blood count cbc": 350.0,
    "hemoglobin": 120.0,
    "total leukocyte count": 150.0,
    "differential leukocyte count": 180.0,
    "platelet count": 180.0,
    "esr": 140.0,
    "peripheral smear": 220.0,
    "reticulocyte count": 250.0,
    "bleeding time": 120.0,
    "clotting time": 120.0,
    "blood grouping": 180.0,
    "rh typing": 120.0,
    "cross matching": 450.0,
    "coombs test": 500.0,
    # Coagulation and cardiac labs
    "prothrombin time pt": 220.0,
    "international normalized ratio inr": 180.0,
    "pt inr": 300.0,
    "aptt": 260.0,
    "d dimer": 1200.0,
    "troponin i": 1400.0,
    "troponin t": 1400.0,
    "ck mb": 700.0,
    "bnp": 1800.0,
    "serum lactate": 500.0,
    # Biochemistry profile
    "liver function test lft": 700.0,
    "kidney function test kft": 650.0,
    "blood sugar fasting": 120.0,
    "blood sugar post prandial": 130.0,
    "random blood sugar": 120.0,
    "hba1c": 500.0,
    "lipid profile": 800.0,
    "thyroid profile": 900.0,
    "t3": 300.0,
    "t4": 300.0,
    "tsh": 350.0,
    "serum electrolytes": 500.0,
    "sodium": 180.0,
    "potassium": 180.0,
    "chloride": 180.0,
    "calcium": 200.0,
    "phosphorus": 220.0,
    "magnesium": 220.0,
    "serum creatinine": 140.0,
    "blood urea": 120.0,
    "uric acid": 140.0,
    "bilirubin total": 180.0,
    "bilirubin direct": 160.0,
    "sgot ast": 180.0,
    "sgpt alt": 180.0,
    "alkaline phosphatase alp": 220.0,
    "albumin": 180.0,
    "globulin": 180.0,
    "total protein": 220.0,
    "amylase": 250.0,
    "lipase": 320.0,
    "serum iron": 300.0,
    "ferritin": 650.0,
    "vitamin b12": 900.0,
    "vitamin d": 1200.0,
    "crp": 400.0,
    "procalcitonin": 1800.0,
    "ldh": 350.0,
    # Urine and stool
    "urine routine": 180.0,
    "urine microscopy": 180.0,
    "urine culture sensitivity": 700.0,
    "24 hour urine protein": 350.0,
    "stool routine": 220.0,
    "stool culture sensitivity": 750.0,
    "occult blood stool": 250.0,
    # Serology and microbiology
    "hiv 1 2": 500.0,
    "hbsag": 450.0,
    "hcv": 500.0,
    "vdrl": 250.0,
    "dengue ns1": 700.0,
    "dengue igm": 700.0,
    "malaria antigen": 450.0,
    "widal typhoid": 280.0,
    "pregnancy test urine": 200.0,
    "beta hcg": 750.0,
    "psa": 900.0,
    "covid rt pcr": 700.0,
    "influenza antigen": 450.0,
    "blood culture sensitivity": 900.0,
    "sputum culture sensitivity": 850.0,
    "pus culture sensitivity": 800.0,
    # Imaging and diagnostics
    "ecg": 250.0,
    "2d echo": 1800.0,
    "tmt": 2000.0,
    "holter monitoring": 2500.0,
    "eeg": 1800.0,
    "emg": 2200.0,
    "x ray chest": 500.0,
    "x ray abdomen": 550.0,
    "x ray knee": 500.0,
    "x ray spine": 700.0,
    "x ray pelvis": 600.0,
    "x ray skull": 550.0,
    "x ray hand": 450.0,
    "x ray foot": 450.0,
    "x ray cervical spine": 700.0,
    "x ray lumbosacral spine": 750.0,
    "x ray pns": 650.0,
    "ultrasound abdomen": 1200.0,
    "ultrasound pelvis": 1100.0,
    "ultrasound obstetric": 1300.0,
    "ultrasound thyroid": 1000.0,
    "ultrasound breast": 1200.0,
    "ultrasound doppler venous": 1800.0,
    "ultrasound doppler arterial": 2000.0,
    "ct scan head plain": 3000.0,
    "ct scan chest": 3800.0,
    "ct scan abdomen": 4200.0,
    "ct scan pelvis": 3800.0,
    "ct angiography": 6500.0,
    "hrct chest": 4500.0,
    "mri brain": 6000.0,
    "mri spine": 7000.0,
    "mri knee": 6500.0,
    "mri shoulder": 6500.0,
    "mri cervical spine": 7000.0,
    "mri lumbosacral spine": 7000.0,
    "mri abdomen": 8500.0,
    "pet ct scan": 20000.0,
    "mammography": 2200.0,
    "dexa scan": 1800.0,
    "fibroscan": 2500.0,
    # Procedures and OT
    "minor ot charges": 2500.0,
    "major ot charges": 9000.0,
    "laparoscopy": 14000.0,
    "appendectomy": 25000.0,
    "c section": 35000.0,
    "normal delivery package": 18000.0,
    "angiography": 12000.0,
    "angioplasty": 65000.0,
    "endoscopy upper gi": 4500.0,
    "colonoscopy": 6500.0,
    "bronchoscopy": 7000.0,
    "dialysis session": 2800.0,
    "hemodialysis with consumables": 3500.0,
    "peritoneal dialysis": 5000.0,
    "chemotherapy administration": 4500.0,
    "radiotherapy session": 3500.0,
    "physiotherapy session": 600.0,
    "nebulization": 300.0,
    "dressing charges": 400.0,
    "advanced dressing charges": 700.0,
    "suturing charges": 600.0,
    "stitch removal": 250.0,
    "catheterization": 1200.0,
    "foley catheter insertion": 900.0,
    "iv cannula": 250.0,
    "central line insertion": 3500.0,
    "arterial line insertion": 2500.0,
    "blood transfusion": 1800.0,
    "tracheostomy care": 1800.0,
    "intubation charges": 1500.0,
    "extubation charges": 1000.0,
    "plaster cast application": 1200.0,
    "fracture reduction closed": 8000.0,
    "fracture reduction open": 20000.0,
    "wound debridement": 2500.0,
    "incision and drainage": 2000.0,
    "biopsy procedure": 3500.0,
    "lumbar puncture": 2500.0,
    "bone marrow aspiration": 4500.0,
    "vaccination administration": 250.0,
    # Professional and surgical fees
    "surgeon fee minor": 6000.0,
    "surgeon fee major": 15000.0,
    "assistant surgeon fee": 7000.0,
    "anaesthetist fee": 6500.0,
    "consultant fee": 1200.0,
    "specialist consultation": 1500.0,
    "super specialist consultation": 2000.0,
    "pre anesthetic checkup": 800.0,
    "post operative visit": 900.0,
    "oncologist consultation": 1800.0,
    "cardiologist consultation": 1800.0,
    "neurologist consultation": 1800.0,
    "orthopedic consultation": 1500.0,
    "gynaecologist consultation": 1500.0,
    "pediatrician consultation": 1400.0,
    # Support and consumables
    "ambulance local": 1500.0,
    "ambulance with oxygen": 2200.0,
    "oxygen charges": 500.0,
    "high flow oxygen charges": 1200.0,
    "ventilator charges": 2500.0,
    "bipap cpap charges": 1800.0,
    "monitor charges": 700.0,
    "syringe pump charges": 600.0,
    "infusion pump charges": 500.0,
    "defibrillator use charges": 1500.0,
    "ppe kit": 350.0,
    "n95 mask": 40.0,
    "gloves pair": 15.0,
    "surgical gown": 120.0,
    "pharmacy dispensing charges": 250.0,
    "drug administration charges": 300.0,
    "injection administration charges": 200.0,
    "consumables charges": 500.0,
    "disposable charges": 350.0,
    "sterilization charges": 350.0,
    "biomedical waste charges": 150.0,
    "diet charges": 300.0,
    "high protein diet charges": 450.0,
    "medical records charges": 200.0,
    "certificate charges": 250.0,
    "teleconsultation charges": 700.0,
    "home care nursing visit": 1200.0,
    # Frequently seen package/service variants
    "icu nursing charges": 2000.0,
    "nicu nursing charges": 2200.0,
    "hdu nursing charges": 1600.0,
    "emergency registration charges": 300.0,
    "emergency consultation charges": 1200.0,
    "emergency procedure charges": 2500.0,
    "triage charges": 250.0,
    "bedside procedure charges": 1200.0,
    "recovery room charges": 2200.0,
    "post op monitoring charges": 1200.0,
    "operation theatre sterilization charges": 800.0,
    "anesthesia drugs charges": 1800.0,
    "surgical consumables ot": 2500.0,
    "laparoscopy instruments charges": 3500.0,
    "dialysis consumables charges": 900.0,
    "chemotherapy daycare charges": 2200.0,
    "blood bank processing charges": 1000.0,
    "transfusion set charges": 200.0,
    "crossmatch repeat charges": 300.0,
    "sample collection charges": 120.0,
    "home sample collection charges": 250.0,
    "stat lab processing charges": 250.0,
    "weekend surcharge": 500.0,
    "night emergency surcharge": 800.0,
}

TERM_ALIASES: dict[str, str] = {
    "complete blood count": "cbc",
    "complete hemogram": "cbc",
    "liver function test": "lft",
    "kidney function test": "kft",
    "renal function test": "kft",
    "erythrocyte sedimentation rate": "esr",
    "electrocardiogram": "ecg",
    "electroencephalogram": "eeg",
    "ultrasonography": "ultrasound",
    "usg": "ultrasound",
    "magnetic resonance imaging": "mri",
    "computed tomography": "ct scan",
    "operation theatre": "ot",
    "operation theater": "ot",
    "international normalized ratio": "inr",
    "activated partial thromboplastin time": "aptt",
    "prothrombin time": "pt",
    "glycated hemoglobin": "hba1c",
    "thyroid function test": "thyroid profile",
    "urine routine examination": "urine routine",
    "urine routine microscopy": "urine routine",
    "culture and sensitivity": "culture sensitivity",
    "xray": "x ray",
}


@app.get("/health")
def health_check() -> str:
    return "Backend is running"


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


def _normalize_item_name(item_name: str) -> str:
    normalized = item_name.lower().strip()
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = normalized.replace("&", " and ").replace("/", " ")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)

    for source, target in TERM_ALIASES.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)

    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


NORMALIZED_REFERENCE_INDEX: list[tuple[str, str, float, set[str]]] = [
    (
        item_name,
        _normalize_item_name(item_name),
        rate,
        set(_normalize_item_name(item_name).split()),
    )
    for item_name, rate in CGHS_REFERENCE_RATES.items()
]

NORMALIZED_TO_REFERENCE: dict[str, tuple[str, float]] = {
    normalized_name: (original_name, rate)
    for original_name, normalized_name, rate, _ in NORMALIZED_REFERENCE_INDEX
}


def _find_cghs_match(item_name: str) -> dict[str, Any] | None:
    normalized_name = _normalize_item_name(item_name)
    if not normalized_name:
        return None

    direct_match = NORMALIZED_TO_REFERENCE.get(normalized_name)
    if direct_match:
        matched_name, matched_rate = direct_match
        return {
            "reference_item": matched_name,
            "rate": matched_rate,
            "approximate_match": False,
        }

    for original_name, reference_normalized, reference_rate, _ in NORMALIZED_REFERENCE_INDEX:
        if (
            reference_normalized in normalized_name
            or normalized_name in reference_normalized
        ):
            return {
                "reference_item": original_name,
                "rate": reference_rate,
                "approximate_match": False,
            }

    best_match: tuple[float, str, float] | None = None
    input_tokens = set(normalized_name.split())
    for original_name, reference_normalized, reference_rate, reference_tokens in (
        NORMALIZED_REFERENCE_INDEX
    ):
        if not reference_tokens or not input_tokens:
            continue

        overlap_score = len(input_tokens & reference_tokens) / len(
            input_tokens | reference_tokens
        )
        sequence_score = SequenceMatcher(
            None, normalized_name, reference_normalized
        ).ratio()
        score = (0.6 * overlap_score) + (0.4 * sequence_score)

        if best_match is None or score > best_match[0]:
            best_match = (score, original_name, reference_rate)

    if best_match and best_match[0] >= 0.52:
        _, matched_name, matched_rate = best_match
        return {
            "reference_item": matched_name,
            "rate": matched_rate,
            "approximate_match": True,
        }

    return None


def _add_cghs_comparison(line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compared_items: list[dict[str, Any]] = []

    for item in line_items:
        item_name = str(item.get("item_name", "")).strip()
        total_price = _to_float(item.get("total_price"))
        match = _find_cghs_match(item_name)

        if match is None:
            item["cghs_rate"] = None
            item["price_difference"] = None
            item["flag"] = "no_reference"
            item["matched_reference_item"] = None
            item["approximate_match"] = False
        else:
            cghs_rate = _to_float(match["rate"])
            price_difference = round(total_price - cghs_rate, 2)
            item["cghs_rate"] = cghs_rate
            item["price_difference"] = price_difference
            item["flag"] = "overpriced" if price_difference > 0 else "acceptable"
            item["matched_reference_item"] = match["reference_item"]
            item["approximate_match"] = bool(match["approximate_match"])

        compared_items.append(item)

    return compared_items


@app.post("/upload-bill")
async def upload_bill(file: UploadFile = File(...)) -> dict[str, Any]:
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

    compared_line_items = _add_cghs_comparison(line_items)

    return {
        "filename": file.filename or "unknown",
        "file_type": file_type,
        "message": "File received successfully",
        "line_items": compared_line_items,
    }
