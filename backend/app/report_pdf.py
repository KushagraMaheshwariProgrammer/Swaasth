"""Unified report PDF rendering for all comparison schemes.

New schemes register an HTML renderer via ``register_scheme``; the client sends
the full report object (from live results or bill history) to
``/api/reports/render-pdf``.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from html import escape
from typing import Any

from app.aarogya_reports import render_report_html as render_aarogya_report_html
from app.hospitalisation_relief_scheme import build_hospitalisation_relief_advisory
from app.kcr_kit_scheme import build_kcr_kit_advisory

RenderHtmlFn = Callable[[dict[str, Any]], str]

_SCHEME_RENDERERS: dict[str, RenderHtmlFn] = {}

BILL_DISCLAIMER = (
    "This report is based on extracted bill information and reference rates "
    "available in the application. OCR errors, package conditions, exclusions, "
    "and uncertain item matches may require manual verification."
)

_SCHEME_LABELS: dict[str, str] = {
    "cghs": "CGHS Benchmark",
    "hbp_pmjay": "PM-JAY HBP 2022 Benchmark",
    "aarogya_bhadratha": "Aarogya Bhadratha Scheme",
    "rajiv_aarogyasri": "Rajiv Aarogyasri Package Benchmark",
}

_HOSPITAL_TYPE_LABELS: dict[str, str] = {
    "general": "General hospital",
    "speciality": "Speciality hospital",
}


def register_scheme(scheme_id: str, render_html: RenderHtmlFn) -> None:
    _SCHEME_RENDERERS[scheme_id] = render_html


def resolve_scheme_id(report: dict[str, Any]) -> str:
    report_kind = report.get("report_kind")
    if isinstance(report_kind, str) and report_kind in _SCHEME_RENDERERS:
        return report_kind

    comparison_scheme = (report.get("comparison_settings") or {}).get(
        "comparison_scheme"
    )
    if isinstance(comparison_scheme, str) and comparison_scheme in _SCHEME_RENDERERS:
        return comparison_scheme

    if report.get("line_items"):
        return "cghs"

    if report.get("treatment_audit_flags"):
        return "prescription"

    raise ValueError("Could not determine report scheme.")


def validate_report(report: dict[str, Any], scheme_id: str) -> None:
    if scheme_id == "aarogya_bhadratha":
        if not report.get("comparison"):
            raise ValueError("Invalid Aarogya Bhadratha report payload.")
        return

    if scheme_id == "prescription":
        if not report.get("treatment_audit_flags"):
            raise ValueError("Invalid prescription report payload.")
        return

    if not report.get("line_items"):
        raise ValueError("Invalid bill comparison report payload.")


def _fmt_currency(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _flag_label(flag: Any) -> str:
    if flag == "overpriced":
        return "Overpriced"
    if flag == "acceptable":
        return "Acceptable"
    return "No Data"


def _flag_color(flag: Any) -> str:
    if flag == "overpriced":
        return "#c0392b"
    if flag == "acceptable":
        return "#1e8449"
    return "#7f8c8d"


def _reference_rate(item: dict[str, Any]) -> tuple[Any, str]:
    if item.get("comparison_source") == "pharma" or item.get("category") == "medicine":
        return item.get("pharma_rate"), "NPPA Ceiling"
    if item.get("comparison_source") == "hbp":
        return item.get("hbp_rate"), "PM-JAY HBP Rate"
    if item.get("comparison_source") == "aarogyasri":
        return item.get("aarogyasri_rate"), "Aarogyasri Package Rate"
    return item.get("cghs_rate"), "CGHS Rate"


def _scheme_title(scheme_id: str) -> str:
    label = _SCHEME_LABELS.get(scheme_id, scheme_id.replace("_", " ").title())
    return f"{label} Bill Comparison Report"


def _render_hospitalisation_relief_advisory_html(report: dict[str, Any]) -> str:
    advisory = report.get("hospitalisation_relief_advisory")
    if not advisory:
        patient = report.get("patient") or {}
        advisory = build_hospitalisation_relief_advisory(
            hospitalisation_relief_scheme_selected=bool(
                patient.get("hospitalisation_relief_scheme_selected")
            ),
            is_registered_construction_worker=bool(
                patient.get("is_registered_construction_worker")
            ),
        )
    if not advisory:
        return ""

    eligibility_rows = "".join(
        f"<li>{escape(str(item))}</li>"
        for item in (advisory.get("eligibility_summary") or [])
    )
    benefit = advisory.get("benefit") or {}
    benefit_rows = "".join(
        f"<li>{escape(str(item))}</li>"
        for item in (
            benefit.get("daily_relief"),
            benefit.get("monthly_maximum"),
        )
        if item
    )
    apply_rows = "".join(
        f"<li>{escape(str(step))}</li>"
        for step in (advisory.get("how_to_apply") or [])
    )
    document_rows = "".join(
        f"<li>{escape(str(doc))}</li>"
        for doc in (advisory.get("documents_required") or [])
    )

    return f"""
  <h2>{escape(str(advisory.get('title', 'Hospitalisation Relief Scheme Advisory')))}</h2>
  <div class='hrs-pdf-card'>
    <h3>Eligibility Summary</h3>
    <ul>{eligibility_rows}</ul>
  </div>
  <div class='hrs-pdf-card'>
    <h3>Benefit</h3>
    <ul>{benefit_rows}</ul>
  </div>
  <div class='hrs-pdf-card'>
    <h3>Applicant Status</h3>
    <p>{escape(str(advisory.get('applicant_status', '')))}</p>
  </div>
  <div class='hrs-pdf-card'>
    <h3>How to Apply</h3>
    <ol>{apply_rows}</ol>
  </div>
  <div class='hrs-pdf-card'>
    <h3>Documents Required</h3>
    <ul>{document_rows}</ul>
  </div>
  <p class='hrs-pdf-note'>{escape(str(advisory.get('important_note', '')))}</p>
