"""Aarogya Bhadratha Scheme API routes.

Hospital directory / search, hospital empanelment verification, bill-item rate
comparison, and report retrieval / PDF download.

Note on auth: this project authenticates entirely on the client (Firebase Auth)
and authorizes data access via Firestore security rules; the FastAPI backend
(including the existing /upload-bill and /compare-bill endpoints) is stateless
and unauthenticated. These endpoints follow the same architecture and never
expose server filesystem paths.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.aarogya_bhadratha import get_aarogya_store
from app.aarogya_reports import (
    build_report,
    get_report,
    render_report_pdf,
    save_report,
)

router = APIRouter(prefix="/api/aarogya-bhadratha", tags=["aarogya-bhadratha"])

_DATA_UNAVAILABLE = "Aarogya Bhadratha data is currently unavailable. Please try again later."


def _store():
    try:
        return get_aarogya_store()
    except Exception as exc:  # noqa: BLE001 - never leak filesystem paths
        # Log server-side detail without exposing it to the client.
        print(f"WARNING: Aarogya Bhadratha data failed to load: {exc}")
        raise HTTPException(status_code=503, detail=_DATA_UNAVAILABLE) from exc


@router.get("/hospitals")
def list_hospitals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    return _store().search_hospitals(page=page, limit=limit)


@router.get("/hospitals/search")
def search_hospitals(
    query: str = Query("", description="Free-text search across name/district/address/speciality"),
    district: str = Query("", description="Filter by district"),
    speciality: str = Query("", description="Filter by speciality"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    return _store().search_hospitals(
        query=query,
        district=district,
        speciality=speciality,
        page=page,
        limit=limit,
    )


@router.get("/districts")
def list_districts() -> list[str]:
    return _store().list_districts()


@router.get("/specialities")
def list_specialities() -> list[str]:
    return _store().list_specialities()


class VerifyHospitalRequest(BaseModel):
    hospital_name: str = ""
    district: str = ""
    address: str = ""


@router.post("/verify-hospital")
def verify_hospital(body: VerifyHospitalRequest) -> dict[str, Any]:
    name = (body.hospital_name or "").strip()
    if not name:
        return {
            "ocr_hospital_name": "",
            "empanelment_status": "name_missing",
            "matched_hospital": None,
            "match_confidence": 0.0,
            "match_method": "none",
            "candidates": [],
            "message": "No hospital name detected. Search the directory or enter the name.",
        }
    return _store().verify_hospital(name, district=body.district, address=body.address)


class CompareLineItem(BaseModel):
    item_name: str = ""
    quantity: float = Field(default=1, ge=0)
    unit_price: float = Field(default=0, ge=0)
    total_price: float = Field(default=0, ge=0)
    category: str = "other"


class ComparePatient(BaseModel):
    name: str = ""
    state: str = ""
    aarogya_bhadratha_eligible: bool = True
    id: str | None = None


class CompareBillMeta(BaseModel):
    filename: str | None = None
    bill_date: str | None = None
    original_total: float | None = None
    file_type: str | None = None


class CompareRatesRequest(BaseModel):
    hospital_id: str
    patient: ComparePatient = Field(default_factory=ComparePatient)
    line_items: list[CompareLineItem] = Field(default_factory=list)
    bill: CompareBillMeta = Field(default_factory=CompareBillMeta)
    ocr_hospital_name: str = ""
    ocr_text: str = ""
    match_confidence: float | None = None
    match_method: str | None = None


@router.post("/compare-rates")
def compare_rates(body: CompareRatesRequest) -> dict[str, Any]:
    store = _store()

    hospital = store.get_hospital(body.hospital_id)
    if hospital is None:
        raise HTTPException(
            status_code=404,
            detail="Selected hospital was not found in the Aarogya Bhadratha list.",
        )

    line_items = [item.model_dump() for item in body.line_items]
    if not line_items:
        raise HTTPException(status_code=400, detail="No bill items to compare.")

    comparison = store.compare_bill_items(line_items)

    original_total = body.bill.original_total
    if original_total is None:
        original_total = round(
            sum(max(float(i.get("total_price") or 0), 0.0) for i in line_items), 2
        )

    hospital_verification = {
        "ocr_hospital_name": body.ocr_hospital_name or "",
        "matched_hospital": hospital.to_public(),
        "match_confidence": (
            body.match_confidence if body.match_confidence is not None else 1.0
        ),
        "match_method": body.match_method or "user_confirmed",
        "empanelment_status": "empanelled",
    }

    report = build_report(
        patient={
            "name": body.patient.name,
            "state": body.patient.state,
            "aarogya_bhadratha_eligible": body.patient.aarogya_bhadratha_eligible,
            "id": body.patient.id,
        },
        hospital_verification=hospital_verification,
        comparison=comparison,
        bill={
            "filename": body.bill.filename,
            "bill_date": body.bill.bill_date,
            "original_total": original_total,
            "file_type": body.bill.file_type,
        },
        ocr={
            "text": body.ocr_text or "",
            "line_items": line_items,
        },
    )
    save_report(report)
    return report


@router.post("/reports/render-pdf")
def render_pdf(report: dict[str, Any] = Body(...)) -> Response:
    """Render a PDF from a report object supplied by the client.

    Lets a saved report be re-downloaded/shared even if the server-side report
    cache no longer holds it (e.g. after a restart), since the client keeps the
    full report in its bill history.
    """
    if not report.get("comparison"):
        raise HTTPException(status_code=400, detail="Invalid report payload.")
    try:
        pdf_bytes = render_report_pdf(report)
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Aarogya Bhadratha PDF render failed: {exc}")
        raise HTTPException(
            status_code=500, detail="Could not generate the report PDF."
        ) from exc
    report_id = str(report.get("report_id") or "report")[:8]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="aarogya-bhadratha-{report_id}.pdf"'
        },
    )


@router.get("/reports/{report_id}")
def fetch_report(report_id: str) -> dict[str, Any]:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@router.get("/reports/{report_id}/pdf")
def fetch_report_pdf(report_id: str) -> Response:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    try:
        pdf_bytes = render_report_pdf(report)
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Aarogya Bhadratha PDF render failed: {exc}")
        raise HTTPException(
            status_code=500, detail="Could not generate the report PDF."
        ) from exc
    filename = f"aarogya-bhadratha-report-{report_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
