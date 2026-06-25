"""Tests for CGHS city-wise costs loader and compare-bill integration."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.cghs_costs import (
    build_cghs_costs_report,
    build_search_terms,
    get_cghs_costs_store,
)
from app.main import app

client = TestClient(app)


def test_store_loads_cleaned_csv() -> None:
    store = get_cghs_costs_store()
    assert store is not None
    assert len(store.rows) >= 20000
    assert len(store.cities) >= 20
    assert "Delhi and NCR" in store.cities
    assert "Mumbai" in store.cities
    assert "Hyderabad" in store.cities


def test_store_skips_manual_review_rows(tmp_path) -> None:
    csv_path = tmp_path / "cghs_all_cities_cleaned_for_app.csv"
    csv_path.write_text(
        "city,procedure_name,nabh_rate,non_nabh_rate,cghs_rate,"
        "extraction_method,needs_manual_review,quality_status\n"
        "Delhi and NCR,Consultation OPD,350,350,,pdfplumber,False,clean\n"
        "Delhi and NCR,Bad OCR Row,100,90,,ocr,True,needs_review\n"
        "Delhi and NCR,,350,350,,pdfplumber,False,clean\n"
        "Delhi and NCR,No Rate Row,,,,pdfplumber,False,clean\n",
        encoding="utf-8",
    )
    from app.cghs_costs import CghsCostsStore

    store = CghsCostsStore(csv_path=csv_path)
    assert len(store.rows) == 1
    assert store.rows[0].procedure_name == "Consultation OPD"


def test_city_aliases() -> None:
    store = get_cghs_costs_store()
    assert store is not None
    assert store.normalize_city("Delhi") == "Delhi and NCR"
    assert store.normalize_city("New Delhi") == "Delhi and NCR"
    assert store.normalize_city("Bangalore") == "Bengaluru"
    assert store.normalize_city("Kanpur") == "Kanpur and Gwalior"
    assert store.normalize_city("Prayagraj") == "Allahabad and Prayagraj and Varanasi"


def test_find_match_delhi_exact() -> None:
    store = get_cghs_costs_store()
    assert store is not None
    match, debug = store.find_match_detailed(
        "Consultation OPD",
        city="Delhi",
        nabh_accredited=False,
    )
    assert match is not None
    assert match["selected_rate"] == 350
    assert match["city"] == "Delhi and NCR"
    assert debug["city_wise_match_found"] is True


def test_find_match_delhi_consultations_synonym() -> None:
    store = get_cghs_costs_store()
    assert store is not None
    terms = build_search_terms("Consultations")
    assert "consultation opd" in terms
    match, debug = store.find_match_detailed(
        "Consultations",
        city="Delhi",
        nabh_accredited=False,
    )
    assert debug["city_wise_attempted"] is True
    assert match is not None
    assert "consultation" in match["matched_procedure_name"].lower()
    assert match["selected_rate"] == 350


def test_find_match_mumbai() -> None:
    store = get_cghs_costs_store()
    assert store is not None
    match, _debug = store.find_match_detailed(
        "Dressings of wounds",
        city="Mumbai",
        nabh_accredited=False,
    )
    assert match is not None
    assert match["selected_rate"] == 255


def test_room_rent_jaipur_city_match() -> None:
    store = get_cghs_costs_store()
    assert store is not None
    match, debug = store.find_match_detailed(
        "Room Rent - General Ward",
        city="Jaipur",
        nabh_accredited=False,
    )
    assert debug["city_wise_match_found"] is True
    assert match is not None
    assert match["selected_rate"] == 1500


def test_room_rent_delhi_no_city_row_then_no_bad_fuzzy() -> None:
    store = get_cghs_costs_store()
    assert store is not None
    match, debug = store.find_match_detailed(
        "Room Rent - General Ward",
        city="Delhi",
        nabh_accredited=False,
    )
    assert match is None
    assert debug["city_wise_attempted"] is True
    assert debug["city_rows_count"] >= 1800
    assert "room rent general ward" in debug["searched_terms"]


def test_generic_pharmacy_special_handling() -> None:
    store = get_cghs_costs_store()
    assert store is not None
    match, debug = store.find_match_detailed("Pharmacy", city="Delhi")
    assert match is None
    assert debug["special_handling"] == "generic_pharmacy"


def test_hyderabad_limited_data_flag() -> None:
    store = get_cghs_costs_store()
    assert store is not None
    assert store.city_has_limited_data("Hyderabad") is True


def test_build_report_with_city_match() -> None:
    report = build_cghs_costs_report(
        enabled=True,
        patient_city="Delhi",
        hospital_type="general",
        nabh_accredited=False,
        line_items=[{"item_name": "Consultation OPD", "total_price": 500}],
        compared_line_items=[
            {
                "comparison_source": "cghs_city_costs",
                "cghs_rate": 350,
                "matched_reference_item": "Consultation OPD",
                "cghs_costs_rate_type": "non_nabh",
                "nabh_rate": 350,
                "non_nabh_rate": 350,
                "cghs_costs_extraction_method": "pdfplumber",
                "cghs_costs_quality_status": "clean",
                "cghs_costs_confidence": 1.0,
                "cghs_costs_match_reason": "Exact normalized match",
            }
        ],
    )
    assert report is not None
    assert report["match_found"] is True
    assert report["city_rows_count"] >= 1800
    assert report["data_source_file"] == "cghs_all_cities_cleaned_for_app.csv"
    assert report["data_source_display"] == "CGHS city-wise costs data"
    comparison = report["comparisons"][0]
    assert comparison["selected_rate"] == 350
    assert comparison["source_label"] == "CGHS city-wise costs CSV"
    assert comparison["source_display"] == "CGHS city-wise costs data"
    assert comparison["rate_type_display"] in {"NABH", "Non-NABH", "CGHS Rate"}
    assert "source_pdf" not in comparison


def test_compare_bill_delhi_city_match() -> None:
    response = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Consultation OPD",
                    "quantity": 1,
                    "unit_price": 500,
                    "total_price": 500,
                    "category": "procedure",
                }
            ],
            "city": "Delhi",
            "state_ut_name": "Delhi",
            "hospital_type": "general",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["comparison_settings"]["comparison_scheme"] == "cghs"
    assert payload["cghs_costs_report"]["match_found"] is True
    assert payload["cghs_costs_report"]["city_used"] == "Delhi and NCR"
    assert (
        payload["cghs_costs_report"]["data_source_display"]
        == "CGHS city-wise costs data"
    )
    item = payload["line_items"][0]
    assert item["comparison_source"] == "cghs_city_costs"
    assert item["cghs_rate"] == 350
    comparison = payload["cghs_costs_report"]["comparisons"][0]
    assert comparison["source_display"] == "CGHS city-wise costs data"
    assert comparison["source_city"] == "Delhi and NCR"
    assert "source_pdf" not in comparison


def test_compare_bill_delhi_consultations_synonym() -> None:
    response = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Consultations",
                    "quantity": 1,
                    "unit_price": 500,
                    "total_price": 500,
                    "category": "procedure",
                }
            ],
            "city": "Delhi",
            "state_ut_name": "Delhi",
            "hospital_type": "general",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    item = payload["line_items"][0]
    assert item["comparison_source"] == "cghs_city_costs"
    assert item["cghs_rate"] == 350


def test_compare_bill_mumbai_city_match() -> None:
    response = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Dressings of wounds",
                    "quantity": 1,
                    "unit_price": 400,
                    "total_price": 400,
                    "category": "procedure",
                }
            ],
            "city": "Mumbai",
            "state_ut_name": "Maharashtra",
            "hospital_type": "general",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    item = payload["line_items"][0]
    assert item["comparison_source"] == "cghs_city_costs"
    assert item["cghs_rate"] == 255


def test_compare_bill_hyderabad_unknown_item() -> None:
    response = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "zzzznonexistentprocedure999",
                    "quantity": 1,
                    "unit_price": 1000,
                    "total_price": 1000,
                    "category": "procedure",
                }
            ],
            "city": "Hyderabad",
            "state_ut_name": "Telangana",
            "hospital_type": "general",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["cghs_costs_report"]["limited_city_data"] is True
    assert payload["line_items"][0]["flag"] == "no_reference"


def test_compare_bill_pharmacy_advisory() -> None:
    response = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Pharmacy",
                    "quantity": 1,
                    "unit_price": 5000,
                    "total_price": 5000,
                    "category": "other",
                }
            ],
            "city": "Delhi",
            "state_ut_name": "Delhi",
            "hospital_type": "general",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    item = payload["line_items"][0]
    assert item["cghs_generic_pharmacy"] is True
    assert item["cghs_rate"] is None
    comparison = payload["cghs_costs_report"]["comparisons"][0]
    assert comparison["generic_pharmacy"] is True
    assert comparison["status"] == "Verify Medicine Pricing"


def test_compare_bill_delhi_room_rent_no_bad_tier_fallback() -> None:
    response = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Room Rent",
                    "quantity": 1,
                    "unit_price": 8000,
                    "total_price": 8000,
                    "category": "other",
                }
            ],
            "city": "Delhi",
            "state_ut_name": "Delhi",
            "hospital_type": "general",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    item = payload["line_items"][0]
    assert item["comparison_source"] == "cghs"
    assert item["cghs_rate"] is None
    assert item["flag"] == "no_reference"


def test_compare_bill_pmjay_unaffected() -> None:
    response = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Consultation OPD",
                    "quantity": 1,
                    "unit_price": 500,
                    "total_price": 500,
                    "category": "procedure",
                }
            ],
            "city": "Delhi",
            "state_ut_name": "Delhi",
            "hospital_type": "general",
            "pmjay_eligible": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["comparison_settings"]["comparison_scheme"] == "hbp_pmjay"
    assert payload.get("cghs_costs_report") is None

