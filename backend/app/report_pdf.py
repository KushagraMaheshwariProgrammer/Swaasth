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

from app.restricted_medicines import render_restricted_medicine_flags_html

RenderHtmlFn = Callable[[dict[str, Any]], str]

_SCHEME_RENDERERS: dict[str, RenderHtmlFn] = {}

BILL_DISCLAIMER = (
    "This report is based on extracted bill information and reference rates "
    "available in the application. OCR errors, package conditions, exclusions, "
    "and uncertain item matches may require manual verification."
)

_SCHEME_LABELS: dict[str, str] = {
    "general": "General Bill Review",
    "bill": "General Bill Review",
}

_HOSPITAL_TYPE_LABELS: dict[str, str] = {
    "general": "General hospital",
    "speciality": "Speciality hospital",
}


def _render_clinical_evidence_html(report: dict[str, Any]) -> str:
    clinical_context = report.get("clinical_context") or {}
    symptoms = clinical_context.get("symptoms") or []
    test_results = clinical_context.get("test_results") or []
    treatment_audit = report.get("treatment_audit_flags") or {}
    alignment = treatment_audit.get("clinical_alignment") or {}

    if not symptoms and not test_results and not alignment:
        return ""

    symptom_rows = []
    for item in symptoms:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        duration = str(item.get("duration") or "").strip()
        severity = str(item.get("severity") or "").strip()
        details = ", ".join(part for part in (duration, severity) if part)
        symptom_rows.append(
            f"<li>{escape(name)}{f' ({escape(details)})' if details else ''}</li>"
        )

    test_rows = []
    for item in test_results:
        if not isinstance(item, dict):
            continue
        test_name = str(item.get("test_name") or "").strip()
        if not test_name:
            continue
        parts = [test_name]
        if item.get("value"):
            parts.append(str(item.get("value")))
        if item.get("unit"):
            parts.append(str(item.get("unit")))
        if item.get("result"):
            parts.append(str(item.get("result")))
        test_rows.append(f"<li>{escape(' · '.join(parts))}</li>")

    alignment_bits = []
    supported = alignment.get("diagnosis_supported")
    if supported is True:
        alignment_bits.append("<p><b>Diagnosis supported:</b> Yes</p>")
    elif supported is False:
        alignment_bits.append("<p><b>Diagnosis supported:</b> No</p>")
    elif supported is None and alignment:
        alignment_bits.append("<p><b>Diagnosis supported:</b> Insufficient data</p>")

    for label, key in (
        ("Supporting evidence", "supporting_evidence"),
        ("Missing or conflicting evidence", "missing_evidence"),
    ):
        items = alignment.get(key) or []
        if items:
            alignment_bits.append(f"<p><b>{label}:</b></p><ul>")
            alignment_bits.extend(
                f"<li>{escape(str(item))}</li>" for item in items if str(item).strip()
            )
            alignment_bits.append("</ul>")

    return f"""
  <h2>Clinical Evidence</h2>
  {"<p><b>Symptoms</b></p><ul>" + ''.join(symptom_rows) + "</ul>" if symptom_rows else ""}
  {"<p><b>Test results</b></p><ul>" + ''.join(test_rows) + "</ul>" if test_rows else ""}
  {''.join(alignment_bits)}
"""


def register_scheme(scheme_id: str, render_html: RenderHtmlFn) -> None:
    _SCHEME_RENDERERS[scheme_id] = render_html


def resolve_scheme_id(report: dict[str, Any]) -> str:
    report_kind = report.get("report_kind")
    if isinstance(report_kind, str) and report_kind in _SCHEME_RENDERERS:
        return report_kind

    if report.get("line_items"):
        return "general"

    if report.get("treatment_audit_flags"):
        return "prescription"

    raise ValueError("Could not determine report scheme.")


def validate_report(report: dict[str, Any], scheme_id: str) -> None:
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
    return None, "No reference"


def _scheme_title(scheme_id: str) -> str:
    label = _SCHEME_LABELS.get(scheme_id, "General Bill Review")
    return f"{label} Report"


