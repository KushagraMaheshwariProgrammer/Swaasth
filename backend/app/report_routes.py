"""Unified report PDF endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response

from app.report_pdf import (
    render_report_pdf,
    report_filename_prefix,
    resolve_report_kind,
    validate_report,
)
from app.services.firebase_auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/render-pdf")
def render_pdf(
    report: dict[str, Any] = Body(...),
    _user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Render a PDF from a report object supplied by the client."""
    try:
        report_kind = resolve_report_kind(report)
        validate_report(report, report_kind)
        pdf_bytes = render_report_pdf(report)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Report PDF render failed: {exc}")
        raise HTTPException(
            status_code=500, detail="Could not generate the report PDF."
        ) from exc

    patient_name = str((report.get("patient") or {}).get("name") or "report")
    safe_name = patient_name.replace(" ", "-")[:40]
    prefix = report_filename_prefix(report_kind)
    filename = f"{prefix}-{safe_name}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
