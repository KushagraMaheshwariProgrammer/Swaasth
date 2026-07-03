"""Unified report PDF rendering.

Report kinds register an HTML renderer via ``register_report_renderer``; the
client sends the full report object (from live results or bill history) to
``/api/reports/render-pdf``.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from html import escape
from typing import Any

from app.restricted_medicines import render_restricted_medicine_flags_html
from app.services.audit_advocacy import ADVOCACY_SCOPE_CHECKED, ADVOCACY_SCOPE_NOT_CHECKED, flag_display_label

RenderHtmlFn = Callable[[dict[str, Any]], str]

_REPORT_RENDERERS: dict[str, RenderHtmlFn] = {}

BILL_DISCLAIMER = (
    "This report is based on extracted bill information and reference rates "
    "available in the application. OCR errors, package conditions, exclusions, "
    "and uncertain item matches may require manual verification."
)

_REPORT_TITLES: dict[str, str] = {
    "general": "Bill Review Report",
    "bill": "Bill Review Report",
    "combined": "Bill and Prescription Review Report",
    "prescription": "Prescription Treatment Appropriateness Report",
    "dispute_pack": "Dispute Pack — Factual Summary",
    "medical_history": "Medical History Summary",
}

_HOSPITAL_TYPE_LABELS: dict[str, str] = {
    "general": "General hospital",
    "speciality": "Speciality hospital",
}


def _render_patient_questions_html(report: dict[str, Any]) -> str:
    questions = report.get("patient_questions") or []
    if not questions:
        treatment_questions = (report.get("treatment_audit_flags") or {}).get("patient_questions") or []
        audit_questions = (report.get("audit_flags") or {}).get("patient_questions") or []
        questions = treatment_questions or audit_questions
    if not questions:
        return ""

    rows = []
    for index, item in enumerate(questions, start=1):
        confidence = escape(str(item.get("confidence") or "LOW"))
        question = escape(str(item.get("question") or ""))
        basis = escape(str(item.get("guideline_basis") or ""))
        rows.append(
            f"<li><b>{index}. {question}</b> "
            f"<span>({confidence} confidence)</span>"
            f"{f'<br/><i>{basis}</i>' if basis else ''}</li>"
        )
    return f"<h2>Questions to ask before you pay or discharge</h2><ol>{''.join(rows)}</ol>"


def _render_advocacy_scope_html(report: dict[str, Any]) -> str:
    scope = report.get("advocacy_scope") or {}
    checked = scope.get("checked") or list(ADVOCACY_SCOPE_CHECKED)
    not_checked = scope.get("not_checked") or list(ADVOCACY_SCOPE_NOT_CHECKED)
    checked_html = "".join(f"<li>{escape(str(item))}</li>" for item in checked)
    not_checked_html = "".join(f"<li>{escape(str(item))}</li>" for item in not_checked)
    return f"""
  <h2>What we checked</h2>
  <p><b>Checked</b></p><ul>{checked_html}</ul>
  <p><b>Not checked</b></p><ul>{not_checked_html}</ul>
  <p class='disclaimer'>Swaasth does not make final medical, legal, or regulatory findings against any hospital or doctor.</p>
"""


def _export_options(report: dict[str, Any]) -> dict[str, bool]:
    opts = report.get("export_options") or {}
    return {
        "include_stg_excerpts": bool(opts.get("include_stg_excerpts", True)),
        "include_legal_pathways": bool(opts.get("include_legal_pathways", True)),
    }


def _collect_all_flags(report: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for source in [
        (report.get("audit_flags") or {}).get("flags"),
        (report.get("treatment_audit_flags") or {}).get("flags"),
    ]:
        for flag in source or []:
            if isinstance(flag, dict):
                flags.append(flag)
    return flags


def _render_guideline_sources_html(report: dict[str, Any]) -> str:
    treatment_audit = report.get("treatment_audit_flags") or {}
    sources = treatment_audit.get("guideline_sources") or []
    if not sources:
        return ""
    used_fallback = treatment_audit.get("used_fallback")
    note = " (CRC reference book used as fallback)" if used_fallback else ""
    items = "".join(f"<li>{escape(str(source))}</li>" for source in sources)
    return f"""
  <h2>Guideline sources used in this review</h2>
  <ul>{items}</ul>
  <p class='disclaimer'>
    Primary sources are ICMR guidelines and MoHFW Clinical Establishments Act STGs
    where retrieved. CRC Standard Treatment Guidelines may be used when primary
    excerpts are insufficient.{escape(note)}
  </p>