"""


def _render_rajiv_aarogyasri_report_html(report: dict[str, Any]) -> str:
    rajiv = report.get("rajiv_aarogyasri_report")
    if not rajiv or not rajiv.get("selected"):
        return ""

    eligibility = rajiv.get("eligibility_snapshot") or {}
    hospital = rajiv.get("hospital_verification") or {}
    comparisons = rajiv.get("package_comparisons") or []
    advisories = rajiv.get("advisories") or []

    def yes_no(value: Any) -> str:
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        return "—"

    preview_rows = "".join(
        f"<li>{escape(str(message))}</li>"
        for message in (rajiv.get("eligibility_preview") or [])
        if message
    )
    comparison_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('bill_item_name', '')))}</td>"
        f"<td class='num'>{_fmt_currency(item.get('charged_amount'))}</td>"
        f"<td>{escape(str(item.get('matched_package_name') or '—'))}</td>"
        f"<td class='num'>{_fmt_currency(item.get('approved_rate'))}</td>"
        f"<td class='num'>{_fmt_currency(item.get('excess_amount'))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('source_file') or '—'))}</td>"
        "</tr>"
        for item in comparisons
    )
    advisory_rows = "".join(
        "<li>"
        f"<b>{escape(str(advisory.get('title', '')))}</b>"
        + (
            f" · effective {escape(str(advisory.get('effective_date')))}"
            if advisory.get("effective_date")
            else ""
        )
        + f"<br>{escape(str(advisory.get('message', '')))}"
        "</li>"
        for advisory in advisories
    )

    family_amount = eligibility.get("family_coverage_used_amount")
    family_amount_line = ""
    if family_amount is not None:
        family_amount_line = (
            f"<li>Family used coverage amount: {_fmt_currency(family_amount)}</li>"
        )

    return f"""
  <h2>Rajiv Aarogyasri / Aarogyasri Cheyutha</h2>
  <div class='hrs-pdf-card'>
    <h3>Scheme Status</h3>
    <ul>
      <li>Telangana resident: {escape(yes_no(eligibility.get('telangana_resident')))}</li>
      <li>Eligible card/scheme eligibility: {escape(yes_no(eligibility.get('has_eligible_card')))}</li>
      <li>Aadhaar: {escape(yes_no(eligibility.get('has_aadhaar')))}</li>
      <li>Cancer-related treatment: {escape(yes_no(eligibility.get('cancer_related')))}</li>
      {family_amount_line}
    </ul>
    {"<ul>" + preview_rows + "</ul>" if preview_rows else ""}
  </div>
  <div class='hrs-pdf-card'>
    <h3>Hospital Verification</h3>
    <ul>
      <li>OCR hospital name: {escape(str(hospital.get('ocr_hospital_name') or '—'))}</li>
      <li>Matched hospital: {escape(str(hospital.get('matched_hospital_name') or '—'))}</li>
      <li>Match confidence: {escape(str(hospital.get('confidence_score') or '—'))}</li>
      <li>Location: {escape(', '.join(part for part in [hospital.get('city'), hospital.get('district'), hospital.get('state')] if part) or '—')}</li>
      <li>Hospital type: {escape(str(hospital.get('hospital_type') or '—'))}</li>
      <li>Empanelled status: {escape(str(hospital.get('empanelled_status') or '—'))}</li>
      <li>Status: {escape(str(hospital.get('status') or '—'))}</li>
    </ul>
  </div>
  {"<h3>Aarogyasri Package Comparison</h3><table><tr><th>Bill item</th><th class='num'>Charged</th><th>Matched package</th><th class='num'>Approved rate</th><th class='num'>Excess</th><th>Status</th><th>Source</th></tr>" + comparison_rows + "</table>" if comparison_rows else ""}
  {"<div class='hrs-pdf-card'><h3>Advisories</h3><ul>" + advisory_rows + "</ul></div>" if advisory_rows else ""}
  <p class='hrs-pdf-note'>{escape(str(rajiv.get('disclaimer', '')))}</p>
