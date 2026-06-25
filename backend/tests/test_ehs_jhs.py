"""Tests for EHS/JHS shared package and hospital engine."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.ehs_jhs import (
    build_ehs_jhs_report,
    get_ehs_jhs_store,
    normalize_text,
)
from app.main import app

client = TestClient(app)


def test_store_loads_packages_and_hospitals() -> None:
    store = get_ehs_jhs_store()
    assert len(store.packages) >= 1800
    assert len(store.hospitals) >= 300
    assert store.meta.get("primary_sheet") == "Sheet1"


def test_match_hospital_from_csv() -> None:
    store = get_ehs_jhs_store()
    apollo = next(
        record
        for record in store.hospitals
        if "Apollo Institute" in record.hospital_name
    )
    match = store.match_hospital(
        apollo.hospital_name,
        patient_district=apollo.district,
        patient_city=apollo.municipality,
    )
    assert match["status"] == "empanelled"
    assert match["matched_hospital_name"] == apollo.hospital_name
    assert match["source_file"] == "EHS_hospital_list.csv"


def test_match_hospital_not_found() -> None:
    store = get_ehs_jhs_store()
    match = store.match_hospital("Totally Unknown Hospital XYZ 999")
    assert match["status"] == "not_found"


def test_match_package_from_excel_data() -> None:
    store = get_ehs_jhs_store()
    match = store.match_package("Excision of Ganglion")
    assert match.get("matched_package")
    assert match.get("approved_rate") is not None
    assert match.get("approved_rate") > 0


def test_specialities_readable_no_raw_codes_only() -> None:
    store = get_ehs_jhs_store()
    record = next(
        (item for item in store.hospitals if item.specialities_readable),
        None,
    )
    if record is None:
        return
    for name in record.specialities_readable:
        assert not name.strip().upper().startswith("S1 -") or " " in name


def test_build_ehs_report_selected() -> None:
    report = build_ehs_jhs_report(
        scheme_type="EHS",
        selected=True,
        ehs_is_government_employee=True,
        ehs_has_health_card=True,
        ocr_hospital_name="Apollo Institute of Mecdical Sciences and Research",
        line_items=[{"item_name": "Excision of Ganglion", "total_price": 15000}],
        compared_line_items=[{"cghs_rate": 5000}],
    )
    assert report is not None
    assert report["scheme_type"] == "EHS"
    assert report["selected"] is True
    assert report["hospital_verification"]["status"] == "empanelled"
    assert len(report["package_comparisons"]) == 1


def test_build_jhs_report_selected() -> None:
    report = build_ehs_jhs_report(
        scheme_type="JHS",
        selected=True,
        jhs_is_working_journalist=True,
        ocr_hospital_name="Unknown Hospital Name 12345",
        line_items=[{"item_name": "zzzzqqqnonexistent999", "total_price": 1000}],
        compared_line_items=[{"cghs_rate": 800}],
    )
    assert report is not None
    assert report["scheme_type"] == "JHS"
    assert report["hospital_verification"]["status"] == "not_found"
    assert report["package_comparisons"][0]["fallback_used"] is True


def test_build_report_not_selected() -> None:
    assert build_ehs_jhs_report(scheme_type="EHS", selected=False) is None


def test_compare_bill_ehs_selected() -> None:
    response = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Excision of Ganglion",
                    "quantity": 1,
                    "unit_price": 15000,
                    "total_price": 15000,
                    "category": "procedure",
                }
            ],
            "city": "Hyderabad",
            "state_ut_name": "Telangana",
            "hospital_type": "general",
            "hospital_name": "Apollo Institute of Mecdical Sciences and Research",
            "ehs_selected": True,
            "ehs_is_government_employee": True,
            "ehs_has_health_card": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["comparison_settings"]["comparison_scheme"] == "ehs"
    assert payload["ehs_jhs_report"]["scheme_type"] == "EHS"
    assert payload["ehs_jhs_report"]["selected"] is True


def test_compare_bill_jhs_selected() -> None:
    response = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Excision of Ganglion",
                    "quantity": 1,
                    "unit_price": 15000,
                    "total_price": 15000,
                    "category": "procedure",
                }
            ],
            "city": "Hyderabad",
            "state_ut_name": "Telangana",
            "hospital_type": "general",
            "hospital_name": "Apollo Institute of Mecdical Sciences and Research",
            "jhs_selected": True,
            "jhs_is_working_journalist": True,
            "jhs_has_health_card": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["comparison_settings"]["comparison_scheme"] == "jhs"
    assert payload["ehs_jhs_report"]["scheme_type"] == "JHS"


def test_normalize_text() -> None:
    assert "apollo" in normalize_text("Apollo Hospitals Pvt Ltd")
