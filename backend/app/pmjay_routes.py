"""PM-JAY scheme API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from app.pmjay_hospitals import build_pmjay_hospital_verification, get_pmjay_hospital_store

router = APIRouter(prefix="/api/schemes/pmjay", tags=["pmjay"])

_DATA_UNAVAILABLE = "PM-JAY hospital data is currently unavailable. Please try again later."


def _store():
    try:
        return get_pmjay_hospital_store()
    except Exception as exc:  # noqa: BLE001 - never leak filesystem paths
        print(f"WARNING: PM-JAY hospital data failed to load: {exc}")
        raise HTTPException(status_code=503, detail=_DATA_UNAVAILABLE) from exc


class VerifyHospitalRequest(BaseModel):
    hospital_name: str = ""
    state: str | None = None
    district: str | None = None
    city: str | None = None
    pmjay_has_ayushman_card: bool | None = None


@router.get("/status")
def pmjay_status() -> dict[str, Any]:
    store = _store()
    return {
        "status": "ok",
        "hospitals_loaded": len(store.hospitals),
        "states": len(store.list_states()),
        "districts": len(store.list_districts()),
    }


@router.get("/hospitals/search")
def search_hospitals(
    q: str = Query("", description="Search hospital name, alias, city, district, state, speciality"),
    state: str = Query("", description="Filter by state"),
    district: str = Query("", description="Filter by district"),
    city: str = Query("", description="Filter by city"),
    hospital_type: str = Query("", description="Filter by hospital type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    store = _store()
    return store.search_hospitals(
        query=q,
        state=state,
        district=district,
        city=city,
        hospital_type=hospital_type,
        limit=limit,
        offset=offset,
    )


@router.get("/filters")
def list_filters(
    state: str = Query("", description="Optional state for district/city lists"),
    district: str = Query("", description="Optional district for city list"),
) -> dict[str, Any]:
    store = _store()
    return {
        "states": store.list_states(),
        "districts": store.list_districts(state=state),
        "cities": store.list_cities(state=state, district=district),
        "hospital_types": store.list_hospital_types(),
    }


@router.post("/verify-hospital")
def verify_hospital(body: VerifyHospitalRequest = Body(...)) -> dict[str, Any]:
    verification = build_pmjay_hospital_verification(
        pmjay_selected=True,
        ocr_hospital_name=body.hospital_name,
        patient_state=body.state,
        patient_district=body.district,
        patient_city=body.city,
        pmjay_has_ayushman_card=body.pmjay_has_ayushman_card,
    )
    if verification is None:
        raise HTTPException(status_code=400, detail="PM-JAY verification requires a hospital name.")
    return verification