"""


def _render_kcr_kit_advisory_html(report: dict[str, Any]) -> str:
    advisory = report.get("kcr_kit_advisory")
    if not advisory:
        patient = report.get("patient") or {}
        advisory = build_kcr_kit_advisory(
            kcr_kit_selected=bool(patient.get("kcr_kit_selected")),
            kcr_is_pregnant=bool(patient.get("kcr_is_pregnant")),
            kcr_is_telangana_resident=bool(patient.get("kcr_is_telangana_resident")),
            kcr_age_18_or_above=bool(patient.get("kcr_age_18_or_above")),
            kcr_income_below_10000=bool(patient.get("kcr_income_below_10000")),
            kcr_government_hospital_treatment=bool(
                patient.get("kcr_government_hospital_treatment")
            ),
            kcr_more_than_two_live_children=bool(
                patient.get("kcr_more_than_two_live_children")
            ),
            kcr_aadhaar_telangana=bool(patient.get("kcr_aadhaar_telangana")),
            kcr_identified_by_anganwadi_worker=bool(
                patient.get("kcr_identified_by_anganwadi_worker")
            ),
        )
    if not advisory:
        return ""

    eligibility_rows = "".join(
        f"<li>{escape(str(item))}</li>"
        for item in (advisory.get("eligibility_summary") or [])
    )
    exclusion_rows = "".join(
        f"<li>{escape(str(item))}</li>"
        for item in (advisory.get("exclusions") or [])
    )
    status_messages = advisory.get("applicant_status_messages") or [
        advisory.get("applicant_status", "")
    ]
    status_rows = "".join(
        f"<li>{escape(str(message))}</li>"
        for message in status_messages
        if message
    )
    process_rows = "".join(
        f"<li>{escape(str(step))}</li>"
        for step in (advisory.get("application_process") or [])
    )
    document_rows = "".join(
        f"<li>{escape(str(doc))}</li>"
        for doc in (advisory.get("documents_required") or [])
    )
    description = advisory.get("description") or ""
    status_badge = advisory.get("status_badge") or "Advisory"

    return f"""
  <h2>{escape(str(advisory.get('title', 'KCR Kit / Pregnancy Nutrition Kit Advisory')))}</h2>
  <p><b>Status:</b> {escape(str(status_badge))}</p>
  <p>{escape(str(description))}</p>
  <div class='hrs-pdf-card'>
    <h3>Eligibility Summary</h3>
    <ul>{eligibility_rows}</ul>
  </div>
  <div class='hrs-pdf-card'>
    <h3>Exclusions</h3>
    <ul>{exclusion_rows}</ul>
  </div>
  <div class='hrs-pdf-card'>
    <h3>Applicant Status</h3>
    <ul>{status_rows}</ul>
  </div>
  <div class='hrs-pdf-card'>
    <h3>Application Process</h3>
    <ol>{process_rows}</ol>
  </div>
  <div class='hrs-pdf-card'>
    <h3>Documents Required</h3>
    <ul>{document_rows}</ul>
  </div>
  <p class='hrs-pdf-note'>{escape(str(advisory.get('important_note', '')))}</p>
