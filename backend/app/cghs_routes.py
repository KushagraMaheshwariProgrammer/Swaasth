"""CGHS scheme reference API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.cghs_covered_cities import get_cghs_covered_cities_store

router = APIRouter(prefix="/api/schemes/cghs", tags=["cghs"])

_DATA_UNAVAILABLE = "CGHS covered cities data is currently unavailable. Please try again later."


def _store():
    try:
        return get_cghs_covered_cities_store()
    except Exception as exc:  # noqa: BLE001 - never leak filesystem paths
        print(f"WARNING: CGHS covered cities data failed to load: {exc}")
        raise HTTPException(status_code=503, detail=_DATA_UNAVAILABLE) from exc


@router.get("/covered-cities")
def list_covered_cities() -> dict[str, Any]:
    """Return notified CGHS-covered cities for eligibility residence advisory."""
    store = _store()
    return {
        "scheme_code": "CGHS",
        "cities": store.list_public(),
    }
