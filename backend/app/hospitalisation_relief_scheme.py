"""Hospitalisation Relief Scheme advisory for Telangana BOCW Welfare Board."""

from __future__ import annotations

from typing import Any

SCHEME_NAME = "Hospitalisation Relief Scheme"
BOARD_NAME = (
    "Telangana Building & Other Construction Workers Welfare Board"
)

ELIGIBILITY_SUMMARY = [
    (
        "Available for registered building and other construction workers under "
        "the Telangana Building & Other Construction Workers Welfare Board."
    ),
    (
        "The worker must have been hospitalized for at least 5 days due to an "
        "accident or disease."
    ),
    (
        "Relief may be extended up to 3 months in severe or terminal conditions, "
        "subject to approval."
    ),
]

BENEFIT = {
    "daily_relief": "₹300 per day of hospitalization.",
    "monthly_maximum": "Maximum reimbursement/relief: ₹4,500 per month.",
}

APPLICANT_STATUS_REGISTERED = (
    "You indicated that the patient is a registered construction worker. "
    "The patient may be eligible if the hospitalization period and documents "
    "meet the scheme rules."
)

APPLICANT_STATUS_NOT_REGISTERED = (
    "You indicated that the patient is not registered as a construction worker. "
    "Registration with the Telangana Building & Other Construction Workers "
    "Welfare Board is required for this scheme."
)

HOW_TO_APPLY = [
    "Visit the official Telangana labour/board website.",
    "Go to the Downloads section.",
    "Download the application form for the Hospitalisation Relief Scheme.",
    "Fill all required details carefully.",
    "Attach the required documents.",
    "Submit the signed application to the concerned Assistant Labour Officer.",
    (
        "Ask for an acknowledgement/receipt with date, time, and reference "
        "number if available."
    ),
]

DOCUMENTS_REQUIRED = [
    "Passport-size photograph",
    "BOCW registration card attested copy",
    "Renewal challan copy",
    "Hospital admission card",
    (
        "Doctor certificate / medical certificate issued not below the rank of "
        "Assistant Civil Surgeon of a Government Hospital or Primary Health Centre"
    ),
    "Advance stamped receipt",
    "Attested copy of first page of bank passbook",
]

IMPORTANT_NOTE = (
    "This section is an advisory based on the Hospitalisation Relief Scheme "
    "details. Final eligibility, approval, and reimbursement amount must be "
    "verified with the Telangana Building & Other Construction Workers Welfare "
    "Board / concerned Assistant Labour Officer."
)


def build_hospitalisation_relief_advisory(
    *,
    hospitalisation_relief_scheme_selected: bool,
    is_registered_construction_worker: bool,
) -> dict[str, Any] | None:
    if not hospitalisation_relief_scheme_selected:
        return None

    return {
        "scheme_name": SCHEME_NAME,
        "board_name": BOARD_NAME,
        "title": f"{SCHEME_NAME} Advisory",
        "eligibility_summary": ELIGIBILITY_SUMMARY,
        "benefit": BENEFIT,
        "is_registered_construction_worker": is_registered_construction_worker,
        "applicant_status": (
            APPLICANT_STATUS_REGISTERED
            if is_registered_construction_worker
            else APPLICANT_STATUS_NOT_REGISTERED
        ),
        "how_to_apply": HOW_TO_APPLY,
        "documents_required": DOCUMENTS_REQUIRED,
        "important_note": IMPORTANT_NOTE,
    }
