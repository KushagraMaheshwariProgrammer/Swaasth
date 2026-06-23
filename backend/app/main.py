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

from app.aarogya_bhadratha import get_aarogya_store
from app.aarogya_routes import router as aarogya_router
from app.report_routes import router as report_router
from app.cghs_rates import (
    get_cghs_store,
    resolve_hospital_type,
    resolve_rate_type,
    resolve_rate_type_for_hospital,
    resolve_tier,
)
from app.hbp_rates import get_hbp_store
from app.locations import get_location_store
from app.nabh_registry import get_nabh_registry
from app.jan_aushadhi_rates import enrich_line_items_with_jan_aushadhi, get_jan_aushadhi_store
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
    return os.getenv("ENV", "").lower() in {"dev", "development", "local"} or os.getenv(
        "RAJIV_AAROGYASRI_DEBUG", ""
    ).lower() in {"1", "true", "yes"}

app = FastAPI(title="MedBill Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "https://localhost",
        "capacitor://localhost",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(aarogya_router)
app.include_router(report_router)
app.include_router(prescription_router)


@app.on_event("startup")
def load_reference_data() -> None:
    try:
        store = get_cghs_store()
        print(
            f"Loaded {len(store.rows)} CGHS rates from {store.csv_path} "
            f"({len(store.tiers)} tiers)"
        )
    except Exception as exc:
        print(f"WARNING: CGHS rates CSV failed to load: {exc}")

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
        hbp = get_hbp_store()
        print(
            f"Loaded {len(hbp.rows)} HBP 2022 PM-JAY rates from {hbp.csv_path}"
        )
    except Exception as exc:
        print(f"WARNING: HBP 2022 rates CSV failed to load: {exc}")

    try:
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
        aarogya = get_aarogya_store()
        print(
            f"Loaded {len(aarogya.hospitals)} Aarogya Bhadratha hospitals "
            f"({len(aarogya.list_districts())} districts) and "
            f"{len(aarogya.rates)} rate rows"
        )
    except Exception as exc:
        print(f"WARNING: Aarogya Bhadratha data failed to load: {exc}")

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

    try:
        from app.rajiv_aarogyasri import get_rajiv_aarogyasri_store

        rajiv = get_rajiv_aarogyasri_store()
        print(
            f"Loaded {len(rajiv.hospitals)} Rajiv Aarogyasri hospitals and "
            f"{len(rajiv.packages)} packages from {rajiv.data_dir.name}"
        )
    except Exception as exc:
        print(f"WARNING: Rajiv Aarogyasri data failed to load: {exc}")


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
        "hospital_types": [
            {"id": "general", "label": "General hospital"},
            {"id": "speciality", "label": "Speciality hospital"},
        ],
        "total_procedures": len(store.rows),
        "csv_source": str(store.csv_path),
    }


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


