"""Tests for scheme-free bill comparison flow."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_startup_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.text == "Backend is running"


def test_compare_bill_without_scheme_fields() -> None:
    res = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Paracetamol 500mg",
                    "quantity": 10,
                    "unit_price": 5,
                    "total_price": 50,
                    "category": "medicine",
                }
            ],
            "state_ut_name": "Maharashtra",
            "city": "Mumbai",
            "hospital_type": "general",
            "hospital_name": "Test Hospital",
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["comparison_settings"]["comparison_scheme"] == "general"
    assert "cghs_costs_report" not in payload
    assert "pmjay_hospital_verification" not in payload
    assert "rajiv_aarogyasri_report" not in payload
    assert "ehs_jhs_report" not in payload
    assert "kcr_kit_advisory" not in payload
    assert "hospitalisation_relief_advisory" not in payload
    assert payload.get("line_items")
    assert payload.get("audit_flags") is not None
    assert payload.get("jan_aushadhi") is not None
    assert payload["jan_aushadhi"].get("matches")
    assert payload["line_items"][0].get("jan_aushadhi_available") is True


def test_compare_bill_includes_restricted_medicine_flags_shape() -> None:
    res = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Consultation",
                    "quantity": 1,
                    "unit_price": 500,
                    "total_price": 500,
                    "category": "procedure",
                }
            ],
            "state_ut_name": "Karnataka",
            "city": "Bengaluru",
            "hospital_type": "general",
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert "restricted_medicine_flags" in payload