"""


def _render_stg_excerpts_html(report: dict[str, Any]) -> str:
    if not _export_options(report)["include_stg_excerpts"]:
        return ""

    blocks: list[str] = []
    for flag in _collect_all_flags(report):
        citation = flag.get("stg_citation")
        if not isinstance(citation, dict) or not citation.get("full_text"):
            continue
        source = citation.get("source") if isinstance(citation.get("source"), dict) else {}
        reference = citation.get("reference") if isinstance(citation.get("reference"), dict) else {}
        label = flag.get("display_label") or flag_display_label(str(flag.get("type") or ""))
        item = str(flag.get("item") or "").strip()
        title = f"{label}: {item}" if item else str(label)
        ref_bits = [
            str(reference.get("condition") or ""),
            str(reference.get("section") or ""),
            str(reference.get("page_label") or ""),
        ]
        ref_line = " · ".join(bit for bit in ref_bits if bit)
        examples = source.get("legal_use_examples") or []
        examples_html = "".join(f"<li>{escape(str(ex))}</li>" for ex in examples)
        blocks.append(
            f"<div class='stg-block'>"
            f"<h3>{escape(title)}</h3>"
            f"<p><b>Source:</b> {escape(str(source.get('display_name') or source.get('corpus_label') or 'Guidelines'))}"
            f" — {escape(str(source.get('authority') or ''))}</p>"
            f"{f'<p><b>Reference:</b> {escape(ref_line)}</p>' if ref_line else ''}"
            f"<p><i>{escape(str(source.get('credibility_note') or ''))}</i></p>"
            f"<pre class='stg-excerpt'>{escape(str(citation.get('full_text') or ''))}</pre>"
            f"{'<p><b>How this source is used in disputes (examples):</b></p><ul>' + examples_html + '</ul>' if examples_html else ''}"
            f"</div>"
        )
    if not blocks:
        return ""
    return (
        "<h2>Full guideline excerpts (verified citations)</h2>"
        + "".join(blocks)
        + "<p class='disclaimer'>Excerpts are reproduced for patient review. "
        "Verify against the original document before filing any complaint.</p>"
    )


def _render_legal_pathways_html(report: dict[str, Any]) -> str:
    if not _export_options(report)["include_legal_pathways"]:
        return ""

    blocks: list[str] = []
    for flag in _collect_all_flags(report):
        pathway = flag.get("legal_pathway")
        if not isinstance(pathway, dict):
            continue
        label = flag.get("display_label") or flag_display_label(str(flag.get("type") or ""))
        item = str(flag.get("item") or "").strip()
        title = f"{label}: {item}" if item else str(label)
        blocks.append(
            f"<div class='legal-block'>"
            f"<h3>{escape(title)}</h3>"
            f"<p><b>Broader legal concept (educational):</b> "
            f"{escape(str(pathway.get('broader_concept') or ''))}</p>"
            f"<p><b>Possible complaint angle:</b> "
            f"{escape(str(pathway.get('specific_angle') or ''))}</p>"
            f"<p><b>What is usually required to pursue this:</b> "
            f"{escape(str(pathway.get('what_must_be_proven') or ''))}</p>"
            f"<p><i>{escape(str(pathway.get('not_an_accusation') or ''))}</i></p>"
            f"</div>"
        )
    if not blocks:
        return ""
    disclaimer = (
        "Educational only — not legal advice. Swaasth does not accuse any hospital "
        "or doctor. Consult a qualified advocate before alleging medical negligence, "
        "deficiency in service, or unfair trade practice."
    )
    return (
        "<h2>Possible legal pathways (educational — not accusations)</h2>"
        + "".join(blocks)
        + f"<p class='disclaimer'>{escape(disclaimer)}</p>"
    )


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


def register_report_renderer(report_kind: str, render_html: RenderHtmlFn) -> None:
    _REPORT_RENDERERS[report_kind] = render_html


def resolve_report_kind(report: dict[str, Any]) -> str:
    report_kind = report.get("report_kind")
    if isinstance(report_kind, str) and report_kind in _REPORT_RENDERERS:
        return report_kind

    if report.get("line_items"):
        return "general"

    if report.get("treatment_audit_flags"):
        return "prescription"

    raise ValueError("Could not determine report kind.")


def validate_report(report: dict[str, Any], report_kind: str) -> None:
    if report_kind == "dispute_pack":
        if not report.get("action_plan"):
            raise ValueError("Invalid dispute pack report payload.")
        return

    if report_kind == "medical_history":
        patient = report.get("patient") or {}
        if not str(patient.get("name") or "").strip():
            raise ValueError("Invalid medical history report payload.")
        profile = report.get("profile") or {}
        timeline = report.get("timeline") or []
        has_profile = any(
            profile.get(key)
            for key in ("conditions", "surgeries", "allergies")
        )
        if not timeline and not has_profile:
            raise ValueError("Medical history has no entries to export.")
        return

    if report_kind == "prescription":
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


def _report_title(report_kind: str) -> str:
    return _REPORT_TITLES.get(report_kind, "Bill Review Report")


def render_bill_comparison_html(report: dict[str, Any]) -> str:
    settings = report.get("comparison_settings") or {}
    report_kind = report.get("report_kind") or "general"
    title = _report_title(report_kind)

    patient = report.get("patient") or {}
    hospital = report.get("hospital") or {}
    hospital_profile = report.get("hospital_profile") or {}
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
    profile_city = str(hospital_profile.get("city") or "").strip()
    profile_state = str(hospital_profile.get("state") or "").strip()
    if profile_city and profile_state:
        location_bits.append(f"{profile_city}, {profile_state}")
    elif settings.get("city") and settings.get("state_name"):
        location_bits.append(f"{settings['city']}, {settings['state_name']}")
    hospital_name = (
        str(hospital_profile.get("name") or "").strip()
        or str(hospital.get("name_from_bill") or "").strip()
        or "—"
    )
    hospital_type = _HOSPITAL_TYPE_LABELS.get(
        settings.get("hospital_type", ""), settings.get("hospital_type", "—")
    )

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
        label = flag.get("display_label") or flag_display_label(str(flag.get("type") or ""))
        audit_rows.append(
            "<tr>"
            f"<td>{escape(str(flag.get('item', '')))}</td>"
            f"<td>{escape(str(label))}</td>"
            f"<td>{escape(str(flag.get('confidence', '')))}</td>"
            f"<td>{escape(str(flag.get('reason', '')))}</td>"
            f"<td>{escape(str(flag.get('recommendation', '')))}</td>"
            "</tr>"
        )

    treatment_audit = report.get("treatment_audit_flags") or {}
    treatment_flags = treatment_audit.get("flags") or []
    treatment_rows = []
    for flag in treatment_flags:
        basis = flag.get("guideline_basis") or ""
        label = flag.get("display_label") or flag_display_label(str(flag.get("type") or ""))
        treatment_rows.append(
            "<tr>"
            f"<td>{escape(str(flag.get('item', '')))}</td>"
            f"<td>{escape(str(label))}</td>"
            f"<td>{escape(str(flag.get('confidence', '')))}</td>"
            f"<td>{escape(str(flag.get('reason', '')))}</td>"
            f"<td>{escape(str(flag.get('recommendation', '')))}</td>"
            f"<td>{escape(str(basis))}</td>"
            "</tr>"
        )

    patient_questions_html = _render_patient_questions_html(report)
    advocacy_scope_html = _render_advocacy_scope_html(report)
    clinical_evidence_html = _render_clinical_evidence_html(report)
    restricted_medicine_html = render_restricted_medicine_flags_html(report)
    guideline_sources_html = _render_guideline_sources_html(report)
    stg_excerpts_html = _render_stg_excerpts_html(report)
    legal_pathways_html = _render_legal_pathways_html(report)

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
  .stg-excerpt {{ white-space: pre-wrap; font-size: 9px; background: #f8f9fa; padding: 8px; border: 1px solid #d5dbdb; }}
  .stg-block, .legal-block {{ margin: 10px 0; padding: 8px; border: 1px solid #e5e8e8; border-radius: 4px; }}
  ul {{ margin: 4px 0; padding-left: 16px; }}
  ol {{ margin: 4px 0; padding-left: 16px; }}
</style></head>
<body>
  <h1>{escape(title)}</h1>

  <h2>Patient &amp; Hospital Information</h2>
  <div class='meta'>
    <p><b>Patient:</b> {escape(str(patient.get('name', '—')))}
      {f" · {escape(str(patient.get('age')))} yrs" if patient.get('age') is not None else ''}
      {f" · {escape(str(patient.get('gender')))}" if patient.get('gender') else ''}
    </p>
    <p><b>Hospital:</b> {escape(hospital_name)}
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

  {patient_questions_html}

  {advocacy_scope_html}

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

  <h2>Items worth clarifying (billing)</h2>
  {"<table><tr><th>Item</th><th>Finding</th><th>Confidence</th><th>Reason</th><th>Suggested question</th></tr>" + ''.join(audit_rows) + "</table>" if audit_rows else "<p>No billing patterns flagged for clarification.</p>"}

  <h2>Treatment appropriateness (details)</h2>
  {clinical_evidence_html}
  {"<p><b>Matched conditions:</b> " + escape(', '.join(treatment_audit.get('matched_stg_conditions') or [])) + "</p>" if treatment_audit.get('matched_stg_conditions') else ""}
  {"<table><tr><th>Item</th><th>Finding</th><th>Confidence</th><th>Reason</th><th>Suggested question</th><th>Government guideline basis</th></tr>" + ''.join(treatment_rows) + "</table>" if treatment_rows else "<p>No treatment items flagged for clarification based on retrieved guidelines.</p>"}
  {guideline_sources_html}
  {legal_pathways_html}
  {stg_excerpts_html}
  <p class='disclaimer'>Recommendations use ICMR and CRC Standard Treatment Guidelines where available. Not a substitute for clinical judgment.</p>

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
        label = flag.get("display_label") or flag_display_label(str(flag.get("type") or ""))
        treatment_rows.append(
            "<tr>"
            f"<td>{escape(str(flag.get('item', '')))}</td>"
            f"<td>{escape(str(label))}</td>"
            f"<td>{escape(str(flag.get('confidence', '')))}</td>"
            f"<td>{escape(str(flag.get('reason', '')))}</td>"
            f"<td>{escape(str(flag.get('recommendation', '')))}</td>"
            f"<td>{escape(str(basis))}</td>"
            "</tr>"
        )

    patient_questions_html = _render_patient_questions_html(report)
    advocacy_scope_html = _render_advocacy_scope_html(report)
    clinical_evidence_html = _render_clinical_evidence_html(report)
    restricted_medicine_html = render_restricted_medicine_flags_html(report)
    guideline_sources_html = _render_guideline_sources_html(report)
    stg_excerpts_html = _render_stg_excerpts_html(report)
    legal_pathways_html = _render_legal_pathways_html(report)

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
  .stg-excerpt {{ white-space: pre-wrap; font-size: 9px; background: #f8f9fa; padding: 8px; border: 1px solid #d5dbdb; }}
  .stg-block, .legal-block {{ margin: 10px 0; padding: 8px; border: 1px solid #e5e8e8; border-radius: 4px; }}
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

  {patient_questions_html}

  {advocacy_scope_html}

  {restricted_medicine_html}

  <h2>Treatment appropriateness (details)</h2>
  {clinical_evidence_html}
  {"<p><b>Matched conditions:</b> " + escape(', '.join(treatment_audit.get('matched_stg_conditions') or [])) + "</p>" if treatment_audit.get('matched_stg_conditions') else ""}
  {"<table><tr><th>Item</th><th>Finding</th><th>Confidence</th><th>Reason</th><th>Suggested question</th><th>Government guideline basis</th></tr>" + ''.join(treatment_rows) + "</table>" if treatment_rows else "<p>No treatment items flagged for clarification based on retrieved guidelines.</p>"}
  {guideline_sources_html}
  {legal_pathways_html}
  {stg_excerpts_html}

  <p class='disclaimer'>Recommendations use ICMR and CRC Standard Treatment Guidelines where available. Not a substitute for clinical judgment.</p>
</body>
</html>
"""


