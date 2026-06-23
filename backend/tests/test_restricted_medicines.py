"""Tests for restricted medicine detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.restricted_medicines import (
    RestrictedMedicinesStore,
    build_restricted_medicine_flags,
    match_restricted_medicines,
    normalize_medicine_text,
)


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "restricted_medicines.csv"
    csv_path.write_text(
        "medicine_name,generic_name,aliases,brand_names,restriction_type,schedule_or_category,reason,severity,source,notes\n"
        'Tramadol,Tramadol,"Tramadol Hydrochloride|Tramadol HCL","Ultram|Contramal",Controlled Medicine,Schedule H1,Requires caution/prescription verification,High,User database,Flag if found in prescription\n',
        encoding="utf-8",
    )
    return csv_path


@pytest.fixture()
def store(sample_csv: Path) -> RestrictedMedicinesStore:
    return RestrictedMedicinesStore(sample_csv)


def test_normalize_medicine_text_strips_noise() -> None:
    assert normalize_medicine_text("Tramadol 50mg Tablets IP") == "tramadol"


def test_exact_name_in_ocr_text(store: RestrictedMedicinesStore) -> None:
    flags = match_restricted_medicines(
        "Patient prescribed Tramadol 50mg twice daily",
        [],
        store=store,
    )
    assert len(flags) == 1
    assert flags[0]["matched_medicine_name"] == "Tramadol"
    assert flags[0]["confidence_score"] >= 0.95


def test_brand_alias_match(store: RestrictedMedicinesStore) -> None:
    flags = match_restricted_medicines(
        "",
        [{"name": "Ultram 50 mg", "category": "medicine"}],
        store=store,
    )
    assert len(flags) == 1
    assert flags[0]["matched_medicine_name"] == "Tramadol"


def test_fuzzy_match_on_extracted_item(store: RestrictedMedicinesStore) -> None:
    flags = match_restricted_medicines(
        "",
        [{"name": "Tramadoll", "category": "medicine"}],
        store=store,
    )
    assert len(flags) == 1
    assert flags[0]["confidence_score"] >= 0.85


def test_normal_medicine_not_flagged(store: RestrictedMedicinesStore) -> None:
    flags = match_restricted_medicines(
        "Take Paracetamol 500 mg after food",
        [{"name": "Paracetamol 500 mg", "category": "medicine"}],
        store=store,
    )
    assert flags == []


def test_missing_csv_does_not_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing_store = RestrictedMedicinesStore(tmp_path / "missing.csv")
    monkeypatch.setattr("app.restricted_medicines._store", missing_store)
    payload = build_restricted_medicine_flags(
        ocr_text="Tramadol",
        prescription_items=[{"name": "Tramadol", "category": "medicine"}],
    )
    assert missing_store.is_available() is False
    assert payload["detected"] is False
    assert payload["flags"] == []


def test_build_restricted_medicine_flags_structure(
    store: RestrictedMedicinesStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.restricted_medicines._store", store)
    payload = build_restricted_medicine_flags(
        ocr_text="Ultram tablet",
        prescription_items=[],
    )
    assert payload["detected"] is True
    assert payload["flags"]
    assert payload["advisory"]
    assert payload["disclaimer"]


def test_render_restricted_medicine_flags_html() -> None:
    from app.restricted_medicines import render_restricted_medicine_flags_html

    html = render_restricted_medicine_flags_html(
        {
            "restricted_medicine_flags": {
                "detected": True,
                "flags": [
                    {
                        "detected_text": "Tramadol",
                        "matched_medicine_name": "Tramadol",
                        "generic_name": "Tramadol",
                        "restriction_type": "Controlled Medicine",
                        "schedule_or_category": "Schedule H1",
                        "reason": "Requires caution",
                        "severity": "High",
                        "confidence_score": 0.97,
                        "match_reason": "Exact match in OCR text",
                        "source": "User database",
                    }
                ],
                "advisory": "Verify with doctor.",
                "disclaimer": "Not medical advice.",
            }
        }
    )
    assert "Restricted Medicines Check" in html
    assert "Tramadol" in html


def test_compare_bill_includes_restricted_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    sample_csv = Path(__file__).resolve().parent.parent / "data" / "medicines" / "restricted_medicines.csv"
    monkeypatch.setattr(
        "app.restricted_medicines._store",
        RestrictedMedicinesStore(sample_csv),
    )

    test_client = TestClient(app)
    response = test_client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Tramadol 50 mg",
                    "quantity": 1,
                    "unit_price": 100,
                    "total_price": 100,
                    "category": "medicine",
                }
            ],
            "city": "Delhi",
            "state_ut_name": "Delhi",
            "ocr_text": "Tramadol 50 mg tablet",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "restricted_medicine_flags" in payload
    assert payload["restricted_medicine_flags"]["detected"] is True
