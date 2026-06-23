"""Tests for Rajiv Aarogyasri / Aarogyasri Cheyutha scheme."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rajiv_aarogyasri import (
    build_rajiv_aarogyasri_report,
    build_aliases,
    get_rajiv_aarogyasri_store,
    normalize_text,
    reset_rajiv_aarogyasri_store,
)


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_rajiv_aarogyasri_store()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

def test_normalize_text_strips_common_tokens() -> None:
    assert "apollo" in normalize_text("Apollo Hospitals Pvt Ltd, Hyderabad")


def test_build_aliases_includes_initials() -> None:
    aliases = build_aliases("Care Hospital Banjara Hills")
    assert any("banjara" in alias for alias in aliases)


def test_store_loads_hospitals_and_packages() -> None:
    store = get_rajiv_aarogyasri_store()
    assert len(store.hospitals) > 0
    assert len(store.packages) > 0


def test_match_hospital_finds_known_hospital() -> None:
    store = get_rajiv_aarogyasri_store()
    result = store.match_hospital(
        "AVS Wellness Hospitals",
        patient_district="Hyderabad",
        patient_city="Hyderabad",
        patient_state="Telangana",
    )
    assert result["matched_hospital_name"] == "AVS Wellness Hospitals"
    assert result["confidence_score"] >= 0.82


def test_match_package_finds_procedure() -> None:
    store = get_rajiv_aarogyasri_store()
    result = store.match_aarogyasri_package("Excision of Branchial Cyst")
    assert result.get("package_name") == "Excision of Branchial Cyst"
    assert result.get("approved_rate") == 25000


def test_build_report_not_selected() -> None:
    assert build_rajiv_aarogyasri_report(rajiv_aarogyasri_selected=False) is None


def test_build_report_includes_advisories_for_cancer() -> None:
    report = build_rajiv_aarogyasri_report(
        rajiv_aarogyasri_selected=True,
        rajiv_is_telangana_resident=True,
        rajiv_has_eligible_card=True,
        rajiv_has_aadhaar=True,
        rajiv_is_cancer_related=True,
        ocr_hospital_name="Princess Esra Hospital (DCMS)",
        patient_state="Telangana",
        patient_district="Hyderabad",
        patient_city="Hyderabad",
        bill_date="20/07/2024",
        line_items=[
            {
                "item_name": "Excision of Branchial Cyst",
                "total_price": 30000,
            }
        ],
        compared_line_items=[{"cghs_rate": 18000}],
    )
    assert report is not None
    assert report["selected"] is True
    titles = {item["title"] for item in report["advisories"]}
    assert "Cancer Treatment Verification" in titles
    assert "Old City Hospital Access" in titles
    assert report["package_comparisons"][0]["approved_rate"] == 25000
    assert report["package_comparisons"][0]["excess_amount"] == 5000


def test_compare_bill_includes_rajiv_report(client: TestClient) -> None:
    res = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Excision of Branchial Cyst",
                    "quantity": 1,
                    "unit_price": 30000,
                    "total_price": 30000,
                    "category": "procedure",
                }
            ],
            "state_ut_name": "Telangana",
            "city": "Hyderabad",
            "hospital_type": "general",
            "hospital_name": "AVS Wellness Hospitals",
            "rajiv_aarogyasri_selected": True,
            "rajiv_is_telangana_resident": True,
            "rajiv_has_eligible_card": True,
            "rajiv_has_aadhaar": True,
            "bill_date": "20/07/2024",
            "patient_name": "Test Patient",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    report = payload.get("rajiv_aarogyasri_report")
    assert report is not None
    assert report["selected"] is True
    assert payload["patient"]["rajiv_aarogyasri_selected"] is True
    assert report["hospital_verification"]["matched_hospital_name"] == (
        "AVS Wellness Hospitals"
    )
    assert payload["comparison_settings"]["comparison_scheme"] == "rajiv_aarogyasri"
    matched_items = [
        item
        for item in payload.get("line_items", [])
        if item.get("comparison_source") == "aarogyasri"
    ]
    assert matched_items, "Expected at least one Aarogyasri-matched line item"


def test_compare_bill_without_rajiv_has_no_report(client: TestClient) -> None:
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
        },
    )
    assert res.status_code == 200
    assert res.json().get("rajiv_aarogyasri_report") is None


def test_cghs_fallback_when_package_not_found() -> None:
    report = build_rajiv_aarogyasri_report(
        rajiv_aarogyasri_selected=True,
        rajiv_is_telangana_resident=True,
        rajiv_has_eligible_card=True,
        rajiv_has_aadhaar=True,
        ocr_hospital_name="AVS Wellness Hospitals",
        patient_state="Telangana",
        patient_district="Hyderabad",
        patient_city="Hyderabad",
        line_items=[{"item_name": "Unknown custom charge xyz", "total_price": 5000}],
        compared_line_items=[{"cghs_rate": 1200}],
    )
    assert report is not None
    comparison = report["package_comparisons"][0]
    assert comparison["fallback_used"] is True
    assert comparison["status"] == "CGHS Fallback Used"
    assert comparison["approved_rate"] == 1200


def test_owaisi_oncology_bill_triggers_advisories_and_package_search() -> None:
    ocr_text = (
        "Owaisi Hospital and Research Centre\n"
        "Hyderabad, Telangana\n"
        "Department: Oncology\n"
        "Diagnosis: Carcinoma Lung\n"
        "Procedure: Chemotherapy Cycle 1\n"
        "Chemotherapy Procedure Charges"
    )
    report = build_rajiv_aarogyasri_report(
        rajiv_aarogyasri_selected=True,
        rajiv_is_telangana_resident=True,
        rajiv_has_eligible_card=True,
        rajiv_has_aadhaar=True,
        rajiv_is_cancer_related=True,
        ocr_hospital_name="Owaisi Hospital and Research Centre",
        patient_state="Telangana",
        patient_district="Hyderabad",
        patient_city="Hyderabad",
        bill_date="25/10/2025",
        diagnosis="Carcinoma Lung",
        department="Oncology",
        ocr_text=ocr_text,
        line_items=[
            {
                "item_name": "Chemotherapy Procedure Charges",
                "total_price": 12000,
                "category": "procedure",
            }
        ],
        compared_line_items=[{"cghs_rate": 8500}],
    )
    assert report is not None
    titles = {item["title"] for item in report["advisories"]}
    assert "Revised Aarogyasri Packages" in titles
    assert "Old City Hospital Access" in titles
    assert "Cancer Treatment Verification" in titles
    assert "Cashless Package Scheme Advisory" in titles
    assert "Manual Verification Advisory" in titles
    assert report["package_search"]["searched_terms"]
    assert report["package_search"]["source_files_searched"]
    assert report["advisory_debug"]
    hospital_status = report["hospital_verification"]["status"].lower()
    assert "not found" in hospital_status or "manual verification" in hospital_status
    comparison = report["package_comparisons"][0]
    assert comparison["matched_package_name"] or comparison["fallback_used"]
