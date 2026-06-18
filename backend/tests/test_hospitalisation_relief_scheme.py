"""Tests for Hospitalisation Relief Scheme advisory."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.hospitalisation_relief_scheme import build_hospitalisation_relief_advisory
from app.main import app

client = TestClient(app)


def test_build_advisory_when_not_selected() -> None:
    assert build_hospitalisation_relief_advisory(
        hospitalisation_relief_scheme_selected=False,
        is_registered_construction_worker=True,
    ) is None


def test_build_advisory_registered_worker() -> None:
    advisory = build_hospitalisation_relief_advisory(
        hospitalisation_relief_scheme_selected=True,
        is_registered_construction_worker=True,
    )
    assert advisory is not None
    assert advisory["title"] == "Hospitalisation Relief Scheme Advisory"
    assert advisory["is_registered_construction_worker"] is True
    assert "registered construction worker" in advisory["applicant_status"]


def test_build_advisory_unregistered_worker() -> None:
    advisory = build_hospitalisation_relief_advisory(
        hospitalisation_relief_scheme_selected=True,
        is_registered_construction_worker=False,
    )
    assert advisory is not None
    assert advisory["is_registered_construction_worker"] is False
    assert "not registered" in advisory["applicant_status"]


def test_compare_bill_includes_hospitalisation_relief_advisory() -> None:
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
            "hospitalisation_relief_scheme_selected": True,
            "is_registered_construction_worker": True,
            "patient_name": "Test Worker",
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["patient"]["hospitalisation_relief_scheme_selected"] is True
    assert payload["patient"]["is_registered_construction_worker"] is True
    advisory = payload.get("hospitalisation_relief_advisory")
    assert advisory is not None
    assert advisory["title"] == "Hospitalisation Relief Scheme Advisory"


def test_compare_bill_omits_advisory_when_scheme_not_selected() -> None:
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
            "patient_name": "Test Worker",
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload.get("hospitalisation_relief_advisory") is None
