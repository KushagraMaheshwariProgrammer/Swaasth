"""API-level tests for Aarogya Bhadratha endpoints (no Groq/OCR required)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _first_hospital_id() -> str:
    res = client.get("/api/aarogya-bhadratha/hospitals", params={"limit": 1})
    assert res.status_code == 200
    results = res.json()["results"]
    if not results:
        pytest.skip("No Aarogya hospitals available")
    return results[0]["id"]


def test_districts_endpoint() -> None:
    res = client.get("/api/aarogya-bhadratha/districts")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    assert res.json()


def test_specialities_endpoint() -> None:
    res = client.get("/api/aarogya-bhadratha/specialities")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_search_endpoint() -> None:
    res = client.get(
        "/api/aarogya-bhadratha/hospitals/search",
        params={"query": "apollo", "limit": 5},
    )
    assert res.status_code == 200
    body = res.json()
    assert "total" in body and "results" in body


def test_verify_hospital_endpoint() -> None:
    res = client.post(
        "/api/aarogya-bhadratha/verify-hospital",
        json={"hospital_name": "Apollo Hospital, Hyderguda", "district": "Hyderabad"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["empanelment_status"] in {"empanelled", "multiple", "not_found"}


def test_verify_missing_name() -> None:
    res = client.post(
        "/api/aarogya-bhadratha/verify-hospital", json={"hospital_name": ""}
    )
    assert res.status_code == 200
    assert res.json()["empanelment_status"] == "name_missing"


def test_compare_and_report_and_pdf_flow() -> None:
    hospital_id = _first_hospital_id()
    res = client.post(
        "/api/aarogya-bhadratha/compare-rates",
        json={
            "hospital_id": hospital_id,
            "patient": {
                "name": "Test Patient",
                "state": "Telangana",
                "aarogya_bhadratha_eligible": True,
            },
            "line_items": [
                {"item_name": "General Anaesthesia", "quantity": 1, "total_price": 2500},
                {"item_name": "Zzqq Unknown Charge", "quantity": 1, "total_price": 900},
            ],
            "bill": {"filename": "bill.pdf", "bill_date": "01/05/2024"},
            "ocr_hospital_name": "Apollo Hospital",
        },
    )
    assert res.status_code == 200, res.text
    report = res.json()
    assert report["report_kind"] == "aarogya_bhadratha"
    report_id = report["report_id"]
    assert report["comparison"]["summary"]["total_items"] == 2

    fetched = client.get(f"/api/aarogya-bhadratha/reports/{report_id}")
    assert fetched.status_code == 200
    assert fetched.json()["report_id"] == report_id

    pdf = client.get(f"/api/aarogya-bhadratha/reports/{report_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-"

    # stateless render-pdf works from the report object alone
    rendered = client.post("/api/aarogya-bhadratha/reports/render-pdf", json=report)
    assert rendered.status_code == 200
    assert rendered.content[:5] == b"%PDF-"


def test_compare_rejects_unknown_hospital() -> None:
    res = client.post(
        "/api/aarogya-bhadratha/compare-rates",
        json={
            "hospital_id": "abh-does-not-exist",
            "line_items": [{"item_name": "x", "total_price": 1}],
        },
    )
    assert res.status_code == 404


def test_report_not_found() -> None:
    res = client.get("/api/aarogya-bhadratha/reports/nonexistent")
    assert res.status_code == 404
