"""Tests for treatment audit helpers."""

from __future__ import annotations

from app.services.treatment_audit import (
    _compute_risk_level,
    _polish_flags_for_users,
    _polish_user_facing_text,
    _rule_based_bill_prescription_flags,
    _rule_based_clinical_flags,
    analyze_treatment,
)


def test_rule_based_bill_prescription_flags_detects_unprescribed_item() -> None:
    flags = _rule_based_bill_prescription_flags(
        bill_items=[{"item_name": "MRI Brain"}],
        prescription_items=[{"name": "CBC"}],
    )
    assert len(flags) == 1
    assert flags[0]["type"] == "BILLED_NOT_PRESCRIBED"


def test_compute_risk_level_high_for_multiple_flags() -> None:
    flags = [
        {"severity": "MEDIUM"},
        {"severity": "MEDIUM"},
        {"severity": "MEDIUM"},
    ]
    assert _compute_risk_level(flags) == "HIGH"


def test_rule_based_clinical_flags_malaria_negative_rdt() -> None:
    flags = _rule_based_clinical_flags(
        "Malaria",
        {
            "test_results": [
                {"test_name": "Malaria RDT", "result": "negative"},
            ]
        },
    )
    assert len(flags) == 1
    assert flags[0]["type"] == "DIAGNOSIS_TEST_MISMATCH"
    assert flags[0]["category"] == "diagnosis"


def test_polish_user_facing_text_rewrites_generic_stg_recommendation() -> None:
    polished = _polish_user_facing_text(
        "Review and revise prescription according to STG guidelines"
    )
    assert "STG" not in polished
    assert "doctor" in polished.lower()


def test_polish_flags_for_users_preserves_plain_guideline_basis() -> None:
    flags = [
        {
            "type": "NOT_INDICATED_MEDICINE",
            "item": "Amoxicillin",
            "reason": "Antibiotics are usually not needed for viral URTI.",
            "recommendation": "Ask your doctor whether antibiotics are needed.",
            "guideline_basis": (
                "Most throat infections are viral, so antibiotics are usually not needed."
            ),
        }
    ]
    polished = _polish_flags_for_users(flags, chunks=[])
    assert polished[0]["guideline_basis"] == (
        "Most throat infections are viral, so antibiotics are usually not needed."
    )


def test_polish_flags_for_users_adds_source_label_fallback() -> None:
    chunks = [
        {
            "corpus_label": "ICMR",
            "condition": "Treatment Guidelines 2019",
            "text": "Upper respiratory tract infections are usually viral.",
            "section_type": "treatment",
        }
    ]
    flags = [
        {
            "type": "NOT_INDICATED_MEDICINE",
            "item": "Amoxicillin",
            "reason": "Antibiotics are usually not needed for viral URTI.",
            "recommendation": "Ask your doctor whether antibiotics are needed.",
        }
    ]
    polished = _polish_flags_for_users(flags, chunks)
    assert polished[0]["guideline_basis"].startswith("Based on ICMR guidelines")


def test_analyze_treatment_requires_diagnosis(monkeypatch) -> None:
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        analyze_treatment(diagnosis="")
    assert exc.value.status_code == 400
