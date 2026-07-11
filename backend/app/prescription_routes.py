"""Prescription upload and STG treatment analysis routes."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.restricted_medicines import build_restricted_medicine_flags
from app.services.document_extraction import (
    classify_document_with_groq,
    extract_discharge_summary_with_groq,
    extract_document_text,
    extract_lab_report_with_groq,
    extract_prescription_with_groq,
    merge_clinical_contexts,
    normalize_clinical_context,
    normalize_detected_document_type,
    normalize_document_classification,
    normalize_prescription_items,
    resolve_document_date,
)
from app.services.primary_guidelines_index import get_primary_guidelines_store
from app.services.stg_index import get_stg_index_store
from app.services.action_plan import build_action_plan
from app.services.patient_errors import document_mismatch_detail
from app.services.patient_age import resolve_patient_age
from app.services.patient_gender import gender_display_label
from app.services.treatment_audit import analyze_treatment

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpeg",
    "image/png": "png",
}


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


class PrescriptionItemInput(BaseModel):
    name: str = ""
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None
    category: str | None = None


class BillItemInput(BaseModel):
    item_name: str = ""
    name: str | None = None
    category: str | None = None


class AnalyzeTreatmentRequest(BaseModel):
    diagnosis: str
    diagnosis_user_provided: bool = False
    diagnosis_confidence: str | None = None
    medicines: list[PrescriptionItemInput] = Field(default_factory=list)
    tests: list[PrescriptionItemInput] = Field(default_factory=list)
    procedures: list[PrescriptionItemInput] = Field(default_factory=list)
    bill_items: list[BillItemInput] = Field(default_factory=list)
    symptoms: list[SymptomInput] = Field(default_factory=list)
    test_results: list[TestResultInput] = Field(default_factory=list)
    patient_id: str | None = None
    patient_name: str | None = None
    patient_birth_year: int | None = None
    patient_age: int | None = None
    patient_gender: str | None = None
    ocr_text: str | None = None
    clinical_history: dict[str, Any] | None = None


def _prescription_item_payload(
    entry: PrescriptionItemInput,
    *,
    category: str,
) -> dict[str, Any] | None:
    name = entry.name.strip()
    if not name:
        return None
    payload: dict[str, Any] = {"name": name, "category": category}
    if entry.dose:
        payload["dose"] = entry.dose.strip()
    if entry.frequency:
        payload["frequency"] = entry.frequency.strip()
    if entry.duration:
        payload["duration"] = entry.duration.strip()
    return payload


def _prescription_items_from_payload(
    medicines: list[PrescriptionItemInput],
    tests: list[PrescriptionItemInput],
    procedures: list[PrescriptionItemInput],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in medicines:
        item = _prescription_item_payload(entry, category="medicine")
        if item:
            items.append(item)
    for entry in tests:
        item = _prescription_item_payload(entry, category="test")
        if item:
            items.append(item)
    for entry in procedures:
        item = _prescription_item_payload(entry, category="procedure")
        if item:
            items.append(item)
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


@router.get("/api/stg/conditions")
def list_stg_conditions() -> dict[str, Any]:
    primary_store = get_primary_guidelines_store()
    crc_store = get_stg_index_store()

    primary_names = primary_store.condition_names() if primary_store.toc else []
    crc_names = crc_store.condition_names() if crc_store.toc else []

    if not primary_names and not crc_names:
        raise HTTPException(
            status_code=503,
            detail=(
                "No guideline indexes are built. Run "
                "python backend/scripts/build_primary_guidelines_index.py and "
                "python backend/scripts/build_stg_index.py"
            ),
        )

    merged: list[str] = []
    seen: set[str] = set()
    for name in primary_names + crc_names:
        label = str(name).strip()
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(label)

    return {
        "conditions": merged,
        "count": len(merged),
        "sources": {
            "primary": len(primary_names),
            "crc": len(crc_names),
        },
    }


@router.post("/classify-document")
async def classify_document(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Allowed types: pdf, jpg, jpeg, png.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    file_type = ALLOWED_TYPES[file.content_type]
    extracted_text = extract_document_text(file_bytes, file_type)
    if not extracted_text:
        return {
            "filename": file.filename or "unknown",
            "file_type": file_type,
            "document_type": None,
            "confidence": "low",
            "message": "No readable text found; manual confirmation required.",
        }

    ai_result = normalize_document_classification(
        classify_document_with_groq(extracted_text)
    )
    return {
        "filename": file.filename or "unknown",
        "file_type": file_type,
        **ai_result,
    }


@router.post("/upload-prescription")
async def upload_prescription(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Allowed types: pdf, jpg, jpeg, png.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    file_type = ALLOWED_TYPES[file.content_type]
    extracted_text = extract_document_text(file_bytes, file_type)
    if not extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No readable text found in the uploaded file.",
        )

    ai_result = normalize_prescription_items(
        extract_prescription_with_groq(extracted_text)
    )
    if not ai_result.get("is_prescription", False):
        raise HTTPException(
            status_code=400,
            detail=document_mismatch_detail(
                filename=file.filename,
                assigned_type="prescription",
                message=ai_result.get("error"),
                fallback="Uploaded document does not appear to be a prescription.",
                suggested_type=normalize_detected_document_type(
                    ai_result.get("detected_document_type")
                ),
            ),
        )

    ai_result["prescription_date"] = resolve_document_date(
        ai_date=ai_result.get("prescription_date"),
        ocr_text=extracted_text,
    )

    return {
        "filename": file.filename or "unknown",
        "file_type": file_type,
        "message": "Prescription extracted successfully",
        "ocr_text": extracted_text,
        **ai_result,
    }


@router.post("/upload-clinical-document")
async def upload_clinical_document(
    file: UploadFile = File(...),
    document_type: Literal["lab_report", "discharge_summary"] = Form(...),
) -> dict[str, Any]:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Allowed types: pdf, jpg, jpeg, png.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    file_type = ALLOWED_TYPES[file.content_type]
    extracted_text = extract_document_text(file_bytes, file_type)
    if not extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No readable text found in the uploaded file.",
        )

    diagnosis: str | None = None
    procedures: list[dict[str, str]] = []

    if document_type == "lab_report":
        ai_result = extract_lab_report_with_groq(extracted_text)
        if not ai_result.get("is_lab_report", False):
            raise HTTPException(
                status_code=400,
                detail=document_mismatch_detail(
                    filename=file.filename,
                    assigned_type="lab_report",
                    message=ai_result.get("error"),
                    fallback="Uploaded document does not appear to be a lab report.",
                    suggested_type=normalize_detected_document_type(
                        ai_result.get("detected_document_type")
                    ),
                ),
            )
        clinical_context = normalize_clinical_context(
            test_results=ai_result.get("test_results") or [],
            symptoms_source="manual",
            test_results_source="lab_report",
        )
        meta = {
            "lab_name": ai_result.get("lab_name"),
            "report_date": resolve_document_date(
                ai_date=ai_result.get("report_date"),
                ocr_text=extracted_text,
            ),
        }
    else:
        ai_result = extract_discharge_summary_with_groq(extracted_text)
        if not ai_result.get("is_discharge_summary", False):
            raise HTTPException(
                status_code=400,
                detail=document_mismatch_detail(
                    filename=file.filename,
                    assigned_type="discharge_summary",
                    message=ai_result.get("error"),
                    fallback=(
                        "Uploaded document does not appear to be a discharge summary."
                    ),
                    suggested_type=normalize_detected_document_type(
                        ai_result.get("detected_document_type")
                    ),
                ),
            )
        diagnosis = ai_result.get("diagnosis")
        if diagnosis is not None:
            diagnosis = str(diagnosis).strip() or None
        procedures = [
            {"name": str(item.get("name", "")).strip()}
            for item in (ai_result.get("procedures") or [])
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        ]
        clinical_context = normalize_clinical_context(
            symptoms=ai_result.get("symptoms") or [],
            test_results=ai_result.get("test_results") or [],
            symptoms_source="discharge",
            test_results_source="discharge",
        )
        meta = {
            "discharge_date": resolve_document_date(
                ai_date=ai_result.get("discharge_date"),
                ocr_text=extracted_text,
            ),
        }

    return {
        "filename": file.filename or "unknown",
        "file_type": file_type,
        "document_type": document_type,
        "message": "Clinical document extracted successfully",
        "ocr_text": extracted_text,
        "diagnosis": diagnosis,
        "procedures": procedures,
        "clinical_context": clinical_context,
        **meta,
    }


@router.post("/analyze-treatment")
def analyze_treatment_endpoint(body: AnalyzeTreatmentRequest) -> dict[str, Any]:
    prescription_items = _prescription_items_from_payload(
        body.medicines,
        body.tests,
        body.procedures,
    )
    bill_items = [
        {
            "item_name": (item.item_name or item.name or "").strip(),
            "category": item.category or "other",
        }
        for item in body.bill_items
        if (item.item_name or item.name or "").strip()
    ]
    clinical_context = _clinical_context_from_request(body.symptoms, body.test_results)
    patient_age = resolve_patient_age(
        patient_age=body.patient_age,
        patient_birth_year=body.patient_birth_year,
    )
    patient_gender = gender_display_label(body.patient_gender)

    treatment_audit_flags = analyze_treatment(
        diagnosis=body.diagnosis,
        prescription_items=prescription_items,
        bill_items=bill_items,
        clinical_context=clinical_context,
        diagnosis_user_provided=body.diagnosis_user_provided,
        diagnosis_confidence=body.diagnosis_confidence,
        clinical_history=body.clinical_history,
        patient_age=patient_age,
        patient_birth_year=body.patient_birth_year,
        patient_gender=patient_gender,
    )

    restricted_medicine_flags = build_restricted_medicine_flags(
        ocr_text=body.ocr_text,
        line_items=bill_items,
        prescription_items=prescription_items,
    )

    action_plan = build_action_plan(
        flags=list(treatment_audit_flags.get("flags") or []),
        line_items=bill_items,
        jan_aushadhi=None,
        patient={
            "id": body.patient_id,
            "name": body.patient_name,
            "birth_year": body.patient_birth_year,
            "age": patient_age,
            "gender": patient_gender,
        }
        if body.patient_id or body.patient_name
        else None,
        hospital=None,
        clinical=clinical_context,
    )

    return {
        "message": "Treatment analysis completed",
        "diagnosis": body.diagnosis,
        "diagnosis_user_provided": body.diagnosis_user_provided,
        "patient": {
            "id": body.patient_id,
            "name": body.patient_name,
            "birth_year": body.patient_birth_year,
            "age": patient_age,
            "gender": patient_gender,
        }
        if body.patient_id or body.patient_name
        else None,
        "prescription_items": prescription_items,
        "clinical_context": clinical_context,
        "treatment_audit_flags": treatment_audit_flags,
        "restricted_medicine_flags": restricted_medicine_flags,
        "patient_questions": treatment_audit_flags.get("patient_questions") or [],
        "advocacy_scope": treatment_audit_flags.get("advocacy_scope"),
        "action_plan": action_plan,
        "report_kind": "prescription",
        "clinical_history_used": treatment_audit_flags.get("clinical_history_used"),
    }
