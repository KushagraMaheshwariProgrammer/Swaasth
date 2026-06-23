"""Tests for CGHS eligibility advisory."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.cghs_eligibility import (
    build_cghs_eligibility_advisory,
    build_cghs_eligibility_preview,
)
from app.main import app

client = TestClient(app)


def test_build_advisory_when_cghs_not_used() -> None:
    assert build_cghs_eligibility_advisory(
        comparison_scheme="hbp_pmjay",
        cghs_fallback_from_aarogya=False,
        line_items=[],
    ) is None


def test_build_advisory_main_cghs_scheme() -> None:
    advisory = build_cghs_eligibility_advisory(
        comparison_scheme="cghs",
        cghs_fallback_from_aarogya=False,
        line_items=[],
    )
    assert advisory is not None
    assert advisory["title"] == "CGHS Eligibility Criteria"
    assert advisory["mode"] == "full"
    assert len(advisory["groups"]) == 6


def test_build_advisory_cghs_aarogya_fallback() -> None:
    advisory = build_cghs_eligibility_advisory(
        comparison_scheme="cghs",
        cghs_fallback_from_aarogya=True,
        line_items=[],
    )
    assert advisory is not None
    assert advisory["mode"] == "fallback"
    assert "benchmark/fallback" in advisory["fallback_note"]


def test_build_advisory_rajiv_item_fallback() -> None:
    advisory = build_cghs_eligibility_advisory(
        comparison_scheme="rajiv_aarogyasri",
        line_items=[{"aarogyasri_fallback_used": True}],
    )
    assert advisory is not None
    assert advisory["mode"] == "fallback"


def test_eligibility_preview_confirmed_category_and_city() -> None:
    messages = build_cghs_eligibility_preview(
        beneficiary_category="central_gov_employee",
        resides_in_covered_city=True,
    )
    assert any("may fall under" in message.lower() for message in messages)


def test_eligibility_preview_city_no() -> None:
    messages = build_cghs_eligibility_preview(
        beneficiary_category="central_gov_employee",
        resides_in_covered_city=False,
    )
    assert any("cghs-covered city" in message.lower() for message in messages)


def test_compare_bill_includes_cghs_eligibility_advisory() -> None:
    res = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Room rent",
                    "quantity": 1,
                    "unit_price": 2000,
                    "total_price": 2000,
                    "category": "other",
                }
            ],
            "state_ut_name": "Telangana",
            "city": "Hyderabad",
            "hospital_type": "general",
            "patient_name": "CGHS Patient",
            "cghs_beneficiary_category": "central_gov_employee",
            "cghs_eligible_category_confirmed": True,
            "cghs_resides_in_covered_city": True,
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    advisory = payload.get("cghs_eligibility_advisory")
    assert advisory is not None
    assert advisory["mode"] == "full"
    assert payload["comparison_settings"]["comparison_scheme"] == "cghs"


def test_compare_bill_omits_cghs_advisory_for_pmjay() -> None:
    res = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Room rent",
                    "quantity": 1,
                    "unit_price": 2000,
                    "total_price": 2000,
                    "category": "other",
                }
            ],
            "state_ut_name": "Telangana",
            "city": "Hyderabad",
            "hospital_type": "general",
            "pmjay_eligible": True,
            "patient_name": "PMJAY Patient",
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload.get("cghs_eligibility_advisory") is None
