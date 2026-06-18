"""Tests for KCR Kit / Pregnancy Nutrition Kit advisory."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.kcr_kit_scheme import build_kcr_kit_advisory
from app.main import app

client = TestClient(app)


def _eligible_flags() -> dict[str, bool]:
    return {
        "kcr_is_pregnant": True,
        "kcr_is_telangana_resident": True,
        "kcr_age_18_or_above": True,
        "kcr_income_below_10000": True,
        "kcr_government_hospital_treatment": True,
        "kcr_more_than_two_live_children": False,
        "kcr_aadhaar_telangana": True,
    }


def test_build_advisory_when_not_selected() -> None:
    assert build_kcr_kit_advisory(kcr_kit_selected=False) is None


def test_build_advisory_may_be_eligible() -> None:
    advisory = build_kcr_kit_advisory(kcr_kit_selected=True, **_eligible_flags())
    assert advisory is not None
    assert advisory["status_badge"] == "May Be Eligible"
    assert any("pregnant and 18 years or older" in msg for msg in advisory["applicant_status_messages"])


def test_build_advisory_not_pregnant() -> None:
    flags = _eligible_flags()
    flags["kcr_is_pregnant"] = False
    advisory = build_kcr_kit_advisory(kcr_kit_selected=True, **flags)
    assert advisory is not None
    assert advisory["status_badge"] == "Not Eligible"
    assert any("not marked as pregnant" in msg.lower() for msg in advisory["applicant_status_messages"])


def test_build_advisory_private_hospital() -> None:
    flags = _eligible_flags()
    flags["kcr_government_hospital_treatment"] = False
    advisory = build_kcr_kit_advisory(kcr_kit_selected=True, **flags)
    assert advisory is not None
    assert any("not receiving treatment at a government hospital" in msg for msg in advisory["applicant_status_messages"])


def test_build_advisory_more_than_two_children() -> None:
    flags = _eligible_flags()
    flags["kcr_more_than_two_live_children"] = True
    advisory = build_kcr_kit_advisory(kcr_kit_selected=True, **flags)
    assert advisory is not None
    assert any("more than two live children" in msg for msg in advisory["applicant_status_messages"])


def test_compare_bill_includes_kcr_kit_advisory() -> None:
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
            "kcr_kit_selected": True,
            **_eligible_flags(),
            "patient_name": "Test Patient",
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["patient"]["kcr_kit_selected"] is True
    advisory = payload.get("kcr_kit_advisory")
    assert advisory is not None
    assert advisory["title"] == "KCR Kit / Pregnancy Nutrition Kit Advisory"


def test_compare_bill_omits_kcr_advisory_when_not_selected() -> None:
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
            "patient_name": "Test Patient",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json().get("kcr_kit_advisory") is None