def render_bill_comparison_html(report: dict[str, Any]) -> str:
    settings = report.get("comparison_settings") or {}
    scheme_id = settings.get("comparison_scheme") or "general"
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
        basis = flag.get("guideline_basis") or ""
        treatment_rows.append(
            "<tr>"
            f"<td>{escape(str(flag.get('item', '')))}</td>"
            f"<td>{escape(str(flag.get('type', '')).replace('_', ' '))}</td>"
            f"<td>{escape(str(flag.get('severity', '')))}</td>"
            f"<td>{escape(str(flag.get('reason', '')))}</td>"
            f"<td>{escape(str(flag.get('recommendation', '')))}</td>"
            f"<td>{escape(str(basis))}</td>"
            "</tr>"
        )

    clinical_evidence_html = _render_clinical_evidence_html(report)
    restricted_medicine_html = render_restricted_medicine_flags_html(report)

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
  .cghs-pdf-card {{ background: #f4f7fb; border-left: 3px solid #5d8aa8; border-radius: 6px; padding: 8px 10px; margin: 8px 0; }}
  .cghs-pdf-card h3 {{ margin: 0 0 4px; font-size: 10px; color: #1a5276; }}
  .cghs-pdf-fallback {{ margin: 6px 0; font-size: 9px; color: #566573; }}
  .cghs-pdf-preview {{ margin: 6px 0; padding-left: 16px; }}
  .cghs-pdf-details {{ margin: 8px 0; font-size: 9px; }}
</style></head>
<body>
  <h1>{escape(title)}</h1>

  <h2>Patient &amp; Hospital Information</h2>
  <div class='meta'>
    <p><b>Patient:</b> {escape(str(patient.get('name', '—')))}
      {f" · {escape(str(patient.get('age')))} yrs" if patient.get('age') is not None else ''}
      {f" · {escape(str(patient.get('gender')))}" if patient.get('gender') else ''}
    </p>
    <p><b>Hospital (from bill):</b> {escape(str(hospital.get('name_from_bill', '—')))}
    </p>
    <p><b>Location:</b> {escape(', '.join(location_bits) if location_bits else '—')}</p>
    <p><b>Hospital type:</b> {escape(str(hospital_type))}</p>

    <p><b>Source file:</b> {escape(str(report.get('filename', '—')))}</p>
  </div>

  <h2>Summary</h2>
  <table class='summary'>
    <tr><td><b>Total charged</b></td><td class='num'>{_fmt_currency(total_charged)}</td></tr>
    <tr><td><b>Overcharged by</b></td><td class='num'>{_fmt_currency(total_overcharged)}</td></tr>
    <tr><td><b>Items flagged</b></td><td class='num'>{items_flagged}</td></tr>
  </table>

  {"<h2>Jan Aushadhi — subsidized medicines</h2><ul>" + ''.join(jan_rows) + "</ul><p>" + escape(str(jan_aushadhi.get('advisory', ''))) + "</p>" if jan_rows else ""}

  {restricted_medicine_html}

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

  <h2>Treatment Appropriateness Check</h2>
  {clinical_evidence_html}
  {"<p><b>Matched conditions:</b> " + escape(', '.join(treatment_audit.get('matched_stg_conditions') or [])) + "</p>" if treatment_audit.get('matched_stg_conditions') else ""}
  {"<table><tr><th>Item</th><th>Type</th><th>Severity</th><th>Reason</th><th>Recommendation</th><th>Government guideline basis</th></tr>" + ''.join(treatment_rows) + "</table>" if treatment_rows else "<p>No treatment appropriateness flags for the supplied diagnosis.</p>"}
  <p class='disclaimer'>Recommendations use ICMR, Clinical Establishments Act, and CRC Standard Treatment Guidelines. Not a substitute for clinical judgment.</p>

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
        basis = flag.get("guideline_basis") or ""
        treatment_rows.append(
            "<tr>"
            f"<td>{escape(str(flag.get('item', '')))}</td>"
            f"<td>{escape(str(flag.get('type', '')).replace('_', ' '))}</td>"
            f"<td>{escape(str(flag.get('severity', '')))}</td>"
            f"<td>{escape(str(flag.get('reason', '')))}</td>"
            f"<td>{escape(str(flag.get('recommendation', '')))}</td>"
            f"<td>{escape(str(basis))}</td>"
            "</tr>"
        )

    clinical_evidence_html = _render_clinical_evidence_html(report)
    restricted_medicine_html = render_restricted_medicine_flags_html(report)

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

  {restricted_medicine_html}

  <h2>Treatment Appropriateness Check</h2>
  {clinical_evidence_html}
  {"<p><b>Matched conditions:</b> " + escape(', '.join(treatment_audit.get('matched_stg_conditions') or [])) + "</p>" if treatment_audit.get('matched_stg_conditions') else ""}
  {"<table><tr><th>Item</th><th>Type</th><th>Severity</th><th>Reason</th><th>Recommendation</th><th>Government guideline basis</th></tr>" + ''.join(treatment_rows) + "</table>" if treatment_rows else "<p>No treatment appropriateness flags for the supplied diagnosis.</p>"}

  <p class='disclaimer'>Recommendations use ICMR, Clinical Establishments Act, and CRC Standard Treatment Guidelines. Not a substitute for clinical judgment.</p>
</body>
</html>
"""


def _story_from_html(html: str) -> Any:
    """Build a MuPDF Story with bundled fonts for headless Linux CI runners."""
    import fitz

    try:
        archive = fitz.Archive()
        user_css = fitz.css_for_pymupdf_font("ubuntu", archive=archive)
        return fitz.Story(html=html, user_css=user_css, archive=archive)
    except Exception:
        return fitz.Story(html=html)


def html_to_pdf(html: str) -> bytes:
    import fitz

    story = _story_from_html(html)
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
        "general": "bill",
        "bill": "bill",
    }.get(scheme_id, scheme_id.replace("_", "-"))


register_scheme("general", render_bill_comparison_html)
register_scheme("bill", render_bill_comparison_html)
register_scheme("prescription", render_prescription_report_html)
