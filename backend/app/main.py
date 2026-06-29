import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from app.report_routes import router as report_router
from app.cghs_rates import resolve_hospital_type, resolve_tier
from app.locations import get_location_store
from app.nabh_registry import get_nabh_registry
from app.jan_aushadhi_rates import get_jan_aushadhi_store
from app.medicine_comparison import enrich_scheme_line_items_with_jan_aushadhi
from app.pharma_rates import get_pharma_store
from app.prescription_routes import router as prescription_router
from app.services.claim_audit import analyze_claim_items
from app.services.document_extraction import (
    extract_bill_with_groq,
    extract_document_text,
    extract_json_from_text,
    normalize_clinical_context,
)
from app.restricted_medicines import build_restricted_medicine_flags, get_restricted_medicines_store
from app.services.treatment_audit import analyze_treatment


_BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_ROOT / ".env")

logger = logging.getLogger(__name__)


def _dev_logging_enabled() -> bool:
    return os.getenv("ENV", "").lower() in {"dev", "development", "local"}

app = FastAPI(title="MedBill Backend")

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://localhost",
    "capacitor://localhost",
    "https://swaasth.in",
    "https://www.swaasth.in",
]


def _cors_origins() -> list[str]:
    extra = os.getenv("CORS_ORIGINS", "")
    origins = list(_DEFAULT_CORS_ORIGINS)
    for origin in extra.split(","):
        origin = origin.strip()
        if origin and origin not in origins:
            origins.append(origin)
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(report_router)
app.include_router(prescription_router)


@app.on_event("startup")
def load_reference_data() -> None:
    try:
        locations = get_location_store()
        city_count = sum(
            len(cities) for cities in locations.cities_by_state_ut.values()
        )
        print(
            f"Loaded {len(locations.state_ut_names)} states/UTs and {city_count} cities "
            f"from {locations.directory_path.name}"
        )
    except Exception as exc:
        print(f"WARNING: Location directories failed to load: {exc}")

    try:
        nabh = get_nabh_registry()
        print(f"Loaded {len(nabh.records)} NABH registry hospitals from {nabh.csv_path}")
    except Exception as exc:
        print(f"WARNING: NABH registry failed to load: {exc}")

    try:
        from app.pharma_rates import get_pharma_store

        pharma = get_pharma_store()
        az_count = len(pharma.az.rows) if pharma.az else 0
        print(
            f"Loaded {len(pharma.nppa.rows)} NPPA ceiling prices "
            f"from {pharma.nppa.csv_path}"
        )
        if az_count:
            print(
                f"Loaded {az_count} brand-to-generic mappings "
                f"from {pharma.az.csv_path}"
            )
        else:
            print(
                "WARNING: AZ brand dataset not loaded (brand resolution disabled). "
                "Run: python backend/scripts/download_pharma_backup_dataset.py"
            )
    except Exception as exc:
        print(f"WARNING: NPPA price dataset failed to load: {exc}")

    try:
        jan_aushadhi = get_jan_aushadhi_store()
        print(
            f"Loaded {len(jan_aushadhi.rows)} Jan Aushadhi products "
            f"from {jan_aushadhi.csv_path}"
        )
    except Exception as exc:
        print(f"WARNING: Jan Aushadhi product list failed to load: {exc}")

    try:
        restricted = get_restricted_medicines_store()
        if restricted.is_available():
            print(
                f"Loaded {len(restricted.rows)} restricted medicines "
                f"from {restricted.csv_path}"
            )
        else:
            print(
                f"WARNING: Restricted medicines CSV not loaded "
                f"(expected at {restricted.csv_path})"
            )
    except Exception as exc:
        print(f"WARNING: Restricted medicines catalog failed to load: {exc}")


@app.get("/health")
def health_check() -> str:
    return "Backend is running"


@app.get("/api/locations/states")
def list_states() -> list[str]:
    try:
        return get_location_store().get_state_ut_names()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Location data is unavailable: {exc}",
        ) from exc


@app.get("/locations/states")
def list_states_legacy() -> dict[str, list[dict[str, str]]]:
    """Legacy shape for older frontends: { states: [{ code, name }] }."""
    try:
        return {"states": get_location_store().get_states()}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Location data is unavailable: {exc}",
        ) from exc


