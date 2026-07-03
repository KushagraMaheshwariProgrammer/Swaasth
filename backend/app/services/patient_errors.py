"""Patient-facing API error messages."""

from __future__ import annotations

_GENERIC_HTTP_PHRASES = frozenset(
    {
        "bad request",
        "unauthorized",
        "forbidden",
        "not found",
        "method not allowed",
        "not acceptable",
        "request timeout",
        "conflict",
        "gone",
        "length required",
        "precondition failed",
        "payload too large",
        "uri too long",
        "unsupported media type",
        "unprocessable entity",
        "too many requests",
        "internal server error",
        "not implemented",
        "bad gateway",
        "service unavailable",
        "gateway timeout",
    }
)


def patient_facing_detail(message: str | None, fallback: str) -> str:
    """Return a helpful patient message, not a generic HTTP status phrase."""
    cleaned = str(message or "").strip()
    if not cleaned:
        return fallback
    if cleaned.lower() in _GENERIC_HTTP_PHRASES:
        return fallback
    return cleaned


DOCUMENT_TYPE_LABELS = {
    "bill": "Hospital bill",
    "prescription": "Prescription",
    "lab_report": "Lab report",
    "discharge_summary": "Discharge summary",
    "preauth_letter": "Pre-authorization letter",
}


def document_mismatch_detail(
    *,
    filename: str | None,
    assigned_type: str,
    message: str | None,
    fallback: str,
    suggested_type: str | None = None,
) -> str:
    """Name the misclassified file so the user can correct its document type."""
    display_name = str(filename or "").strip() or "This file"
    quoted = display_name if display_name == "This file" else f'"{display_name}"'
    assigned_label = DOCUMENT_TYPE_LABELS.get(
        assigned_type, assigned_type.replace("_", " ")
    )
    explanation = patient_facing_detail(message, fallback)
    text = f"{quoted} was labeled as {assigned_label}. {explanation}"
    if suggested_type and suggested_type != assigned_type:
        suggested_label = DOCUMENT_TYPE_LABELS.get(
            suggested_type, suggested_type.replace("_", " ")
        )
        text += f" Try changing the document type to {suggested_label}."
    return text
