"""Tests for the unified report PDF endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _sample_bill_report() -> dict:
    return {
        "filename": "test-bill.pdf",
        "comparison_settings": {
            "city": "Mumbai",
            "state_name": "Maharashtra",
            "hospital_type": "general",
        },
        "patient": {"name": "Test Patient", "age": 45, "gender": "Male"},
        "hospital": {"name_from_bill": "City Hospital"},
        "line_items": [
            {
                "item_name": "Paracetamol 500mg",
                "quantity": 10,
                "total_price": 50,
                "comparison_source": "pharma",
                "pharma_rate": 40,
                "price_difference": 10,
                "flag": "overpriced",
                "matched_reference_item": "Paracetamol",
                "category": "medicine",
            }
        ],
        "audit_flags": {"flags": [], "flags_count": 0, "risk_level": "LOW"},
    }


def test_unified_render_pdf_general_bill() -> None:
    res = client.post("/api/reports/render-pdf", json=_sample_bill_report())
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"
    assert "bill-Test-Patient.pdf" in res.headers.get("content-disposition", "")


def test_unified_render_pdf_rejects_empty_report() -> None:
    res = client.post("/api/reports/render-pdf", json={})
    assert res.status_code == 400


def test_unified_render_pdf_medical_history() -> None:
    payload = {
        "report_kind": "medical_history",
        "patient": {
            "name": "Test Patient",
            "age_label": "45 years",
            "gender_label": "Male",
        },
        "profile": {
            "conditions": [{"name": "Hypertension", "year": 2020}],
            "surgeries": [],
            "allergies": [],
        },
        "timeline": [
            {
                "kind": "legacy_document",
                "date": "2024-06-01",
                "title": "cbc-report.pdf",
                "document_type_label": "Lab report",
                "diagnosis": "",
            }
        ],
        "include_swaasth_reports": False,
        "generated_at": "2026-07-01T00:00:00.000Z",
    }
    res = client.post("/api/reports/render-pdf", json=payload)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"
    assert "medical-history-Test-Patient.pdf" in res.headers.get(
        "content-disposition", ""
    )
