"""Tests for the unified report PDF endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _sample_cghs_report() -> dict:
    return {
        "filename": "test-bill.pdf",
        "comparison_settings": {
            "comparison_scheme": "cghs",
            "city": "Mumbai",
            "state_name": "Maharashtra",
            "tier_label": "Tier I (X City)",
            "hospital_type": "general",
            "rate_type_label": "Non-NABH",
        },
        "patient": {"name": "Test Patient", "age": 45, "gender": "Male"},
        "hospital": {"name_from_bill": "City Hospital"},
        "line_items": [
            {
                "item_name": "Complete Blood Count",
                "quantity": 1,
                "total_price": 500,
                "cghs_rate": 300,
                "price_difference": 200,
                "flag": "overpriced",
                "matched_reference_item": "CBC",
                "cghs_code": "LAB001",
            }
        ],
        "audit_flags": {"flags": [], "flags_count": 0, "risk_level": "LOW"},
    }


def _sample_pmjay_report() -> dict:
    report = _sample_cghs_report()
    report["comparison_settings"]["comparison_scheme"] = "hbp_pmjay"
    report["patient"]["ayushman_eligible"] = True
    report["line_items"][0]["comparison_source"] = "hbp"
    report["line_items"][0]["hbp_rate"] = 280
    report["line_items"][0].pop("cghs_rate", None)
    return report


def test_unified_render_pdf_cghs() -> None:
    res = client.post("/api/reports/render-pdf", json=_sample_cghs_report())
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"
    assert "cghs-Test-Patient.pdf" in res.headers.get("content-disposition", "")


def test_unified_render_pdf_pmjay() -> None:
    res = client.post("/api/reports/render-pdf", json=_sample_pmjay_report())
    assert res.status_code == 200, res.text
    assert res.content[:5] == b"%PDF-"


def test_unified_render_pdf_rejects_empty_report() -> None:
    res = client.post("/api/reports/render-pdf", json={})
    assert res.status_code == 400


def test_unified_render_pdf_includes_hospitalisation_relief_advisory() -> None:
    report = _sample_cghs_report()
    report["hospitalisation_relief_advisory"] = {
        "title": "Hospitalisation Relief Scheme Advisory",
        "eligibility_summary": ["Eligible worker criteria."],
        "benefit": {
            "daily_relief": "₹300 per day of hospitalization.",
            "monthly_maximum": "Maximum reimbursement/relief: ₹4,500 per month.",
        },
        "applicant_status": "Registered worker status message.",
        "how_to_apply": ["Visit the official Telangana labour/board website."],
        "documents_required": ["Passport-size photograph"],
        "important_note": "Advisory disclaimer text.",
    }
    res = client.post("/api/reports/render-pdf", json=report)
    assert res.status_code == 200, res.text
    assert res.content[:5] == b"%PDF-"


def test_unified_render_pdf_includes_kcr_kit_advisory() -> None:
    report = _sample_cghs_report()
    report["kcr_kit_advisory"] = {
        "title": "KCR Kit / Pregnancy Nutrition Kit Advisory",
        "description": "Advisory description.",
        "status_badge": "May Be Eligible",
        "eligibility_summary": ["Patient must be a pregnant woman."],
        "exclusions": ["Non-residents of Telangana are not eligible."],
        "applicant_status_messages": [
            "Based on the information provided, the patient may be eligible."
        ],
        "application_process": ["Contact the nearest Anganwadi Centre."],
        "documents_required": ["Aadhaar Card"],
        "important_note": "Advisory disclaimer text.",
    }
    res = client.post("/api/reports/render-pdf", json=report)
    assert res.status_code == 200, res.text
    assert res.content[:5] == b"%PDF-"


def test_unified_render_pdf_prescription_report() -> None:
    report = {
        "report_kind": "prescription",
        "filename": "prescription.pdf",
        "diagnosis": "Malaria",
        "patient": {"name": "Test Patient"},
        "prescription": {
            "medicines": [{"name": "Artemether-Lumefantrine"}],
            "tests": [{"name": "Malaria smear"}],
            "procedures": [],
        },
        "treatment_audit_flags": {
            "flags_count": 1,
            "risk_level": "MEDIUM",
            "matched_stg_conditions": ["Malaria"],
            "flags": [
                {
                    "type": "UNNECESSARY_TEST",
                    "severity": "MEDIUM",
                    "item": "MRI Brain",
                    "reason": "Not indicated for malaria in STG excerpts.",
                    "recommendation": "Ask the doctor to justify the test.",
                    "stg_reference": {
                        "condition": "Malaria",
                        "section": "Diagnostic tests",
                        "page": 58,
                    },
                }
            ],
        },
    }
    res = client.post("/api/reports/render-pdf", json=report)
    assert res.status_code == 200, res.text
    assert res.content[:5] == b"%PDF-"
