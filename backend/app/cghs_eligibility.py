"""CGHS eligibility criteria advisory — display only, not eligibility determination."""

from __future__ import annotations

from typing import Any

TITLE = "CGHS Eligibility Criteria"
SUBTITLE = (
    "Central Government Health Scheme eligibility depends on beneficiary category "
    "and residence in a CGHS-covered city."
)
BADGE = "Eligibility Advisory"

RESIDENCE_RULE = (
    "Residence, and not headquarters, is the criterion for determining eligibility "
    "of a Central Government servant for availing medical facilities under CGHS. "
    "Central Government employees and eligible family members residing in notified "
    "CGHS-covered cities are covered under the scheme."
)

IMPORTANT_NOTE = (
    "This section is an eligibility advisory based on CGHS beneficiary categories. "
    "Final eligibility, CGHS card validity, dependent status, city coverage, "
    "contribution requirements, and entitlement must be verified through official "
    "CGHS/MoHFW sources or the concerned CGHS Wellness Centre."
)

FALLBACK_NOTE = (
    "CGHS rates are used only as a benchmark/fallback here. "
    "CGHS eligibility is separate."
)

RESIDENCE_CONFIRMED = "Patient indicated residence in a CGHS-covered city."
RESIDENCE_NOT_CONFIRMED = (
    "Patient indicated they do not reside in a CGHS-covered city. "
    "CGHS eligibility/facility access should be verified."
)
RESIDENCE_UNKNOWN = (
    "CGHS-covered city residence was not confirmed. "
    "Verify city coverage with CGHS/MoHFW."
)

CGHS_ELIGIBILITY_GROUPS: list[dict[str, Any]] = [
    {
        "id": "central_gov_employees",
        "title": "Central Government Employees and Pensioners",
        "items": [
            (
                "All Central Government employees paid from Central Civil Estimates, "
                "except Railways and Delhi Administration, including their families."
            ),
            (
                "Pensioners of Central Government, except pensioners belonging to "
                "Railways and Armed Forces, including their families."
            ),
            (
                "Central Government pensioners retiring with Contributory Provident "
                "Fund benefits and their families."
            ),
            "Widows of Central Government pensioners receiving family pension.",
            (
                "Central Government servants deputed to semi-government/autonomous "
                "bodies receiving substantial Central Government grants."
            ),
            (
                "Central Government employees on deputation to statutory/autonomous "
                "bodies during deputation."
            ),
            (
                "Work-charged and industrial staff working in establishments run by "
                "Central Government ministries/departments from the date of joining."
            ),
            (
                "PSU absorbees who had commuted 100% pension and later restored "
                "1/3rd pension after 15 years."
            ),
        ],
    },
    {
        "id": "defence_police_capf",
        "title": "Defence, Police, CAPF, and Related Personnel",
        "items": [
            "Delhi Police personnel and their families, in Delhi only.",
            (
                "Civilian employees of Defence paid from Defence Service Estimates, "
                "except in Mumbai where applicable."
            ),
            (
                "Military officers on deputation to civil departments and paid from "
                "Central Civil Estimates."
            ),
            "CISF personnel and families, and CAPF personnel posted in CGHS cities.",
            (
                "Defence Industrial Employees of Naval Dockyard, Central Ordnance "
                "Depot and AFMSD in Mumbai."
            ),
        ],
    },
    {
        "id": "railway_audit",
        "title": "Railway and Audit Related Categories",
        "items": [
            "Railway Board employees.",
            "Serving and retired Railway Audit Staff.",
            "Pensioners of Ordnance factories.",
            (
                "Employees of Ordnance Factory Board Headquarters, Kolkata and "
                "Ordnance Equipment Factories Headquarters, Kanpur."
            ),
            (
                "Retired Divisional Accountants of Indian Audit and Accounts Department "
                "whose pay/pension are borne by State Governments."
            ),
            (
                "Retired Divisional Accounts Officers and Divisional Accountants of the "
                "Office of Comptroller and Auditor General of India."
            ),
        ],
    },
    {
        "id": "constitutional",
        "title": "Constitutional / Public Functionaries",
        "items": [
            "Ex-Governors and Lt. Governors and their families.",
            "Ex-Vice Presidents and their families.",
            "Parliamentary Secretaries of the Central Government and their families.",
            "Members of Parliament and their families.",
            "Ex-Members of Parliament.",
            "Family members of deceased Ex-Members of Parliament.",
            "Sitting Judges of Supreme Court and High Court of Delhi.",
            "Former Judges of Supreme Court and High Courts.",
        ],
    },
    {
        "id": "special_categories",
        "title": "Special Eligible Categories",
        "items": [
            (
                "Freedom Fighters and family members receiving Central Pension under "
                "Swatantrata Sainik Samman Pension Scheme."
            ),
            (
                "Accredited Journalist producing certificate from Press Council of India "
                "stating membership of Press Association, New Delhi, for OPD and at "
                "RML Hospital."
            ),
            (
                "Members of Staff Side of the National Council of Joint Consultative "
                "Machinery, even if not serving as Central Government employees."
            ),
            (
                "Employees of Kendriya Vidyalaya Sangathan stationed at Delhi & NCR, "
                "Kolkata, Chennai, Hyderabad, Mumbai and Bengaluru."
            ),
            "Employees of Supreme Court Legal Services Committee.",
            "Employees of India Pharmacopoeia Commission and their families.",
            "Persons employed in semi-government/autonomous bodies permitted to join CGHS.",
            (
                "Employees of statutory/autonomous bodies of Central Government who "
                "receive Central Civil Pension."
            ),
            (
                "All India Service pensioners who retire while serving under the State, "
                "at their option."
            ),
        ],
    },
    {
        "id": "family_dependents",
        "title": "Family / Dependent Coverage Situations",
        "items": [
            (
                "Families of Government servants transferred to a non-CGHS area, for "
                "maximum six months on advance CGHS contribution payment."
            ),
            (
                "Families of IAS officers on North-Eastern Cadre staying back in Delhi "
                "after officer repatriation, if they continue to occupy Government "
                "accommodation and pay CGHS contribution in advance."
            ),
            "Same applies to families of IAS officers of J&K Cadre.",
            (
                "Child drawing pension on death of a Central Government employee, "
                "including minor brothers and sisters of such child."
            ),
            (
                "Family/dependent members of a CGHS beneficiary who stay back in "
                "CGHS-covered area after posting of employee to N.E. region including "
                "Sikkim, Andaman & Nicobar, Lakshadweep, Ladakh, or CAPF personnel "
                "posted in Left Wing Extremist areas, on payment of annual CGHS "
                "contribution in advance."
            ),
        ],
    },
]