@app.get("/api/locations/cities")
def list_cities(
    state: str = Query(..., description="State/UT name from /api/locations/states"),
) -> list[str]:
    try:
        store = get_location_store()
        city_names = store.get_city_names(state)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Location data is unavailable: {exc}",
        ) from exc

    if not city_names:
        raise HTTPException(
            status_code=404,
            detail=f"No cities found for state '{state}'.",
        )

    return city_names


@app.get("/locations/cities")
def list_cities_legacy(
    state_code: str = Query(..., description="State code from /locations/states"),
) -> dict[str, list[dict[str, str]]]:
    """Legacy shape for older frontends: { cities: [{ name, tier_id, ... }] }."""
    try:
        store = get_location_store()
        state_ut_name = store.get_state_ut_name_by_code(state_code)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Location data is unavailable: {exc}",
        ) from exc

    if not state_ut_name:
        raise HTTPException(
            status_code=404,
            detail=f"No cities found for state_code '{state_code}'.",
        )

    cities = store.get_cities(state_ut_name)
    if not cities:
        raise HTTPException(
            status_code=404,
            detail=f"No cities found for state_code '{state_code}'.",
        )

    return {"cities": cities}


@app.get("/api/locations/tier")
def resolve_city_tier(
    state: str = Query(..., description="State/UT name from /api/locations/states"),
    city: str = Query(..., description="City name from /api/locations/cities"),
) -> dict[str, str]:
    try:
        return get_location_store().resolve_tier(state, city)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Location data is unavailable: {exc}",
        ) from exc


def _resolve_comparison_tier(
    *,
    tier: str | None,
    state_ut_name: str | None,
    city: str | None,
) -> tuple[str, dict[str, Any]]:
    location_meta: dict[str, Any] = {}

    if state_ut_name and city:
        try:
            resolved = get_location_store().resolve_tier(state_ut_name, city)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        location_meta = {
            "state_code": resolved["state_code"],
            "state_ut_name": resolved["state_ut_name"],
            "state_name": resolved["state_name"],
            "city": resolved["city_name"],
            "tier_id": resolved["tier_id"],
            "tier_label": resolved["tier_label"],
            "tier_source": resolved["tier_source"],
        }
        return resolve_tier(resolved["tier_id"]), location_meta

    if tier:
        return resolve_tier(tier), location_meta

    raise HTTPException(
        status_code=400,
        detail="Provide state_ut_name and city, or an explicit tier.",
    )


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    return extract_document_text(file_bytes, "pdf")


def _extract_text_from_image(file_bytes: bytes) -> str:
    return extract_document_text(file_bytes, "jpeg")


def _extract_json_from_text(raw_text: str) -> dict[str, Any]:
    return extract_json_from_text(raw_text)


def _analyze_bill_text_with_groq(extracted_text: str) -> dict[str, Any]:
    return extract_bill_with_groq(extracted_text)


def _resolve_nabh_lookup(hospital_name: str | None) -> dict[str, Any]:
    nabh_lookup: dict[str, Any] = {
        "hospital_name": hospital_name or "",
        "is_accredited": False,
        "accreditation_status": None,
        "matched_registry_name": None,
        "accreditation_number": None,
        "approximate_match": False,
        "match_score": 0.0,
    }

    if hospital_name and hospital_name.strip():
        try:
            nabh_lookup = get_nabh_registry().lookup(hospital_name)
        except Exception:
            pass

    return nabh_lookup


def _add_price_comparison(line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from app.medicine_comparison import (
        compare_line_item_with_nppa,
        should_use_nppa_result,
    )

    compared: list[dict[str, Any]] = []
    for raw_item in line_items:
        item = dict(raw_item)
        pharma_item = compare_line_item_with_nppa(item)
        if should_use_nppa_result(item, pharma_item):
            compared.append(pharma_item)
            continue
        item["comparison_source"] = None
        item["price_difference"] = None
        item["flag"] = "no_reference"
        item["matched_reference_item"] = None
        item["approximate_match"] = False
        compared.append(item)
    return compared


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class BillLineItemInput(BaseModel):
    item_name: str = ""
    quantity: float = Field(default=1, ge=0)
    unit_price: float = Field(default=0, ge=0)
    total_price: float = Field(default=0, ge=0)
    category: str = "other"


def _resolve_state_ut_name(
    *,
    state_ut_name: str | None,
    state_code: str | None,
) -> str:
    if state_ut_name and state_ut_name.strip():
        return state_ut_name.strip()
    if state_code and state_code.strip():
        resolved = get_location_store().get_state_ut_name_by_code(state_code)
        if resolved:
            return resolved
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state_code '{state_code}'.",
        )
    raise HTTPException(
        status_code=400,
        detail="Provide state_ut_name or state_code.",
    )


