"""KCR Kit / Pregnancy Nutrition Kit advisory for Telangana."""

from __future__ import annotations

from typing import Any

SCHEME_NAME = "KCR Kit / Pregnancy Nutrition Kit"
TITLE = f"{SCHEME_NAME} Advisory"

DESCRIPTION = (
    "This scheme provides support to eligible pregnant women in Telangana by "
    "supplying essential nutrition/kit benefits during pregnancy. This section "
    "is advisory and does not replace official verification."
)

ELIGIBILITY_SUMMARY = [
    "Patient must be a pregnant woman.",
    "Patient must be at least 18 years old.",
    "Patient must be a resident of Telangana.",
    "Family monthly income should be below ₹10,000.",
    "Patient should be identified/verified through Anganwadi Worker process where applicable.",
    "Patient should preferably have Telangana-linked Aadhaar details as required by the scheme rules.",
]

EXCLUSIONS = [
    "Not eligible if the beneficiary has more than two live children.",
    "Not eligible if treatment is taken from a non-government/private hospital.",
    "Not eligible if Aadhaar does not belong to Telangana.",
    "Non-residents of Telangana are not eligible.",
]

APPLICATION_PROCESS = [
    "Eligible beneficiaries are usually identified by Anganwadi Workers.",
    "Anganwadi Workers conduct local surveys and verify pregnancy, residence, income, and other eligibility conditions.",
    "The patient should contact the nearest Anganwadi Centre or concerned local health/welfare authority.",
    "Submit Aadhaar and any required supporting details for verification.",
    "Final approval and benefit distribution will depend on official verification.",
]

DOCUMENTS_REQUIRED = [
    "Aadhaar Card",
    "Any pregnancy-related medical record if required by local authority",
    "Residence/income details if asked during verification",
    "Anganwadi Worker verification details if applicable",
]

IMPORTANT_NOTE = (
    "This advisory is based on the scheme details entered in the app. Final "
    "eligibility, approval, and benefits must be verified with the concerned "
    "Anganwadi Worker, local health department, or Telangana government authority."
)


def _is_potentially_eligible(
    *,
    kcr_is_pregnant: bool,
    kcr_is_telangana_resident: bool,
    kcr_age_18_or_above: bool,
    kcr_income_below_10000: bool,
    kcr_government_hospital_treatment: bool,
    kcr_more_than_two_live_children: bool,
    kcr_aadhaar_telangana: bool,
) -> bool:
    return (
        kcr_is_pregnant
        and kcr_is_telangana_resident
        and kcr_age_18_or_above
        and kcr_income_below_10000
        and kcr_government_hospital_treatment
        and not kcr_more_than_two_live_children
        and kcr_aadhaar_telangana
    )


