"""Tests for PM-JAY hospital directory and verification."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.pmjay_hospitals import (
    PmjayHospitalStore,
    build_pmjay_hospital_verification,
    get_pmjay_hospital_store,
    normalize_text,
)

client = TestClient(app)


def test_store_loads_hospitals() -> None:
    store = get_pmjay_hospital_store()
    assert len(store.hospitals) > 0
    names = {record.hospital_name for record in store.hospitals}
    assert any("Gandhi" in name for name in names)


def test_normalize_text_strips_common_words() -> None:
    assert "apollo" in normalize_text("Apollo Hospitals Pvt Ltd")


def test_match_exact_hospital() -> None:
    store = get_pmjay_hospital_store()
    gandhi = next(
        record
        for record in store.hospitals
        if "Gandhi Hospitals" in record.hospital_name
    )
    match = store.match_pmjay_hospital(
        gandhi.hospital_name,
        patient_state=gandhi.state,
        patient_district=gandhi.district,
        patient_city=gandhi.city,
    )
    assert match["status"] == "empanelled"
    assert match["matched_hospital_name"] == gandhi.hospital_name
    assert match["confidence_score"] >= 0.9


def test_match_fuzzy_ocr_spelling() -> None:
    store = get_pmjay_hospital_store()
    match = store.match_pmjay_hospital(
        "Apolo Hospitl Gandhi",
        patient_state="Telangana",
        patient_district="Hyderabad",
    )
    assert match["confidence_score"] >= 0.55


def test_match_not_found() -> None:
    store = get_pmjay_hospital_store()
    match = store.match_pmjay_hospital("Totally Unknown Hospital XYZ 999")
    assert match["status"] == "not_found"


def test_match_missing_ocr_name() -> None:
    store = get_pmjay_hospital_store()
    match = store.match_pmjay_hospital("")
    assert match["status"] == "manual_verification_required"


def test_store_deduplicates(tmp_path) -> None:
    csv_path = tmp_path / "pmjay_empanelled_hospitals.csv"
    csv_path.write_text(
        "scheme_code,hospital_id,hospital_name,aliases,state,district,city,address,"
        "hospital_type,empanelment_type,empanelment_status,specialities,source,last_updated\n"
        'PMJAY,H1,Test Hospital,"Test Hospital",Telangana,Hyderabad,Hyderabad,,Public,PMJAY,active,,test,2026-06-24\n'
        'PMJAY,H1,Test Hospital,"Test Hospital",Telangana,Hyderabad,Hyderabad,,Public,PMJAY,active,,test,2026-06-24\n',
        encoding="utf-8",
    )
    store = PmjayHospitalStore(csv_path=csv_path)
    assert len(store.hospitals) == 1


def test_suspended_status(tmp_path) -> None:
    csv_path = tmp_path / "pmjay_empanelled_hospitals.csv"
    csv_path.write_text(
        "scheme_code,hospital_id,hospital_name,aliases,state,district,city,address,"
        "hospital_type,empanelment_type,empanelment_status,specialities,source,last_updated\n"
        'PMJAY,H2,Suspended Hospital,"Suspended Hospital",Telangana,Hyderabad,Hyderabad,,Public,PMJAY,suspended,,test,2026-06-24\n',
        encoding="utf-8",
    )
    store = PmjayHospitalStore(csv_path=csv_path)
    match = store.match_pmjay_hospital("Suspended Hospital")
    assert match["status"] == "suspended"


def test_build_verification_includes_eligibility_advisory() -> None:
    verification = build_pmjay_hospital_verification(
        pmjay_selected=True,
        ocr_hospital_name="Gandhi Hospitals",
        patient_state="Telangana",
        patient_district="Hyderabad",
        pmjay_has_ayushman_card=None,
    )
    assert verification is not None
    assert verification["selected"] is True
    assert any("eligibility" in msg.lower() for msg in verification["advisories"])


def test_build_verification_not_selected() -> None:
    assert build_pmjay_hospital_verification(pmjay_selected=False, ocr_hospital_name="X") is None


def test_search_endpoint() -> None:
    res = client.get("/api/schemes/pmjay/hospitals/search", params={"q": "Gandhi", "limit": 5})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["total"] >= 1


def test_compare_bill_includes_pmjay_verification() -> None:
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
            "hospital_name": "Gandhi Hospitals",
            "pmjay_eligible": True,
            "pmjay_has_ayushman_card": True,
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    verification = payload.get("pmjay_hospital_verification")
    assert verification is not None
    assert verification["selected"] is True
    assert payload["comparison_settings"]["comparison_scheme"] == "hbp_pmjay"


def test_compare_bill_omits_pmjay_verification_when_not_selected() -> None:
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
            "hospital_name": "Gandhi Hospitals",
            "pmjay_eligible": False,
        },
    )
    assert res.status_code == 200, res.text
    assert res.json().get("pmjay_hospital_verification") is None