"""


def render_bill_comparison_html(report: dict[str, Any]) -> str:
    settings = report.get("comparison_settings") or {}
    scheme_id = settings.get("comparison_scheme") or "cghs"
    title = _scheme_title(scheme_id)
    scheme_label = _SCHEME_LABELS.get(scheme_id, scheme_id)

    patient = report.get("patient") or {}
    hospital = report.get("hospital") or {}
    line_items = report.get("line_items") or []
    audit_flags = (report.get("audit_flags") or {}).get("flags") or []
    jan_aushadhi = report.get("jan_aushadhi") or {}
    jan_matches = jan_aushadhi.get("matches") or []

    total_charged = 0.0
    total_overcharged = 0.0
    items_flagged = 0

    rows_html: list[str] = []
    for item in line_items:
        charged = float(item.get("total_price") or 0)
        diff = float(item.get("price_difference") or 0)
        total_charged += charged
        total_overcharged += max(diff, 0)
        if item.get("flag") == "overpriced":
            items_flagged += 1

        reference_rate, reference_label = _reference_rate(item)
        flag = item.get("flag")
        matched = item.get("matched_reference_item") or "—"
        code_bits: list[str] = []
        if item.get("hbp_procedure_code"):
            code_bits.append(str(item["hbp_procedure_code"]))
        elif item.get("cghs_code"):
            code_bits.append(str(item["cghs_code"]))
        if item.get("pharma_product_id"):
            code_bits.append(f"NPPA #{item['pharma_product_id']}")
        if code_bits:
            matched = f"{matched} ({', '.join(code_bits)})"

        rows_html.append(
            "<tr>"
            f"<td>{escape(str(item.get('item_name', '')))}</td>"
            f"<td class='num'>{escape(str(item.get('quantity', '')))}</td>"
            f"<td class='num'>{_fmt_currency(item.get('total_price'))}</td>"
            f"<td>{escape(str(matched))}</td>"
            f"<td class='num'>{_fmt_currency(reference_rate)}</td>"
            f"<td>{escape(reference_label)}</td>"
            f"<td class='num'>{_fmt_currency(item.get('price_difference'))}</td>"
            f"<td style='color:{_flag_color(flag)}'>{escape(_flag_label(flag))}</td>"
            "</tr>"
        )

    location_bits: list[str] = []
    if settings.get("city") and settings.get("state_name"):
        location_bits.append(f"{settings['city']}, {settings['state_name']}")
    tier_label = settings.get("tier_label") or settings.get("tier") or "—"
    hospital_type = _HOSPITAL_TYPE_LABELS.get(
        settings.get("hospital_type", ""), settings.get("hospital_type", "—")
    )
    rate_type_label = settings.get("rate_type_label") or settings.get("rate_type") or "—"

    jan_rows = []
    for match in jan_matches:
        generic = match.get("generic_name")
        bill_name = match.get("bill_item_name")
        generic_note = ""
        if generic and generic != bill_name:
            generic_note = f" · matched as {escape(str(generic))}"
        mrp_note = ""
        if match.get("mrp") is not None:
            mrp_note = f" · Jan Aushadhi MRP: {_fmt_currency(match.get('mrp'))}"
        jan_rows.append(
            "<li>"
            f"<b>{escape(str(bill_name or ''))}</b>"
            f"{generic_note}"
            f"{mrp_note}"
            "</li>"
        )

    audit_rows = []
    for flag in audit_flags:
        audit_rows.append(
            "<tr>"
            f"<td>{escape(str(flag.get('item', '')))}</td>"
            f"<td>{escape(str(flag.get('type', '')).replace('_', ' '))}</td>"
            f"<td>{escape(str(flag.get('severity', '')))}</td>"
            f"<td>{escape(str(flag.get('reason', '')))}</td>"
            f"<td>{escape(str(flag.get('recommendation', '')))}</td>"
            "</tr>"
        )

    treatment_audit = report.get("treatment_audit_flags") or {}
    treatment_flags = treatment_audit.get("flags") or []
    treatment_rows = []
    for flag in treatment_flags:
        reference = flag.get("stg_reference") or {}
        ref_text = reference.get("condition") or ""
        if reference.get("section"):
            ref_text = f"{ref_text} · {reference.get('section')}"
        if reference.get("page") is not None:
            ref_text = f"{ref_text} · p.{reference.get('page')}"
        treatment_rows.append(
            "<tr>"
            f"<td>{escape(str(flag.get('item', '')))}</td>"
            f"<td>{escape(str(flag.get('type', '')).replace('_', ' '))}</td>"
            f"<td>{escape(str(flag.get('severity', '')))}</td>"
            f"<td>{escape(str(flag.get('reason', '')))}</td>"
            f"<td>{escape(str(flag.get('recommendation', '')))}</td>"
            f"<td>{escape(ref_text)}</td>"
            "</tr>"
        )

    nabh_line = ""
    if hospital.get("is_accredited") is not None:
        if hospital.get("is_accredited"):
            nabh_line = (
                f"NABH: Accredited ({escape(str(hospital.get('accreditation_status', '')))})"
            )
        else:
            nabh_line = "NABH: Not found in NABH registry"

    hrs_advisory_html = _render_hospitalisation_relief_advisory_html(report)
    kcr_advisory_html = _render_kcr_kit_advisory_html(report)
    rajiv_report_html = _render_rajiv_aarogyasri_report_html(report)

    return f"""
