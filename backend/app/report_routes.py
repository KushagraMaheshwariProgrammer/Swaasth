"""Unified report PDF endpoints for all comparison schemes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from app.report_pdf import (
    render_report_pdf,
    resolve_scheme_id,
    scheme_filename_prefix,
    validate_report,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/render-pdf")
def render_pdf(report: dict[str, Any] = Body(...)) -> Response:
    """Render a PDF from a report object supplied by the client.

    Works for any registered comparison scheme (CGHS, PM-JAY HBP, Aarogya
    Bhadratha, and future schemes) using the full report stored in bill history.
    """
    try:
        scheme_id = resolve_scheme_id(report)
        validate_report(report, scheme_id)
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
    prefix = scheme_filename_prefix(scheme_id)
    filename = f"{prefix}-{safe_name}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