def _rate_type_label(rate_type: str) -> str:
    labels = {
        "nabh": "NABH rate (accredited)",
        "non_nabh": "Non-NABH rate (not accredited)",
        "super_speciality": "Super speciality rate",
    }
    return labels.get(rate_type, rate_type)


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _add_pharma_comparison(line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        store = get_pharma_store()
    except (FileNotFoundError, ValueError) as exc:
        fallback: list[dict[str, Any]] = []
        for raw_item in line_items:
            item = dict(raw_item)
            item["comparison_source"] = "pharma"
            item["pharma_rate"] = None
            item["price_difference"] = None
            item["flag"] = "no_reference"
            item["matched_reference_item"] = None
            item["approximate_match"] = False
            item["pharma_error"] = str(exc)
            fallback.append(item)
        return fallback

    return [store.compare_line_item(dict(raw_item)) for raw_item in line_items]


def _add_hbp_comparison(
    line_items: list[dict[str, Any]],
    *,
    tier_id: str,
) -> list[dict[str, Any]]:
    try:
        store = get_hbp_store()
    except (FileNotFoundError, ValueError) as exc:
        fallback: list[dict[str, Any]] = []
        for raw_item in line_items:
            item = dict(raw_item)
            item["comparison_source"] = "hbp"
            item["hbp_rate"] = None
            item["price_difference"] = None
            item["flag"] = "no_reference"
            item["matched_reference_item"] = None
            item["approximate_match"] = False
            item["hbp_error"] = str(exc)
            fallback.append(item)
        return fallback

    compared_items: list[dict[str, Any]] = []
    for raw_item in line_items:
        item = dict(raw_item)
        item["comparison_source"] = "hbp"
        item_name = str(item.get("item_name", "")).strip()
        total_price = _to_float(item.get("total_price"))
        match = store.find_match(item_name, tier_id=tier_id)

        if match is None:
            item["hbp_rate"] = None
            item["price_difference"] = None
            item["flag"] = "no_reference"
            item["matched_reference_item"] = None
            item["approximate_match"] = False
            item["hbp_procedure_code"] = None
            item["hbp_package_code"] = None
            item["hbp_package_name"] = None
        else:
            hbp_rate = _to_float(match["rate"])
            price_difference = round(total_price - hbp_rate, 2)
            item["hbp_rate"] = hbp_rate
            item["price_difference"] = price_difference
            item["flag"] = "overpriced" if price_difference > 0 else "acceptable"
            item["matched_reference_item"] = match["reference_item"]
            item["approximate_match"] = bool(match["approximate_match"])
            item["hbp_procedure_code"] = match["hbp_procedure_code"]
            item["hbp_package_code"] = match["hbp_package_code"]
            item["hbp_package_name"] = match["package_name"]
            item["hbp_tier_1_rate"] = match["tier_1_rate"]
            item["hbp_tier_2_rate"] = match["tier_2_rate"]
            item["hbp_tier_3_rate"] = match["tier_3_rate"]

        compared_items.append(item)

    return compared_items


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

    for raw_item in line_items:
        item = dict(raw_item)
        item["comparison_source"] = "cghs"
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


def _add_rajiv_aarogyasri_comparison(
    line_items: list[dict[str, Any]],
    *,
    tier: str,
    rate_type: str,
    bill_date: str | None = None,
    context_match: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    from app.rajiv_aarogyasri import get_rajiv_aarogyasri_store

    try:
        store = get_rajiv_aarogyasri_store()
    except FileNotFoundError:
        return _add_cghs_comparison(
            line_items,
            tier=tier,
            rate_type=rate_type,
        )
    except Exception as exc:
        logger.exception("Rajiv Aarogyasri comparison unavailable: %s", exc)
        compared_items: list[dict[str, Any]] = []
        for raw_item in line_items:
            cghs_items = _add_cghs_comparison([raw_item], tier=tier, rate_type=rate_type)
            fallback_item = cghs_items[0]
            fallback_item["comparison_source"] = "cghs"
            fallback_item["aarogyasri_fallback_used"] = True
            fallback_item["aarogyasri_package_not_found"] = True
            compared_items.append(fallback_item)
        return compared_items

    compared_items: list[dict[str, Any]] = []

    for raw_item in line_items:
        item = dict(raw_item)
        item_name = str(item.get("item_name", "")).strip()
        total_price = _to_float(item.get("total_price"))
        try:
            package_match = store.match_aarogyasri_package(item_name, bill_date)
            if (
                not package_match.get("matched_package")
                and context_match
                and context_match.get("matched_package")
            ):
                package_match = context_match
        except Exception as exc:
            logger.exception(
                "Rajiv Aarogyasri package match failed for '%s': %s",
                item_name,
                exc,
            )
            cghs_items = _add_cghs_comparison([item], tier=tier, rate_type=rate_type)
            fallback_item = cghs_items[0]
            fallback_item["comparison_source"] = "cghs"
            fallback_item["aarogyasri_fallback_used"] = True
            fallback_item["aarogyasri_package_not_found"] = True
            compared_items.append(fallback_item)
            continue

        if package_match.get("matched_package") and package_match.get("approved_rate") is not None:
            approved_rate = _to_float(package_match["approved_rate"])
            price_difference = round(total_price - approved_rate, 2)
            item["comparison_source"] = "aarogyasri"
            item["aarogyasri_rate"] = approved_rate
            item["price_difference"] = price_difference
            item["flag"] = "overpriced" if price_difference > 0 else "acceptable"
            item["matched_reference_item"] = package_match.get("package_name")
            item["approximate_match"] = bool(
                _to_float(package_match.get("confidence_score")) < 0.84
            )
            item["aarogyasri_package_code"] = package_match.get("package_code")
            item["aarogyasri_package_name"] = package_match.get("package_name")
            item["aarogyasri_specialty"] = package_match.get("specialty")
            item["aarogyasri_source_file"] = package_match.get("source_file")
            item["aarogyasri_match_confidence"] = package_match.get("confidence_score")
            item["aarogyasri_fallback_used"] = False
            item["cghs_rate"] = None
            compared_items.append(item)
            continue

        cghs_items = _add_cghs_comparison([item], tier=tier, rate_type=rate_type)
        fallback_item = cghs_items[0]
        fallback_item["comparison_source"] = "cghs"
        fallback_item["aarogyasri_fallback_used"] = True
        fallback_item["aarogyasri_package_not_found"] = True
        compared_items.append(fallback_item)

    return compared_items


def _add_price_comparison(
    line_items: list[dict[str, Any]],
    *,
    tier: str,
    rate_type: str,
    tier_id: str | None = None,
    pmjay_eligible: bool = False,
    rajiv_aarogyasri_selected: bool = False,
    bill_date: str | None = None,
    rajiv_context_match: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    from app.medicine_comparison import (
        compare_line_item_with_nppa,
        should_use_nppa_result,
    )

    compared: list[dict[str, Any]] = []
    effective_tier_id = tier_id or "tier_3"
    for raw_item in line_items:
        item = dict(raw_item)
        pharma_item = compare_line_item_with_nppa(item)
        if should_use_nppa_result(item, pharma_item):
            compared.append(pharma_item)
            continue
        if rajiv_aarogyasri_selected:
            compared.extend(
                _add_rajiv_aarogyasri_comparison(
                    [item],
                    tier=tier,
                    rate_type=rate_type,
                    bill_date=bill_date,
                    context_match=rajiv_context_match,
                )
            )
        elif pmjay_eligible:
            compared.extend(
                _add_hbp_comparison([item], tier_id=effective_tier_id)
            )
        else:
            compared.extend(
                _add_cghs_comparison([item], tier=tier, rate_type=rate_type)
            )
    return compared


def _resolve_nabh_and_rate_type(
    hospital_name: str | None,
    hospital_type: str,
) -> tuple[str, dict[str, Any]]:
    canonical_hospital_type = resolve_hospital_type(hospital_type)
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

    rate_type = resolve_rate_type_for_hospital(
        canonical_hospital_type,
        nabh_accredited=bool(nabh_lookup.get("is_accredited")),
    )
    return rate_type, {
        "hospital_type": canonical_hospital_type,
        "rate_type": rate_type,
        "nabh": nabh_lookup,
    }


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
    pmjay_eligible: bool = False
    hospitalisation_relief_scheme_selected: bool = False
    is_registered_construction_worker: bool = False
    kcr_kit_selected: bool = False
    kcr_is_pregnant: bool = False
    kcr_is_telangana_resident: bool = False
    kcr_age_18_or_above: bool = False
    kcr_income_below_10000: bool = False
    kcr_government_hospital_treatment: bool = False
    kcr_more_than_two_live_children: bool = False
    kcr_aadhaar_telangana: bool = False
    kcr_identified_by_anganwadi_worker: bool = False
    rajiv_aarogyasri_selected: bool = False
    rajiv_is_telangana_resident: bool = False
    rajiv_has_eligible_card: bool = False
    rajiv_has_aadhaar: bool = False
    rajiv_is_cancer_related: bool = False
    rajiv_family_coverage_used_amount: float | None = None
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
    cghs_fallback_from_aarogya: bool = False
    cghs_beneficiary_category: str | None = None
    cghs_eligible_category_confirmed: bool | None = None
    cghs_resides_in_covered_city: bool | None = None

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
    pmjay_eligible: bool = False,
    hospitalisation_relief_scheme_selected: bool = False,
    is_registered_construction_worker: bool = False,
    kcr_kit_selected: bool = False,
    kcr_is_pregnant: bool = False,
    kcr_is_telangana_resident: bool = False,
    kcr_age_18_or_above: bool = False,
    kcr_income_below_10000: bool = False,
    kcr_government_hospital_treatment: bool = False,
    kcr_more_than_two_live_children: bool = False,
    kcr_aadhaar_telangana: bool = False,
    kcr_identified_by_anganwadi_worker: bool = False,
    rajiv_aarogyasri_selected: bool = False,
    rajiv_is_telangana_resident: bool = False,
    rajiv_has_eligible_card: bool = False,
    rajiv_has_aadhaar: bool = False,
    rajiv_is_cancer_related: bool = False,
    rajiv_family_coverage_used_amount: float | None = None,
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
    cghs_fallback_from_aarogya: bool = False,
    cghs_beneficiary_category: str | None = None,
    cghs_eligible_category_confirmed: bool | None = None,
    cghs_resides_in_covered_city: bool | None = None,
) -> dict[str, Any]:
    if not line_items:
        raise HTTPException(status_code=400, detail="Add at least one line item.")

    canonical_tier, location_meta = _resolve_comparison_tier(
        tier=tier,
        state_ut_name=state_ut_name,
        city=city,
    )
    canonical_rate_type, hospital_meta = _resolve_nabh_and_rate_type(
        hospital_name, hospital_type
    )

    normalized_items = _normalize_line_items(line_items)
    tier_id = location_meta.get("tier_id") or tier or "tier_3"
    from app.rajiv_aarogyasri import (
        build_package_search_terms,
        build_rajiv_aarogyasri_fallback_report,
        extract_department_from_text,
        get_rajiv_aarogyasri_store,
    )

    package_search_terms: list[str] = []
    rajiv_context_match: dict[str, Any] | None = None
    if rajiv_aarogyasri_selected:
        package_search_terms = build_package_search_terms(
            ocr_text=ocr_text,
            diagnosis=diagnosis,
            department=extract_department_from_text(ocr_text),
            line_items=normalized_items,
            prescription_items=prescription_items or [],
        )
        if _dev_logging_enabled():
            logger.info(
                "compare-bill Rajiv context: %d bill items, %d search terms, hospital=%s",
                len(normalized_items),
                len(package_search_terms),
                hospital_name,
            )
        try:
            rajiv_store = get_rajiv_aarogyasri_store()
            if _dev_logging_enabled():
                logger.info(
                    "Rajiv Aarogyasri CSV folder=%s files=%s",
                    rajiv_store.data_dir,
                    [path.name for path in rajiv_store._discover_package_files()],
                )
            rajiv_context_match = rajiv_store.match_package_from_search_terms(
                package_search_terms,
                bill_date,
            )
            if _dev_logging_enabled():
                logger.info(
                    "Rajiv Aarogyasri package match result=%s confidence=%s",
                    rajiv_context_match.get("package_match_status"),
                    rajiv_context_match.get("confidence_score"),
                )
        except Exception as exc:
            logger.exception("Rajiv Aarogyasri package context match failed: %s", exc)

    compared_line_items = _add_price_comparison(
        normalized_items,
        tier=canonical_tier,
        rate_type=canonical_rate_type,
        tier_id=tier_id,
        pmjay_eligible=pmjay_eligible,
        rajiv_aarogyasri_selected=rajiv_aarogyasri_selected,
        bill_date=bill_date,
        rajiv_context_match=rajiv_context_match,
    )
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

    store = get_cghs_store()
    comparison_scheme = (
        "rajiv_aarogyasri"
        if rajiv_aarogyasri_selected
        else "hbp_pmjay"
        if pmjay_eligible
        else "cghs"
    )
    rates_source: dict[str, Any] = {
        "cghs_file": str(store.csv_path.name),
        "total_procedures_loaded": len(store.rows),
        "comparison_scheme": comparison_scheme,
    }
    if rajiv_aarogyasri_selected:
        try:
            from app.rajiv_aarogyasri import get_rajiv_aarogyasri_store

            rajiv_store = get_rajiv_aarogyasri_store()
            rates_source["aarogyasri_hospitals_loaded"] = len(rajiv_store.hospitals)
            rates_source["aarogyasri_packages_loaded"] = len(rajiv_store.packages)
        except Exception:
            rates_source["aarogyasri_hospitals_loaded"] = 0
            rates_source["aarogyasri_packages_loaded"] = 0
    if pmjay_eligible:
        try:
            hbp_store = get_hbp_store()
            rates_source["hbp_file"] = str(hbp_store.csv_path.name)
            rates_source["total_hbp_procedures_loaded"] = len(hbp_store.rows)
        except Exception:
            rates_source["hbp_file"] = None
            rates_source["total_hbp_procedures_loaded"] = 0
    try:
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

    from app.cghs_eligibility import build_cghs_eligibility_advisory
    from app.hospitalisation_relief_scheme import build_hospitalisation_relief_advisory
    from app.kcr_kit_scheme import build_kcr_kit_advisory
    from app.rajiv_aarogyasri import build_rajiv_aarogyasri_report

    patient_payload: dict[str, Any] | None = None
    if patient_id or patient_name:
        patient_payload = {
            "id": patient_id,
            "name": patient_name,
            "age": patient_age,
            "gender": patient_gender,
            "ayushman_eligible": pmjay_eligible,
            "hospitalisation_relief_scheme_selected": (
                hospitalisation_relief_scheme_selected
            ),
            "is_registered_construction_worker": is_registered_construction_worker,
            "kcr_kit_selected": kcr_kit_selected,
            "kcr_is_pregnant": kcr_is_pregnant,
            "kcr_is_telangana_resident": kcr_is_telangana_resident,
            "kcr_age_18_or_above": kcr_age_18_or_above,
            "kcr_income_below_10000": kcr_income_below_10000,
            "kcr_government_hospital_treatment": kcr_government_hospital_treatment,
            "kcr_more_than_two_live_children": kcr_more_than_two_live_children,
            "kcr_aadhaar_telangana": kcr_aadhaar_telangana,
            "kcr_identified_by_anganwadi_worker": kcr_identified_by_anganwadi_worker,
            "rajiv_aarogyasri_selected": rajiv_aarogyasri_selected,
            "rajiv_is_telangana_resident": rajiv_is_telangana_resident,
            "rajiv_has_eligible_card": rajiv_has_eligible_card,
            "rajiv_has_aadhaar": rajiv_has_aadhaar,
            "rajiv_is_cancer_related": rajiv_is_cancer_related,
            "rajiv_family_coverage_used_amount": rajiv_family_coverage_used_amount,
            "cghs_beneficiary_category": cghs_beneficiary_category,
            "cghs_eligible_category_confirmed": cghs_eligible_category_confirmed,
            "cghs_resides_in_covered_city": cghs_resides_in_covered_city,
        }

    hospitalisation_relief_advisory = build_hospitalisation_relief_advisory(
        hospitalisation_relief_scheme_selected=hospitalisation_relief_scheme_selected,
        is_registered_construction_worker=is_registered_construction_worker,
    )
    kcr_kit_advisory = build_kcr_kit_advisory(
        kcr_kit_selected=kcr_kit_selected,
        kcr_is_pregnant=kcr_is_pregnant,
        kcr_is_telangana_resident=kcr_is_telangana_resident,
        kcr_age_18_or_above=kcr_age_18_or_above,
        kcr_income_below_10000=kcr_income_below_10000,
        kcr_government_hospital_treatment=kcr_government_hospital_treatment,
        kcr_more_than_two_live_children=kcr_more_than_two_live_children,
        kcr_aadhaar_telangana=kcr_aadhaar_telangana,
        kcr_identified_by_anganwadi_worker=kcr_identified_by_anganwadi_worker,
    )
    rajiv_aarogyasri_report = build_rajiv_aarogyasri_report(
        rajiv_aarogyasri_selected=rajiv_aarogyasri_selected,
        rajiv_is_telangana_resident=rajiv_is_telangana_resident,
        rajiv_has_eligible_card=rajiv_has_eligible_card,
        rajiv_has_aadhaar=rajiv_has_aadhaar,
        rajiv_is_cancer_related=rajiv_is_cancer_related,
        rajiv_family_coverage_used_amount=rajiv_family_coverage_used_amount,
        ocr_hospital_name=hospital_name,
        patient_state=location_meta.get("state_name", state_ut_name),
        patient_district=patient_district or location_meta.get("city", city),
        patient_city=location_meta.get("city", city),
        bill_date=bill_date,
        line_items=normalized_items,
        compared_line_items=compared_line_items,
        ocr_text=ocr_text,
        diagnosis=diagnosis,
        department=extract_department_from_text(ocr_text),
        prescription_items=prescription_items or [],
        context_match=rajiv_context_match,
    )
    if rajiv_aarogyasri_selected and rajiv_aarogyasri_report is None:
        rajiv_aarogyasri_report = build_rajiv_aarogyasri_fallback_report(
            rajiv_is_telangana_resident=rajiv_is_telangana_resident,
            rajiv_has_eligible_card=rajiv_has_eligible_card,
            rajiv_has_aadhaar=rajiv_has_aadhaar,
            rajiv_is_cancer_related=rajiv_is_cancer_related,
            rajiv_family_coverage_used_amount=rajiv_family_coverage_used_amount,
            ocr_hospital_name=hospital_name,
            patient_state=location_meta.get("state_name", state_ut_name),
            patient_district=patient_district or location_meta.get("city", city),
            patient_city=location_meta.get("city", city),
            line_items=normalized_items,
            compared_line_items=compared_line_items,
        )

    restricted_medicine_flags = build_restricted_medicine_flags(
        ocr_text=ocr_text,
        line_items=compared_line_items,
        prescription_items=prescription_items or [],
    )
    cghs_eligibility_advisory = build_cghs_eligibility_advisory(
        comparison_scheme=comparison_scheme,
        cghs_fallback_from_aarogya=cghs_fallback_from_aarogya,
        line_items=compared_line_items,
        beneficiary_category=cghs_beneficiary_category,
        eligible_category_confirmed=cghs_eligible_category_confirmed,
        resides_in_covered_city=cghs_resides_in_covered_city,
    )

    return {
        "filename": filename,
        "file_type": file_type,
        "message": "Comparison completed",
        "hospital": {
            "name_from_bill": hospital_name,
            **hospital_meta["nabh"],
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
            "hospital_type": hospital_meta["hospital_type"],
            "rate_type": canonical_rate_type,
            "rate_type_label": _rate_type_label(canonical_rate_type),
            "pmjay_eligible": pmjay_eligible,
            "rajiv_aarogyasri_selected": rajiv_aarogyasri_selected,
            "comparison_scheme": comparison_scheme,
            "cghs_fallback_from_aarogya": cghs_fallback_from_aarogya,
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
        "hospitalisation_relief_advisory": hospitalisation_relief_advisory,
        "kcr_kit_advisory": kcr_kit_advisory,
        "rajiv_aarogyasri_report": rajiv_aarogyasri_report,
        "restricted_medicine_flags": restricted_medicine_flags,
        "cghs_eligibility_advisory": cghs_eligibility_advisory,
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
            "POST /compare-bill: items=%d rajiv=%s state=%s city=%s hospital=%s",
            len(line_items),
            body.rajiv_aarogyasri_selected,
            body.state_ut_name,
            body.city,
            body.hospital_name,
        )
    response = _build_comparison_response(
        line_items=line_items,
        state_ut_name=body.state_ut_name,
        city=body.city,
        hospital_type=body.hospital_type,
        hospital_name=body.hospital_name,
        tier=body.tier,
        filename=body.filename or "edited-bill",
        file_type=body.file_type or "manual",
        pmjay_eligible=body.pmjay_eligible,
        hospitalisation_relief_scheme_selected=(
            body.hospitalisation_relief_scheme_selected
        ),
        is_registered_construction_worker=body.is_registered_construction_worker,
        kcr_kit_selected=body.kcr_kit_selected,
        kcr_is_pregnant=body.kcr_is_pregnant,
        kcr_is_telangana_resident=body.kcr_is_telangana_resident,
        kcr_age_18_or_above=body.kcr_age_18_or_above,
        kcr_income_below_10000=body.kcr_income_below_10000,
        kcr_government_hospital_treatment=body.kcr_government_hospital_treatment,
        kcr_more_than_two_live_children=body.kcr_more_than_two_live_children,
        kcr_aadhaar_telangana=body.kcr_aadhaar_telangana,
        kcr_identified_by_anganwadi_worker=body.kcr_identified_by_anganwadi_worker,
        rajiv_aarogyasri_selected=body.rajiv_aarogyasri_selected,
        rajiv_is_telangana_resident=body.rajiv_is_telangana_resident,
        rajiv_has_eligible_card=body.rajiv_has_eligible_card,
        rajiv_has_aadhaar=body.rajiv_has_aadhaar,
        rajiv_is_cancer_related=body.rajiv_is_cancer_related,
        rajiv_family_coverage_used_amount=body.rajiv_family_coverage_used_amount,
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
        cghs_fallback_from_aarogya=body.cghs_fallback_from_aarogya,
        cghs_beneficiary_category=body.cghs_beneficiary_category,
        cghs_eligible_category_confirmed=body.cghs_eligible_category_confirmed,
        cghs_resides_in_covered_city=body.cghs_resides_in_covered_city,
    )
    if _dev_logging_enabled():
        logger.info(
            "POST /compare-bill complete: compared_items=%d rajiv_report=%s status=%s",
            len(response.get("line_items") or []),
            bool(response.get("rajiv_aarogyasri_report")),
            (response.get("rajiv_aarogyasri_report") or {}).get("status"),
        )
    return response


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

    _, hospital_meta = _resolve_nabh_and_rate_type(hospital_name, hospital_type)

    normalized_items = _normalize_line_items(line_items)

    return {
        "filename": file.filename or "unknown",
        "file_type": file_type,
        "message": "Bill extracted successfully",
        "hospital": {
            "name_from_bill": hospital_name,
            **hospital_meta["nabh"],
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
            "hospital_type": hospital_meta["hospital_type"],
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


@app.post("/api/aarogya-bhadratha/extract-bill")
async def aarogya_extract_bill(file: UploadFile = File(...)) -> dict[str, Any]:
    """OCR-extract a bill for the Aarogya Bhadratha workflow.

    Reuses the same OCR + extraction pipeline as /upload-bill but without
    requiring CGHS state/city/tier (Telangana is not in the CGHS city
    directory). Preserves the original OCR text and extracted values.
    """
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
    if not ai_result.get("is_medical_bill", False):
        raise HTTPException(
            status_code=400,
            detail=ai_result.get(
                "error", "Uploaded document does not appear to be a medical bill."
            ),
        )

    line_items = ai_result.get("line_items", [])
    if not isinstance(line_items, list):
        line_items = []
    normalized_items = _normalize_line_items(line_items)

    hospital_name = ai_result.get("hospital_name")
    if hospital_name is not None:
        hospital_name = str(hospital_name).strip() or None

    original_total = round(
        sum(max(_to_float(i.get("total_price")), 0.0) for i in normalized_items), 2
    )

    return {
        "filename": file.filename or "unknown",
        "file_type": file_type,
        "message": "Bill extracted successfully",
        "ocr_hospital_name": hospital_name,
        "ocr_text": extracted_text,
        "bill_date": _extract_bill_date(extracted_text),
        "original_total": original_total,
        "line_items": normalized_items,
    }