def render_dispute_pack_html(report: dict[str, Any]) -> str:
    """Render a dispute / evidence pack PDF from action_plan data."""
    action_plan = report.get("action_plan") or {}
    patient = report.get("patient") or {}
    hospital = report.get("hospital") or {}
    discharge = action_plan.get("discharge_guidance") or {}
    recoverable = action_plan.get("recoverable_estimate") or {}

    evidence_rows = []
    for item in action_plan.get("evidence_pack_items") or []:
        ref = item.get("reference_rate") or {}
        stg = item.get("stg_excerpt") or {}
        evidence_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('display_label') or item.get('item') or ''))}</td>"
            f"<td>{escape(str(item.get('tier') or ''))}</td>"
            f"<td>{escape(_fmt_currency(ref.get('value')) if ref.get('value') is not None else '—')}</td>"
            f"<td>{escape(str(stg.get('condition') or '—'))}</td>"
            f"<td>{escape('; '.join(item.get('questions') or []))}</td>"
            "</tr>"
        )

    ladder_html = []
    for step in action_plan.get("escalation_ladder") or []:
        attachments = step.get("what_to_attach") or []
        attach_html = "".join(f"<li>{escape(str(a))}</li>" for a in attachments)
        ladder_html.append(
            f"<h3>{escape(str(step.get('title') or ''))}</h3>"
            f"<p><b>When:</b> {escape(str(step.get('when') or ''))}</p>"
            f"<p><b>Typical timeline:</b> {escape(str(step.get('typical_timeline') or ''))}</p>"
            f"<p><b>Attach:</b></p><ul>{attach_html}</ul>"
            f"<p><i>{escape(str(step.get('disclaimer') or ''))}</i></p>"
        )

    template_blocks = []
    for template in action_plan.get("complaint_templates") or []:
        template_blocks.append(
            f"<h3>{escape(str(template.get('audience') or ''))}</h3>"
            f"<p><b>Subject:</b> {escape(str(template.get('subject') or ''))}</p>"
            f"<pre style='white-space:pre-wrap;font-size:9px;'>{escape(str(template.get('body') or ''))}</pre>"
        )

    reasons = discharge.get("reasons") or []
    reasons_html = "".join(f"<li>{escape(str(r))}</li>" for r in reasons)

    return f"""
<html>
<head><style>
  body {{ font-family: Helvetica, Arial, sans-serif; color: #2c3e50; font-size: 10px; }}
  h1 {{ font-size: 16px; color: #1a5276; }}
  h2 {{ font-size: 12px; color: #1a5276; border-bottom: 1px solid #aed6f1; margin-top: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  th, td {{ border: 1px solid #d5dbdb; padding: 4px 5px; text-align: left; vertical-align: top; }}
  th {{ background: #eaf2f8; font-size: 9px; }}
  .disclaimer {{ margin-top: 14px; font-size: 8.5px; color: #7f8c8d; font-style: italic; }}
  ul {{ margin: 4px 0; padding-left: 16px; }}
</style></head>
<body>
  <h1>Dispute Pack — Factual Summary</h1>
  <p><b>Patient:</b> {escape(str(patient.get('name', '—')))}</p>
  <p><b>Hospital:</b> {escape(str(hospital.get('name_from_bill', '—')))}</p>

  <h2>Discharge payment guidance</h2>
  <p><b>Status:</b> {escape(str(discharge.get('status', '—')))}</p>
  <ul>{reasons_html}</ul>
  <p><i>{escape(str(discharge.get('emergency_note') or ''))}</i></p>

  <h2>Recoverable amount estimate</h2>
  <p><b>Overpriced vs NPPA:</b> {_fmt_currency(recoverable.get('overpriced_total'))}</p>
  <p><b>Jan Aushadhi savings potential:</b> {_fmt_currency(recoverable.get('jan_aushadhi_savings'))}</p>
  <p><b>Total estimate:</b> {_fmt_currency(recoverable.get('total'))}</p>
  <p class='disclaimer'>{escape(str(recoverable.get('disclaimer') or ''))}</p>

  <h2>Evidence pack items</h2>
  {"<table><tr><th>Item</th><th>Tier</th><th>Reference</th><th>Guideline</th><th>Questions</th></tr>" + ''.join(evidence_rows) + "</table>" if evidence_rows else "<p>No Tier A/B evidence items.</p>"}

  <h2>Escalation ladder</h2>
  {''.join(ladder_html)}

  <h2>Complaint draft templates</h2>
  {''.join(template_blocks) if template_blocks else "<p>No templates generated.</p>"}

  <p class='disclaimer'>{escape(str(action_plan.get('disclaimer') or ''))}</p>
  <p class='disclaimer'>Swaasth does not make final medical, legal, or regulatory findings.</p>
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
    report_kind = resolve_report_kind(report)
    validate_report(report, report_kind)
    render_html = _REPORT_RENDERERS[report_kind]
    return html_to_pdf(render_html(report))


def render_medical_history_html(report: dict[str, Any]) -> str:
    patient = report.get("patient") or {}
    profile = report.get("profile") or {}
    timeline = report.get("timeline") or []
    include_swaasth = bool(report.get("include_swaasth_reports", True))
    generated_at = escape(str(report.get("generated_at") or "")[:10])

    def _list_rows(items: list[Any], label_key: str = "name") -> str:
        if not items:
            return "<p>None recorded.</p>"
        rows = []
        for item in items:
            if isinstance(item, dict):
                name = escape(str(item.get(label_key) or ""))
                extra_bits = []
                if item.get("year"):
                    extra_bits.append(str(item.get("year")))
                if item.get("status"):
                    extra_bits.append(str(item.get("status")))
                if item.get("reaction"):
                    extra_bits.append(str(item.get("reaction")))
                suffix = f" ({', '.join(extra_bits)})" if extra_bits else ""
                rows.append(f"<li>{name}{escape(suffix)}</li>")
            else:
                rows.append(f"<li>{escape(str(item))}</li>")
        return f"<ul>{''.join(rows)}</ul>"

    timeline_blocks: list[str] = []
    for entry in timeline:
        date_label = escape(str(entry.get("date") or "Date unknown"))
        kind = str(entry.get("kind") or "")
        hospital_name = escape(str(entry.get("hospital") or ""))
        hospital_city = escape(str(entry.get("hospital_city") or ""))
        hospital_state = escape(str(entry.get("hospital_state") or ""))
        hospital_bits = [bit for bit in [hospital_name, hospital_city, hospital_state] if bit]
        hospital_line = (
            f"<p><b>Hospital:</b> {', '.join(hospital_bits)}</p>" if hospital_bits else ""
        )
        if kind == "swaasth_report":
            title = escape(str(entry.get("title") or "Swaasth report"))
            report_label = escape(str(entry.get("report_kind_label") or "Report"))
            diagnosis = escape(str(entry.get("diagnosis") or ""))
            medicines = entry.get("medicines") or []
            symptoms = entry.get("symptoms") or []
            test_results = entry.get("test_results") or []
            med_list = ", ".join(escape(str(name)) for name in medicines if name)
            symptom_list = ", ".join(escape(str(name)) for name in symptoms if name)
            timeline_blocks.append(
                f"<div class='history-entry'>"
                f"<h3>{date_label} — Swaasth {report_label}</h3>"
                f"<p><b>{title}</b></p>"
                f"{hospital_line}"
                f"{f'<p><b>Diagnosis:</b> {diagnosis}</p>' if diagnosis else ''}"
                f"{f'<p><b>Medicines:</b> {med_list}</p>' if med_list else ''}"
                f"{f'<p><b>Symptoms:</b> {symptom_list}</p>' if symptom_list else ''}"
                f"{f'<p><b>Test results:</b> {len(test_results)} recorded</p>' if test_results else ''}"
                f"</div>"
            )
        else:
            title = escape(str(entry.get("title") or "Document"))
            doc_type = escape(str(entry.get("document_type_label") or entry.get("document_type") or "Document"))
            diagnosis = escape(str(entry.get("diagnosis") or ""))
            timeline_blocks.append(
                f"<div class='history-entry'>"
                f"<h3>{date_label} — {doc_type}</h3>"
                f"<p><b>{title}</b></p>"
                f"{hospital_line}"
                f"{f'<p><b>Diagnosis:</b> {diagnosis}</p>' if diagnosis else ''}"
                f"</div>"
            )

    scope_note = (
        "Includes Swaasth analysis reports and uploaded historical documents."
        if include_swaasth
        else "Includes profile history and uploaded historical documents only (Swaasth reports excluded)."
    )

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>Medical History Summary</title></head>
<body>
  <h1>Medical History Summary</h1>
  <p><b>Patient:</b> {escape(str(patient.get('name') or 'Patient'))}</p>
  <p><b>Age:</b> {escape(str(patient.get('age_label') or patient.get('age') or '—'))}</p>
  <p><b>Gender:</b> {escape(str(patient.get('gender_label') or patient.get('gender') or '—'))}</p>
  <p><b>Generated:</b> {generated_at}</p>
  <p class='disclaimer'>{escape(scope_note)}</p>

  <h2>Profile medical history</h2>
  <p><b>Conditions</b></p>
  {_list_rows(profile.get('conditions') or [])}
  <p><b>Surgeries</b></p>
  {_list_rows(profile.get('surgeries') or [])}
  <p><b>Allergies</b></p>
  {_list_rows(profile.get('allergies') or [])}

  <h2>Chronological timeline</h2>
  {''.join(timeline_blocks) if timeline_blocks else '<p>No dated entries yet.</p>'}

  <p class='disclaimer'>
    This summary is compiled from information you provided and documents analyzed in Swaasth.
    It is not a substitute for official medical records. Verify details with your healthcare providers.
  </p>
</body>
</html>
"""


def report_filename_prefix(report_kind: str) -> str:
    return {
        "general": "bill",
        "bill": "bill",
        "combined": "bill-prescription",
        "prescription": "prescription",
        "dispute_pack": "dispute",
        "medical_history": "medical-history",
    }.get(report_kind, report_kind.replace("_", "-"))


register_report_renderer("general", render_bill_comparison_html)
register_report_renderer("bill", render_bill_comparison_html)
register_report_renderer("combined", render_bill_comparison_html)
register_report_renderer("prescription", render_prescription_report_html)
register_report_renderer("dispute_pack", render_dispute_pack_html)
register_report_renderer("medical_history", render_medical_history_html)
