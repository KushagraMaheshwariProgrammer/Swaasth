"""Tests for patient-advocacy helpers."""

from __future__ import annotations

from app.services.audit_advocacy import (
    assign_confidence,
    build_patient_questions,
    finalize_audit_flags,
    flag_display_label,
)
from app.services.claim_audit import analyze_claim_items


def test_flag_display_label_neutral_wording() -> None:
    assert flag_display_label("UNNECESSARY_TEST") == "Not routinely recommended"
    assert flag_display_label("GUIDELINE_SUPPORT_NOT_IDENTIFIED") == (
        "Guideline support not identified"
    )


def test_assign_confidence_low_for_insufficient_types() -> None:
    flag = {"type": "INSUFFICIENT_STG_EVIDENCE", "severity": "MEDIUM"}
    assert assign_confidence(flag) == "LOW"


def test_assign_confidence_medium_for_billing_heuristic() -> None:
    flag = {"type": "DUPLICATE_ITEM", "severity": "HIGH"}
    assert assign_confidence(flag) == "MEDIUM"


def test_build_patient_questions_deduplicates() -> None:
    flags = [
        {
            "type": "DUPLICATE_ITEM",
            "item": "CBC",
            "confidence": "MEDIUM",
            "recommendation": "Ask hospital for justification or supporting prescription.",
        },
        {
            "type": "LAB_REPETITION",
            "item": "CBC",
            "confidence": "MEDIUM",
            "recommendation": "Ask hospital for justification or supporting prescription.",
        },
    ]
    questions = build_patient_questions(flags)
    assert len(questions) == 1
    assert "?" in questions[0]["question"]


def test_finalize_audit_flags_adds_display_label_and_confidence() -> None:
    flags = [{"type": "UNNECESSARY_TEST", "severity": "HIGH", "item": "MRI"}]
    finalized = finalize_audit_flags(flags, chunks=[])
    assert finalized[0]["display_label"] == "Not routinely recommended"
    assert finalized[0]["confidence"] in {"LOW", "MEDIUM", "HIGH"}


def test_claim_audit_returns_patient_questions() -> None:
    result = analyze_claim_items(
        [
            {"item_name": "CBC", "quantity": 1},
            {"item_name": "CBC", "quantity": 1},
        ]
    )
    assert result["patient_questions"]
    assert result["advocacy_scope"]["checked"]
    assert "fraud" not in str(result).lower()
