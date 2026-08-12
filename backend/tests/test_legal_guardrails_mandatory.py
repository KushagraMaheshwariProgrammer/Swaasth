"""Mandatory legal-language sanitization on analysis output paths."""

from __future__ import annotations

from app.pharma_rates import nppa_list_display_date
from app.report_pdf import render_bill_comparison_html
from app.restricted_medicines import build_restricted_medicine_flags
from app.services.audit_advocacy import build_advocacy_payload, finalize_audit_flags
from app.services.claim_audit import analyze_claim_items
from app.services.legal_guardrails import assert_payload_safe, sanitize_text, sanitize_value
from app.services.treatment_audit import _normalize_clinical_alignment


def test_finalize_audit_flags_strips_banned_terms() -> None:
    flags = [
        {
            "type": "DUPLICATE_ITEM",
            "severity": "HIGH",
            "item": "CBC fraud charge",
            "reason": "This looks like fraud and negligence.",
            "recommendation": "Sue the hospital for cheating.",
            "guideline_basis": "Possible scam on the bill.",
        }
    ]
    finalized = finalize_audit_flags(flags, chunks=[])
    assert_payload_safe(finalized)
    blob = str(finalized).lower()
    assert "fraud" not in blob
    assert "negligence" not in blob
    assert "sue" not in blob
    assert "scam" not in blob


def test_advocacy_payload_and_claim_audit_are_safe() -> None:
    payload = build_advocacy_payload(
        [
            {
                "type": "MEDICINE_PRICE_DISCREPANCY",
                "severity": "HIGH",
                "item": "Paracetamol",
                "reason": "Possible fraudulent overcharge",
                "recommendation": "Ask the hospital to explain the billed amount.",
            }
        ]
    )
    assert_payload_safe(payload)

    result = analyze_claim_items(
        [
            {"item_name": "CBC", "quantity": 1},
            {"item_name": "CBC", "quantity": 1},
        ]
    )
    assert_payload_safe(result)


def test_sanitize_value_walks_nested_structures() -> None:
    cleaned = sanitize_value({"note": "alleged fraud", "items": ["negligent care"]})
    assert "fraud" not in str(cleaned).lower()
    assert cleaned["note"] == sanitize_text("alleged fraud")


def test_restricted_medicine_payload_is_safe() -> None:
    payload = build_restricted_medicine_flags(
        ocr_text="",
        line_items=[],
        prescription_items=[],
    )
    assert_payload_safe(payload)


def test_pdf_html_sanitizes_client_supplied_report() -> None:
    html = render_bill_comparison_html(
        {
            "report_kind": "bill",
            "patient": {"name": "Test"},
            "hospital": {"name_from_bill": "Test Hospital"},
            "line_items": [],
            "audit_flags": {
                "flags": [
                    {
                        "type": "DUPLICATE_ITEM",
                        "item": "CBC",
                        "reason": "Possible fraud on this line",
                        "recommendation": "Ask the hospital to explain.",
                    }
                ]
            },
        }
    )
    assert "fraud" not in html.lower()
    assert "Generated with AI assistance" in html


def test_documents_consistent_tri_state() -> None:
    assert _normalize_clinical_alignment({"diagnosis_supported": True})[
        "documents_consistent"
    ] == "yes"
    assert _normalize_clinical_alignment({"diagnosis_supported": False})[
        "documents_consistent"
    ] == "unclear"
    assert _normalize_clinical_alignment({})["documents_consistent"] == "not_assessable"
    assert _normalize_clinical_alignment({"documents_consistent": "yes"})[
        "diagnosis_supported"
    ] is True


def test_nppa_list_display_date_from_filename() -> None:
    from pathlib import Path

    assert nppa_list_display_date(Path("NPPA_Price_List_03-06-2025.csv")) == "3 June 2025"