PREVIEW_MAY_BE_ELIGIBLE = (
    "Patient may fall under a CGHS eligible category, subject to CGHS card and "
    "official verification."
)
PREVIEW_NOT_CONFIRMED = (
    "CGHS eligibility could not be confirmed from the information provided. "
    "Verify beneficiary category and CGHS card status."
)


def _category_is_confirmed(beneficiary_category: str | None) -> bool:
    return bool(beneficiary_category and beneficiary_category != "not_sure")


def build_residence_advisory(
    resides_in_covered_city: bool | None = None,
) -> str:
    if resides_in_covered_city is True:
        return RESIDENCE_CONFIRMED
    if resides_in_covered_city is False:
        return RESIDENCE_NOT_CONFIRMED
    return RESIDENCE_UNKNOWN


def build_cghs_eligibility_preview(
    *,
    beneficiary_category: str | None = None,
    resides_in_covered_city: bool | None = None,
) -> list[str]:
    messages: list[str] = [build_residence_advisory(resides_in_covered_city)]
    category_confirmed = _category_is_confirmed(beneficiary_category)

    if category_confirmed and resides_in_covered_city is True:
        messages.append(PREVIEW_MAY_BE_ELIGIBLE)
    elif not category_confirmed or beneficiary_category == "not_sure":
        messages.append(PREVIEW_NOT_CONFIRMED)

    return messages


def _cghs_rates_used(
    *,
    comparison_scheme: str,
    cghs_fallback_from_aarogya: bool = False,
    line_items: list[dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    """Return whether CGHS advisory should appear and display mode (full|fallback)."""
    has_item_fallback = any(
        item.get("aarogyasri_fallback_used") for item in (line_items or [])
    )

    if comparison_scheme == "cghs":
        if cghs_fallback_from_aarogya:
            return True, "fallback"
        return True, "full"

    if cghs_fallback_from_aarogya or has_item_fallback:
        return True, "fallback"

    return False, "full"


def build_cghs_eligibility_advisory(
    *,
    comparison_scheme: str,
    cghs_fallback_from_aarogya: bool = False,
    line_items: list[dict[str, Any]] | None = None,
    beneficiary_category: str | None = None,
    eligible_category_confirmed: bool | None = None,
    resides_in_covered_city: bool | None = None,
) -> dict[str, Any] | None:
    show, mode = _cghs_rates_used(
        comparison_scheme=comparison_scheme,
        cghs_fallback_from_aarogya=cghs_fallback_from_aarogya,
        line_items=line_items,
    )
    if not show:
        return None

    preview = build_cghs_eligibility_preview(
        beneficiary_category=beneficiary_category,
        resides_in_covered_city=resides_in_covered_city,
    )

    return {
        "title": TITLE,
        "subtitle": SUBTITLE,
        "badge": BADGE,
        "residence_rule": RESIDENCE_RULE,
        "residence_advisory": build_residence_advisory(resides_in_covered_city),
        "groups": CGHS_ELIGIBILITY_GROUPS,
        "important_note": IMPORTANT_NOTE,
        "mode": mode,
        "fallback_note": FALLBACK_NOTE,
        "eligibility_preview": preview,
        "beneficiary_category": beneficiary_category,
        "eligible_category_confirmed": eligible_category_confirmed,
        "resides_in_covered_city": resides_in_covered_city,
    }