class PrescriptionItemInput(BaseModel):
    name: str = ""
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None
    category: str | None = None


class SymptomInput(BaseModel):
    name: str = ""
    duration: str | None = None
    severity: str | None = None


class TestResultInput(BaseModel):
    test_name: str = ""
    value: str | None = None
    unit: str | None = None
    result: str | None = None
    reference_range: str | None = None


class CompareBillRequest(BaseModel):
    line_items: list[BillLineItemInput]
    state_ut_name: str | None = None
    state_code: str | None = None
    city: str
    hospital_type: str = "general"
    hospital_name: str | None = None
    tier: str | None = None
    filename: str | None = None
    file_type: str | None = None
    bill_date: str | None = None
    patient_district: str | None = None
    patient_id: str | None = None
    patient_name: str | None = None
    patient_age: int | None = None
    patient_gender: str | None = None
    diagnosis: str | None = None
    diagnosis_user_provided: bool = False
    prescription_medicines: list[PrescriptionItemInput] = Field(default_factory=list)
    prescription_tests: list[PrescriptionItemInput] = Field(default_factory=list)
    prescription_procedures: list[PrescriptionItemInput] = Field(default_factory=list)
    symptoms: list[SymptomInput] = Field(default_factory=list)
    test_results: list[TestResultInput] = Field(default_factory=list)
    ocr_text: str | None = None

    @model_validator(mode="after")
    def resolve_state(self) -> "CompareBillRequest":
        self.state_ut_name = _resolve_state_ut_name(
            state_ut_name=self.state_ut_name,
            state_code=self.state_code,
        )
        return self


