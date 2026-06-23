"""Aarogya Bhadratha report persistence and PDF generation.

Reports are stored in-memory and mirrored to disk (JSON) so they survive a
restart and can be retrieved / rendered as a PDF by report id. Patient bill
history itself is owned by the client (Firestore + local store, like the rest
of the app); this server-side copy backs the report retrieval / PDF endpoints.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from app.restricted_medicines import render_restricted_medicine_flags_html

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_REPORT_DIR = _BACKEND_ROOT / "data" / "aarogya_bhadratha_cache" / "reports"

REPORT_TITLE = "Aarogya Bhadratha Bill Comparison Report"
DISCLAIMER = (
    "This report is based on OCR-extracted bill information and the Aarogya "
    "Bhadratha data available in the application. OCR errors, package "
    "conditions, exclusions and uncertain item matches may require manual "
    "verification. Unmatched items are not treated as overcharged."
)

_lock = threading.Lock()
_reports: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_export_text(value: Any) -> str:
    """Neutralize CSV/spreadsheet formula injection for any exported text."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def build_report(
    *,
    patient: dict[str, Any],
    hospital_verification: dict[str, Any],
    comparison: dict[str, Any],
    bill: dict[str, Any],
    ocr: dict[str, Any],
    jan_aushadhi: dict[str, Any] | None = None,
    restricted_medicine_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_id = uuid.uuid4().hex
    now = _now_iso()
    return {
        "report_id": report_id,
        "report_kind": "aarogya_bhadratha",
        "title": REPORT_TITLE,
        "scheme": "Aarogya Bhadratha Scheme",
        "generated_at": now,
        "analysis_date": now,
        "patient": patient,
        "hospital": hospital_verification,
        "bill": bill,
        "ocr": ocr,
        "comparison": comparison,
        "jan_aushadhi": jan_aushadhi,
        "restricted_medicine_flags": restricted_medicine_flags,
        "disclaimer": DISCLAIMER,
    }


