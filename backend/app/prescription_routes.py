"""Prescription upload and STG treatment analysis routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.document_extraction import (
    extract_bill_with_groq,
    extract_document_text,
    extract_prescription_with_groq,
    normalize_prescription_items,
)
from app.services.stg_index import get_stg_index_store
from app.services.treatment_audit import analyze_treatment

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpeg",
    "image/png": "png",
}


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
    medicines: list[PrescriptionItemInput] = Field(default_factory=list)
    tests: list[PrescriptionItemInput] = Field(default_factory=list)
    procedures: list[PrescriptionItemInput] = Field(default_factory=list)
    bill_items: list[BillItemInput] = Field(default_factory=list)
    patient_id: str | None = None
    patient_name: str | None = None


def _prescription_items_from_payload(
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


@router.get("/api/stg/conditions")
def list_stg_conditions() -> dict[str, Any]:
    store = get_stg_index_store()
    if not store.toc:
        raise HTTPException(
            status_code=503,
            detail=(
                "STG index is not built. Run: python backend/scripts/build_stg_index.py"
            ),
        )
    return {
        "conditions": store.condition_names(),
        "count": len(store.toc),
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
            detail=ai_result.get(
                "error",
                "Uploaded document does not appear to be a prescription.",
            ),
        )

    return {
        "filename": file.filename or "unknown",
        "file_type": file_type,
        "message": "Prescription extracted successfully",
        "ocr_text": extracted_text,
        **ai_result,
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

    treatment_audit_flags = analyze_treatment(
        diagnosis=body.diagnosis,
        prescription_items=prescription_items,
        bill_items=bill_items,
    )

    return {
        "message": "Treatment analysis completed",
        "diagnosis": body.diagnosis,
        "diagnosis_user_provided": body.diagnosis_user_provided,
        "patient": {
            "id": body.patient_id,
            "name": body.patient_name,
        }
        if body.patient_id or body.patient_name
        else None,
        "prescription_items": prescription_items,
        "treatment_audit_flags": treatment_audit_flags,
        "report_kind": "prescription",
    }