<html>
<head><style>
  body {{ font-family: Helvetica, Arial, sans-serif; color: #2c3e50; font-size: 10px; }}
  h1 {{ font-size: 16px; color: #1a5276; margin-bottom: 2px; }}
  h2 {{ font-size: 12px; color: #1a5276; border-bottom: 1px solid #aed6f1; padding-bottom: 2px; margin-top: 14px; }}
  .meta p {{ margin: 2px 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  th, td {{ border: 1px solid #d5dbdb; padding: 4px 5px; text-align: left; vertical-align: top; }}
  th {{ background: #eaf2f8; font-size: 9px; }}
  td.num, th.num {{ text-align: right; }}
  .summary td {{ border: none; padding: 2px 4px; }}
  .disclaimer {{ margin-top: 14px; font-size: 8.5px; color: #7f8c8d; font-style: italic; }}
  ul {{ margin: 4px 0; padding-left: 16px; }}
  ol {{ margin: 4px 0; padding-left: 16px; }}
  .hrs-pdf-card {{ background: #f4f7fb; border-left: 3px solid #5d8aa8; border-radius: 6px; padding: 8px 10px; margin: 8px 0; }}
  .hrs-pdf-card h3 {{ margin: 0 0 4px; font-size: 10px; color: #1a5276; }}
  .hrs-pdf-note {{ margin-top: 8px; font-size: 8.5px; color: #566573; font-style: italic; }}
</style></head>
<body>
  <h1>{escape(title)}</h1>
  <p><b>Scheme:</b> {escape(scheme_label)}</p>

  <h2>Patient &amp; Hospital Information</h2>
  <div class='meta'>
    <p><b>Patient:</b> {escape(str(patient.get('name', '—')))}
      {f" · {escape(str(patient.get('age')))} yrs" if patient.get('age') is not None else ''}
      {f" · {escape(str(patient.get('gender')))}" if patient.get('gender') else ''}
      {f" · Ayushman Bharat PM-JAY eligible" if patient.get('ayushman_eligible') else ''}
    </p>
    <p><b>Hospital (from bill):</b> {escape(str(hospital.get('name_from_bill', '—')))}
      {f" · {nabh_line}" if nabh_line else ''}
    </p>
    <p><b>Location:</b> {escape(', '.join(location_bits) if location_bits else '—')}</p>
    <p><b>Tier:</b> {escape(str(tier_label))} &nbsp; <b>Hospital type:</b> {escape(str(hospital_type))}</p>
    <p><b>Rate basis:</b> {escape(str(rate_type_label if scheme_id != 'hbp_pmjay' else 'PM-JAY HBP 2022 benchmark'))}</p>
    <p><b>Source file:</b> {escape(str(report.get('filename', '—')))}</p>
  </div>

  <h2>Summary</h2>
  <table class='summary'>
    <tr><td><b>Total charged</b></td><td class='num'>{_fmt_currency(total_charged)}</td></tr>
    <tr><td><b>Overcharged by</b></td><td class='num'>{_fmt_currency(total_overcharged)}</td></tr>
    <tr><td><b>Items flagged</b></td><td class='num'>{items_flagged}</td></tr>
  </table>

  {"<h2>Jan Aushadhi — subsidized medicines</h2><ul>" + ''.join(jan_rows) + "</ul><p>" + escape(str(jan_aushadhi.get('advisory', ''))) + "</p>" if jan_rows else ""}

  <h2>Item-level Comparison</h2>
  <table>
    <tr>
      <th>Bill item</th><th class='num'>Qty</th><th class='num'>Charged</th>
      <th>Matched reference</th><th class='num'>Reference rate</th><th>Rate type</th>
      <th class='num'>Difference</th><th>Status</th>
    </tr>
    {''.join(rows_html)}
  </table>

  <h2>Suspicious / Unnecessary Charges</h2>
  {"<table><tr><th>Item</th><th>Type</th><th>Severity</th><th>Reason</th><th>Recommendation</th></tr>" + ''.join(audit_rows) + "</table>" if audit_rows else "<p>No suspicious repetitions or unnecessary package-component charges detected.</p>"}

  <h2>Treatment Appropriateness (STG)</h2>
  {"<p><b>Matched STG conditions:</b> " + escape(', '.join(treatment_audit.get('matched_stg_conditions') or [])) + "</p>" if treatment_audit.get('matched_stg_conditions') else ""}
  {"<table><tr><th>Item</th><th>Type</th><th>Severity</th><th>Reason</th><th>Recommendation</th><th>STG reference</th></tr>" + ''.join(treatment_rows) + "</table>" if treatment_rows else "<p>No treatment appropriateness flags for the supplied diagnosis.</p>"}
  <p class='disclaimer'>Guideline-based indication check using CRC Standard Treatment Guidelines, 7th ed. Not a substitute for clinical judgment.</p>

  {hrs_advisory_html}

  {kcr_advisory_html}

  {rajiv_report_html}

  <p class='disclaimer'>{escape(BILL_DISCLAIMER)}</p>
</body>
</html>
"""


def render_prescription_report_html(report: dict[str, Any]) -> str:
    patient = report.get("patient") or {}
    prescription = report.get("prescription") or {}
    treatment_audit = report.get("treatment_audit_flags") or {}
    treatment_flags = treatment_audit.get("flags") or []

    medicine_rows = [
        f"<li>{escape(str(item.get('name', '')))}</li>"
        for item in prescription.get("medicines") or []
    ]
    test_rows = [
        f"<li>{escape(str(item.get('name', '')))}</li>"
        for item in prescription.get("tests") or []
    ]
    procedure_rows = [
        f"<li>{escape(str(item.get('name', '')))}</li>"
        for item in prescription.get("procedures") or []
    ]

    treatment_rows = []
    for flag in treatment_flags:
        reference = flag.get("stg_reference") or {}
        ref_text = reference.get("condition") or ""
        if reference.get("section"):
            ref_text = f"{ref_text} · {reference.get('section')}"
        treatment_rows.append(
            "<tr>"
            f"<td>{escape(str(flag.get('item', '')))}</td>"
            f"<td>{escape(str(flag.get('type', '')).replace('_', ' '))}</td>"
            f"<td>{escape(str(flag.get('severity', '')))}</td>"
            f"<td>{escape(str(flag.get('reason', '')))}</td>"
            f"<td>{escape(str(flag.get('recommendation', '')))}</td>"
            f"<td>{escape(ref_text)}</td>"
            "</tr>"
        )

    return f"""
<html>
<head><style>
  body {{ font-family: Helvetica, Arial, sans-serif; color: #2c3e50; font-size: 10px; }}
  h1 {{ font-size: 16px; color: #1a5276; margin-bottom: 2px; }}
  h2 {{ font-size: 12px; color: #1a5276; border-bottom: 1px solid #aed6f1; padding-bottom: 2px; margin-top: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  th, td {{ border: 1px solid #d5dbdb; padding: 4px 5px; text-align: left; vertical-align: top; }}
  th {{ background: #eaf2f8; font-size: 9px; }}
  .disclaimer {{ margin-top: 14px; font-size: 8.5px; color: #7f8c8d; font-style: italic; }}
  ul {{ margin: 4px 0; padding-left: 16px; }}
</style></head>
<body>
  <h1>Prescription Treatment Appropriateness Report</h1>
  <p><b>Patient:</b> {escape(str(patient.get('name', '—')))}</p>
  <p><b>Diagnosis:</b> {escape(str(report.get('diagnosis') or prescription.get('diagnosis') or '—'))}</p>
  <p><b>Source file:</b> {escape(str(report.get('filename', '—')))}</p>

  {"<h2>Medicines</h2><ul>" + ''.join(medicine_rows) + "</ul>" if medicine_rows else ""}
  {"<h2>Tests</h2><ul>" + ''.join(test_rows) + "</ul>" if test_rows else ""}
  {"<h2>Procedures</h2><ul>" + ''.join(procedure_rows) + "</ul>" if procedure_rows else ""}

  <h2>Treatment Appropriateness (STG)</h2>
  {"<p><b>Matched STG conditions:</b> " + escape(', '.join(treatment_audit.get('matched_stg_conditions') or [])) + "</p>" if treatment_audit.get('matched_stg_conditions') else ""}
  {"<table><tr><th>Item</th><th>Type</th><th>Severity</th><th>Reason</th><th>Recommendation</th><th>STG reference</th></tr>" + ''.join(treatment_rows) + "</table>" if treatment_rows else "<p>No treatment appropriateness flags for the supplied diagnosis.</p>"}

  <p class='disclaimer'>Guideline-based indication check using CRC Standard Treatment Guidelines, 7th ed. Not a substitute for clinical judgment.</p>
</body>
</html>
"""


def html_to_pdf(html: str) -> bytes:
    import fitz

    story = fitz.Story(html=html)
    stream = io.BytesIO()
    buffer = fitz.DocumentWriter(stream)
    media = fitz.paper_rect("a4")
    where = media + (36, 36, -36, -36)
    more = True
    while more:
        device = buffer.begin_page(media)
        more, _ = story.place(where)
        story.draw(device)
        buffer.end_page()
    buffer.close()
    return stream.getvalue()


def render_report_pdf(report: dict[str, Any]) -> bytes:
    scheme_id = resolve_scheme_id(report)
    validate_report(report, scheme_id)
    render_html = _SCHEME_RENDERERS[scheme_id]
    return html_to_pdf(render_html(report))


def scheme_filename_prefix(scheme_id: str) -> str:
    return {
        "cghs": "cghs",
        "hbp_pmjay": "pmjay-hbp",
        "aarogya_bhadratha": "aarogya-bhadratha",
    }.get(scheme_id, scheme_id.replace("_", "-"))


register_scheme("aarogya_bhadratha", render_aarogya_report_html)
register_scheme("cghs", render_bill_comparison_html)
register_scheme("hbp_pmjay", render_bill_comparison_html)
register_scheme("prescription", render_prescription_report_html)