def save_report(report: dict[str, Any]) -> str:
    report_id = report["report_id"]
    with _lock:
        _reports[report_id] = report
    try:
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (_REPORT_DIR / f"{report_id}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        # Persistence to disk is best-effort; in-memory copy still serves it.
        pass
    return report_id


def get_report(report_id: str) -> dict[str, Any] | None:
    with _lock:
        report = _reports.get(report_id)
    if report is not None:
        return report
    path = _REPORT_DIR / f"{report_id}.json"
    if path.exists():
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            with _lock:
                _reports[report_id] = report
            return report
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _fmt_currency(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _status_color(status: str) -> str:
    return {
        "Above Approved Rate": "#c0392b",
        "Within Approved Rate": "#1e8449",
        "Below Approved Rate": "#1e8449",
        "Manual Verification Required": "#b9770e",
        "Rate Not Found": "#7f8c8d",
    }.get(status, "#34495e")


def render_report_html(report: dict[str, Any]) -> str:
    patient = report.get("patient", {})
    hosp = report.get("hospital", {})
    matched = hosp.get("matched_hospital") or {}
    bill = report.get("bill", {})
    comparison = report.get("comparison", {})
    summary = comparison.get("summary", {})
    items = comparison.get("items", [])

    rows_html = []
    for item in items:
        color = _status_color(item.get("status", ""))
        conf = item.get("match_confidence")
        conf_txt = f"{round(float(conf) * 100)}%" if conf else "—"
        is_medicine = item.get("comparison_source") == "pharma" or item.get("category") == "medicine"
        matched_label = item.get("matched_name") or "—"
        if is_medicine and matched_label != "—":
            matched_label = f"{matched_label} (NPPA ceiling)"
        rows_html.append(
            "<tr>"
            f"<td>{escape(str(item.get('item_name', '')))}</td>"
            f"<td class='num'>{escape(str(item.get('quantity', '')))}</td>"
            f"<td class='num'>{_fmt_currency(item.get('total_price'))}</td>"
            f"<td>{escape(str(matched_label))}"
            f"{(' (' + escape(str(item.get('matched_code'))) + ')') if item.get('matched_code') else ''}</td>"
            f"<td class='num'>{_fmt_currency(item.get('approved_amount') if not is_medicine else item.get('pharma_rate'))}</td>"
            f"<td class='num'>{_fmt_currency(item.get('difference'))}</td>"
            f"<td class='num'>{_fmt_currency(item.get('excess_amount'))}</td>"
            f"<td style='color:{color}'>{escape(str(item.get('status', '')))}</td>"
            f"<td class='num'>{conf_txt}</td>"
            "</tr>"
        )

    jan_aushadhi = report.get("jan_aushadhi") or {}
    jan_matches = jan_aushadhi.get("matches") or []
    jan_rows = []
    for match in jan_matches:
        jan_rows.append(
            "<li>"
            f"<b>{escape(str(match.get('bill_item_name', '')))}</b>"
            f" — {escape(str(match.get('generic_name') or ''))}"
            f" · Jan Aushadhi MRP {_fmt_currency(match.get('mrp'))}"
            f"{(' per ' + escape(str(match.get('unit_size')))) if match.get('unit_size') else ''}"
            "</li>"
        )

    eligible = "Yes" if patient.get("aarogya_bhadratha_eligible") else "No"
    spec = ", ".join(matched.get("specialities", [])[:8]) or matched.get(
        "specialities_text", "—"
    )

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
  .badge {{ color: #1e8449; font-weight: bold; }}
</style></head>
<body>
  <h1>{escape(REPORT_TITLE)}</h1>
  <p class='badge'>This hospital is empanelled under the Aarogya Bhadratha Scheme.</p>

  <h2>Patient &amp; Hospital Information</h2>
  <div class='meta'>
    <p><b>Patient:</b> {escape(str(patient.get('name', '—')))}</p>
    <p><b>State:</b> {escape(str(patient.get('state', '—')))} &nbsp; <b>Aarogya Bhadratha eligible:</b> {eligible}</p>
    <p><b>Hospital (OCR):</b> {escape(str(hosp.get('ocr_hospital_name', '—')))}</p>
    <p><b>Matched empanelled hospital:</b> {escape(str(matched.get('name', '—')))}</p>
    <p><b>District:</b> {escape(str(matched.get('district', '—')))}</p>
    <p><b>Address:</b> {escape(str(matched.get('address', '—')))}</p>
    <p><b>Speciality:</b> {escape(str(spec))}</p>
    <p><b>Hospital code:</b> {escape(str(matched.get('hospital_code') or '—'))} &nbsp; <b>Ref no:</b> {escape(str(matched.get('ref_no', '—')))}</p>
    <p><b>Bill date:</b> {escape(str(bill.get('bill_date') or '—'))} &nbsp; <b>Original bill total:</b> {_fmt_currency(bill.get('original_total'))}</p>
    <p><b>Empanelment status:</b> Empanelled &nbsp; <b>Match confidence:</b> {round(float(hosp.get('match_confidence', 0)) * 100)}% ({escape(str(hosp.get('match_method', '—')))})</p>
  </div>

  <h2>Item-level Comparison</h2>
  <table>
    <tr>
      <th>Bill item</th><th class='num'>Qty</th><th class='num'>Charged</th>
      <th>Matched scheme procedure</th><th class='num'>Approved rate</th>
      <th class='num'>Difference</th><th class='num'>Excess</th><th>Status</th><th class='num'>Conf.</th>
    </tr>
    {''.join(rows_html)}
  </table>

  <h2>Summary</h2>
  <table class='summary'>
    <tr><td><b>Total hospital-billed amount</b></td><td class='num'>{_fmt_currency(summary.get('total_charged'))}</td></tr>
    <tr><td><b>Total approved amount (matched items)</b></td><td class='num'>{_fmt_currency(summary.get('total_approved_matched'))}</td></tr>
    <tr><td><b>Total possible excess amount</b></td><td class='num'>{_fmt_currency(summary.get('total_possible_excess'))}</td></tr>
    <tr><td><b>Total below approved rates</b></td><td class='num'>{_fmt_currency(summary.get('total_below_approved'))}</td></tr>
    <tr><td><b>Percentage difference</b></td><td class='num'>{summary.get('percentage_difference') if summary.get('percentage_difference') is not None else '—'}%</td></tr>
    <tr><td><b>Matched items</b></td><td class='num'>{summary.get('matched_items', 0)}</td></tr>
    <tr><td><b>Unmatched items</b></td><td class='num'>{summary.get('unmatched_items', 0)}</td></tr>
    <tr><td><b>Items requiring manual verification</b></td><td class='num'>{summary.get('manual_verification_items', 0)}</td></tr>
  </table>
  <p style='margin-top:6px;font-size:9px;'>Medicines are compared against NPPA ceiling prices (with brand-to-generic resolution when needed). Procedures and other services use Aarogya Bhadratha annexure rates.</p>
  {"<h2>Jan Aushadhi — subsidized medicines</h2><ul>" + ''.join(jan_rows) + "</ul><p>" + escape(str(jan_aushadhi.get('advisory', ''))) + "</p>" if jan_rows else ""}

  {render_restricted_medicine_flags_html(report)}

  <p class='disclaimer'>{escape(DISCLAIMER)}</p>
</body>
</html>
"""


def render_report_pdf(report: dict[str, Any]) -> bytes:
    """Render the report to a PDF via the shared scheme registry."""
    from app.report_pdf import render_report_pdf as render_scheme_pdf

    return render_scheme_pdf(report)