def _resolve_applicant_status(
    *,
    kcr_is_pregnant: bool,
    kcr_is_telangana_resident: bool,
    kcr_age_18_or_above: bool,
    kcr_income_below_10000: bool,
    kcr_government_hospital_treatment: bool,
    kcr_more_than_two_live_children: bool,
    kcr_aadhaar_telangana: bool,
    kcr_identified_by_anganwadi_worker: bool = False,
) -> tuple[str, list[str]]:
    eligible = _is_potentially_eligible(
        kcr_is_pregnant=kcr_is_pregnant,
        kcr_is_telangana_resident=kcr_is_telangana_resident,
        kcr_age_18_or_above=kcr_age_18_or_above,
        kcr_income_below_10000=kcr_income_below_10000,
        kcr_government_hospital_treatment=kcr_government_hospital_treatment,
        kcr_more_than_two_live_children=kcr_more_than_two_live_children,
        kcr_aadhaar_telangana=kcr_aadhaar_telangana,
    )

    if eligible:
        messages = [
            "Patient may be eligible for the KCR Kit / Pregnancy Nutrition Kit.",
        ]
        if kcr_is_pregnant and kcr_age_18_or_above:
            messages.append("Patient is pregnant and 18 years or older.")
        elif kcr_is_pregnant:
            messages.append("Patient is pregnant.")
        if kcr_is_telangana_resident:
            messages.append("Patient is a Telangana resident.")
        if kcr_income_below_10000:
            messages.append("Family monthly income is below ₹10,000.")
        if kcr_government_hospital_treatment:
            messages.append("Patient is receiving treatment at a government hospital.")
        if not kcr_more_than_two_live_children:
            messages.append("Patient has two or fewer live children.")
        if kcr_aadhaar_telangana:
            messages.append("Patient has Telangana-linked Aadhaar.")
        if kcr_identified_by_anganwadi_worker:
            messages.append("Patient was identified by an Anganwadi Worker.")
        messages.append("Final approval still requires official verification.")
        return "May Be Eligible", messages

    messages = [
        "Patient does not appear eligible for the KCR Kit based on the details provided.",
    ]
    if not kcr_is_pregnant:
        messages.append("Patient is not marked as pregnant.")
    if not kcr_age_18_or_above:
        messages.append("Patient is below 18 years.")
    if not kcr_is_telangana_resident:
        messages.append("Patient is not a Telangana resident.")
    if not kcr_income_below_10000:
        messages.append("Family monthly income is not below ₹10,000.")
    if not kcr_government_hospital_treatment:
        messages.append("Patient is not receiving treatment at a government hospital.")
    if kcr_more_than_two_live_children:
        messages.append("Patient has more than two live children.")
    if not kcr_aadhaar_telangana:
        messages.append("Patient does not have Telangana-linked Aadhaar.")

    return "Not Eligible", messages


def build_kcr_kit_advisory(
    *,
    kcr_kit_selected: bool,
    kcr_is_pregnant: bool = False,
    kcr_is_telangana_resident: bool = False,
    kcr_age_18_or_above: bool = False,
    kcr_income_below_10000: bool = False,
    kcr_government_hospital_treatment: bool = False,
    kcr_more_than_two_live_children: bool = False,
    kcr_aadhaar_telangana: bool = False,
    kcr_identified_by_anganwadi_worker: bool = False,
) -> dict[str, Any] | None:
    if not kcr_kit_selected:
        return None

    status_badge, applicant_messages = _resolve_applicant_status(
        kcr_is_pregnant=kcr_is_pregnant,
        kcr_is_telangana_resident=kcr_is_telangana_resident,
        kcr_age_18_or_above=kcr_age_18_or_above,
        kcr_income_below_10000=kcr_income_below_10000,
        kcr_government_hospital_treatment=kcr_government_hospital_treatment,
        kcr_more_than_two_live_children=kcr_more_than_two_live_children,
        kcr_aadhaar_telangana=kcr_aadhaar_telangana,
        kcr_identified_by_anganwadi_worker=kcr_identified_by_anganwadi_worker,
    )

    return {
        "scheme_name": SCHEME_NAME,
        "title": TITLE,
        "description": DESCRIPTION,
        "eligibility_summary": ELIGIBILITY_SUMMARY,
        "exclusions": EXCLUSIONS,
        "status_badge": status_badge,
        "applicant_status_messages": applicant_messages,
        "applicant_status": " ".join(applicant_messages),
        "application_process": APPLICATION_PROCESS,
        "documents_required": DOCUMENTS_REQUIRED,
        "important_note": IMPORTANT_NOTE,
        "kcr_is_pregnant": kcr_is_pregnant,
        "kcr_is_telangana_resident": kcr_is_telangana_resident,
        "kcr_age_18_or_above": kcr_age_18_or_above,
        "kcr_income_below_10000": kcr_income_below_10000,
        "kcr_government_hospital_treatment": kcr_government_hospital_treatment,
        "kcr_more_than_two_live_children": kcr_more_than_two_live_children,
        "kcr_aadhaar_telangana": kcr_aadhaar_telangana,
        "kcr_identified_by_anganwadi_worker": kcr_identified_by_anganwadi_worker,
    }