def _normalize_line_items(line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed_categories = {"medicine", "test", "procedure", "other"}
    normalized: list[dict[str, Any]] = []

    for item in line_items:
        category = str(item.get("category", "other")).strip().lower()
        if category not in allowed_categories:
            category = "other"

        quantity = max(_to_float(item.get("quantity")), 0.0)
        unit_price = max(_to_float(item.get("unit_price")), 0.0)
        total_price = _to_float(item.get("total_price"))
        if total_price <= 0 and quantity > 0 and unit_price > 0:
            total_price = round(quantity * unit_price, 2)

        normalized.append(
            {
                "item_name": str(item.get("item_name", "")).strip(),
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "category": category,
            }
        )

    return normalized


def _prescription_items_from_request(
    medicines: list[PrescriptionItemInput],
    tests: list[PrescriptionItemInput],
    procedures: list[PrescriptionItemInput],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in medicines:
        name = entry.name.strip()
        if name:
            items.append({"name": name, "category": "medicine"})
    for entry in tests:
        name = entry.name.strip()
        if name:
            items.append({"name": name, "category": "test"})
    for entry in procedures:
        name = entry.name.strip()
        if name:
            items.append({"name": name, "category": "procedure"})
    return items


def _clinical_context_from_request(
    symptoms: list[SymptomInput],
    test_results: list[TestResultInput],
) -> dict[str, Any]:
    return normalize_clinical_context(
        symptoms=[item.model_dump() for item in symptoms if item.name.strip()],
        test_results=[
            {
                "test_name": item.test_name,
                "value": item.value,
                "unit": item.unit,
                "result": item.result,
                "reference_range": item.reference_range,
            }
            for item in test_results
            if item.test_name.strip()
        ],
        symptoms_source="manual",
        test_results_source="manual",
    )


def _build_comparison_response(
    *,
    line_items: list[dict[str, Any]],
    state_ut_name: str,
    city: str,
    hospital_type: str,
    hospital_name: str | None,
    tier: str | None = None,
    filename: str = "edited-bill",
    file_type: str = "manual",
    bill_date: str | None = None,
    patient_district: str | None = None,
    patient_id: str | None = None,
    patient_name: str | None = None,
    patient_age: int | None = None,
    patient_gender: str | None = None,
    diagnosis: str | None = None,
    diagnosis_user_provided: bool = False,
    prescription_items: list[dict[str, Any]] | None = None,
    clinical_context: dict[str, Any] | None = None,
    report_kind: str = "bill",
    ocr_text: str | None = None,
) -> dict[str, Any]:
    if not line_items:
        raise HTTPException(status_code=400, detail="Add at least one line item.")

    canonical_tier, location_meta = _resolve_comparison_tier(
        tier=tier,
        state_ut_name=state_ut_name,
        city=city,
    )
    canonical_hospital_type = resolve_hospital_type(hospital_type)
    nabh_lookup = _resolve_nabh_lookup(hospital_name)

    normalized_items = _normalize_line_items(line_items)
    compared_line_items = _add_price_comparison(normalized_items)
    compared_line_items, jan_aushadhi = enrich_scheme_line_items_with_jan_aushadhi(
        compared_line_items
    )

    audit_flags = analyze_claim_items(
        compared_line_items,
        city=location_meta.get("city", city),
    )

    treatment_audit_flags: dict[str, Any] | None = None
    prescription_payload: dict[str, Any] | None = None
    clinical_context = clinical_context or {}
    if diagnosis and diagnosis.strip():
        prescription_items = prescription_items or []
        treatment_audit_flags = analyze_treatment(
            diagnosis=diagnosis.strip(),
            prescription_items=prescription_items,
            bill_items=compared_line_items,
            clinical_context=clinical_context,
            diagnosis_user_provided=diagnosis_user_provided,
        )
        if prescription_items or clinical_context:
            prescription_payload = {
                "diagnosis": diagnosis.strip(),
                "diagnosis_user_provided": diagnosis_user_provided,
                "medicines": [
                    item for item in prescription_items if item.get("category") == "medicine"
                ],
                "tests": [
                    item for item in prescription_items if item.get("category") == "test"
                ],
                "procedures": [
                    item
                    for item in prescription_items
                    if item.get("category") == "procedure"
                ],
            }

    rates_source: dict[str, Any] = {"comparison_scheme": "general"}
    try:
        from app.pharma_rates import get_pharma_store

        pharma_store = get_pharma_store()
        rates_source["nppa_file"] = str(pharma_store.nppa.csv_path.name)
        rates_source["total_nppa_entries"] = len(pharma_store.nppa.rows)
        if pharma_store.az:
            rates_source["az_brand_file"] = str(pharma_store.az.csv_path.name)
            rates_source["az_brand_index_size"] = len(pharma_store.az.rows)
        else:
            rates_source["az_brand_file"] = None
            rates_source["az_brand_index_size"] = 0
    except Exception:
        rates_source["nppa_file"] = None
        rates_source["total_nppa_entries"] = 0
        rates_source["az_brand_file"] = None
        rates_source["az_brand_index_size"] = 0
    try:
        jan_aushadhi_store = get_jan_aushadhi_store()
        rates_source["jan_aushadhi_file"] = str(jan_aushadhi_store.csv_path.name)
        rates_source["total_jan_aushadhi_products"] = len(jan_aushadhi_store.rows)
    except Exception:
        rates_source["jan_aushadhi_file"] = None
        rates_source["total_jan_aushadhi_products"] = 0

    patient_payload: dict[str, Any] | None = None
    if patient_id or patient_name:
        patient_payload = {
            "id": patient_id,
            "name": patient_name,
            "age": patient_age,
            "gender": patient_gender,
        }

    restricted_medicine_flags = build_restricted_medicine_flags(
        ocr_text=ocr_text,
        line_items=compared_line_items,
        prescription_items=prescription_items or [],
    )

    return {
        "filename": filename,
        "file_type": file_type,
        "message": "Comparison completed",
        "hospital": {
            "name_from_bill": hospital_name,
            **nabh_lookup,
        },
        "comparison_settings": {
            "tier": canonical_tier,
            "tier_id": location_meta.get("tier_id", tier),
            "tier_label": location_meta.get("tier_label"),
            "tier_source": location_meta.get("tier_source"),
            "state_code": location_meta.get("state_code"),
            "state_ut_name": location_meta.get("state_ut_name", state_ut_name),
            "state_name": location_meta.get("state_name", state_ut_name),
            "city": location_meta.get("city", city),
            "hospital_type": canonical_hospital_type,
            "comparison_scheme": "general",
        },
        "patient": patient_payload,
        "rates_source": rates_source,
        "line_items": compared_line_items,
        "jan_aushadhi": jan_aushadhi,
        "audit_flags": audit_flags,
        "treatment_audit_flags": treatment_audit_flags,
        "prescription": prescription_payload,
        "clinical_context": clinical_context if clinical_context else None,
        "report_kind": report_kind,
        "restricted_medicine_flags": restricted_medicine_flags,
    }


@app.post("/compare-bill")
def compare_bill(body: CompareBillRequest) -> dict[str, Any]:
    try:
        resolve_hospital_type(body.hospital_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    line_items = [item.model_dump() for item in body.line_items]
    prescription_items = _prescription_items_from_request(
        body.prescription_medicines,
        body.prescription_tests,
        body.prescription_procedures,
    )
    report_kind = (
        "combined"
        if body.diagnosis and (prescription_items or body.symptoms or body.test_results)
        else "bill"
    )
    clinical_context = _clinical_context_from_request(body.symptoms, body.test_results)
    if _dev_logging_enabled():
        logger.info(
            "POST /compare-bill: items=%d state=%s city=%s hospital=%s",
            len(line_items),
            body.state_ut_name,
            body.city,
            body.hospital_name,
        )
    return _build_comparison_response(
        line_items=line_items,
        state_ut_name=body.state_ut_name,
        city=body.city,
        hospital_type=body.hospital_type,
        hospital_name=body.hospital_name,
        tier=body.tier,
        filename=body.filename or "edited-bill",
        file_type=body.file_type or "manual",
        bill_date=body.bill_date,
        patient_district=body.patient_district,
        patient_id=body.patient_id,
        patient_name=body.patient_name,
        patient_age=body.patient_age,
        patient_gender=body.patient_gender,
        diagnosis=body.diagnosis,
        diagnosis_user_provided=body.diagnosis_user_provided,
        prescription_items=prescription_items,
        clinical_context=clinical_context,
        report_kind=report_kind,
        ocr_text=body.ocr_text,
    )


@app.post("/upload-bill")
async def upload_bill(
    file: UploadFile = File(...),
    state_ut_name: str | None = Query(
        default=None,
        description="State/UT name where the hospital is located",
    ),
    state_code: str | None = Query(
        default=None,
        description="Legacy state code from /locations/states",
    ),
    city: str = Query(
        ...,
        description="City where the hospital is located",
    ),
    hospital_type: str = Query(
        ...,
        description="Hospital type: general or speciality",
    ),
    tier: str | None = Query(
        default=None,
        description="Optional manual tier override (tier_1, tier_2, tier_3)",
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
        resolved_state_ut_name = _resolve_state_ut_name(
            state_ut_name=state_ut_name,
            state_code=state_code,
        )
        canonical_tier, location_meta = _resolve_comparison_tier(
            tier=tier,
            state_ut_name=resolved_state_ut_name,
            city=city,
        )
        resolve_hospital_type(hospital_type)
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

    hospital_name = ai_result.get("hospital_name")
    if hospital_name is not None:
        hospital_name = str(hospital_name).strip() or None

    nabh_lookup = _resolve_nabh_lookup(hospital_name)
    canonical_hospital_type = resolve_hospital_type(hospital_type)

    normalized_items = _normalize_line_items(line_items)

    return {
        "filename": file.filename or "unknown",
        "file_type": file_type,
        "message": "Bill extracted successfully",
        "hospital": {
            "name_from_bill": hospital_name,
            **nabh_lookup,
        },
        "comparison_settings": {
            "tier": canonical_tier,
            "tier_id": location_meta.get("tier_id", tier),
            "tier_label": location_meta.get("tier_label"),
            "tier_source": location_meta.get("tier_source"),
            "state_code": location_meta.get("state_code"),
            "state_ut_name": location_meta.get("state_ut_name", resolved_state_ut_name),
            "state_name": location_meta.get("state_name", resolved_state_ut_name),
            "city": location_meta.get("city", city),
            "hospital_type": canonical_hospital_type,
        },
        "line_items": normalized_items,
        "ocr_text": extracted_text,
    }


def _extract_bill_date(text: str) -> str | None:
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
                    return match.group(1)
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None
