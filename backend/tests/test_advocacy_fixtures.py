"""Realistic advocacy regression fixtures."""

from __future__ import annotations

from app.services.audit_advocacy import build_patient_questions, finalize_audit_flags
from app.services.claim_audit import analyze_claim_items
from app.services.investigation_audit import analyze_investigations
from app.services.prescription_rationality import analyze_prescription_rationality
from app.services.treatment_audit import _rule_based_clinical_flags

BANNED_PHRASES = ("fraud", "unnecessary", "wrong prescription", "doctor was wrong")


def _assert_no_banned_phrases(text: str) -> None:
    lowered = text.lower()
    for phrase in BANNED_PHRASES:
        assert phrase not in lowered, f"Banned phrase found: {phrase}"


def test_dengue_antibiotics_repeat_cbc_questions() -> None:
    clinical_flags = _rule_based_clinical_flags(
        "Dengue",
        {
            "symptoms": [{"name": "fever"}],
            "test_results": [{"test_name": "Dengue NS1", "result": "positive"}],
        },
        prescription_items=[{"name": "Azithromycin 500mg"}],
    )
    rx_flags = analyze_prescription_rationality(
        diagnosis="Dengue",
        prescription_items=[{"name": "Azithromycin 500mg", "category": "medicine"}],
    )
    inv_flags = analyze_investigations(
        diagnosis="Dengue",
        investigation_items=["CBC", "CBC"],
        retrieval_chunks=[],
        flagged_item_norms=set(),
    )
    bill_flags = analyze_claim_items(
        [{"item_name": "CBC", "quantity": 1}, {"item_name": "CBC", "quantity": 1}]
    )
    questions = build_patient_questions(
        finalize_audit_flags(clinical_flags + rx_flags + inv_flags + bill_flags["flags"])
    )
    assert questions
    for question in questions:
        _assert_no_banned_phrases(question["question"])
        assert question["confidence"] in {"HIGH", "MEDIUM", "LOW"}


def test_viral_urti_azithromycin_broader_spectrum() -> None:
    flags = analyze_prescription_rationality(
        diagnosis="Viral URTI",
        prescription_items=[{"name": "Azithromycin", "category": "medicine"}],
    )
    finalized = finalize_audit_flags(flags)
    assert any(flag["type"] == "BROADER_SPECTRUM_ANTIBIOTIC" for flag in finalized)
    questions = build_patient_questions(finalized)
    assert questions
    _assert_no_banned_phrases(" ".join(q["question"] for q in questions))


def test_typhoid_negative_widal_mismatch() -> None:
    flags = _rule_based_clinical_flags(
        "Typhoid",
        {"test_results": [{"test_name": "Widal test", "result": "negative"}]},
    )
    assert flags
    assert flags[0]["type"] == "DIAGNOSIS_TEST_MISMATCH"
    questions = build_patient_questions(finalize_audit_flags(flags))
    assert questions[0]["confidence"] in {"LOW", "MEDIUM", "HIGH"}


def test_package_and_separate_ot_billing_question() -> None:
    result = analyze_claim_items(
        [
            {"item_name": "Hernia surgery package", "category": "procedure"},
            {"item_name": "OT charges", "category": "procedure"},
        ]
    )
    assert any(
        flag["type"] == "PACKAGE_COMPONENT_CHARGED_SEPARATELY"
        for flag in result["flags"]
    )
    assert result["patient_questions"]
    _assert_no_banned_phrases(result["patient_questions"][0]["question"])


def test_mri_guideline_silent_low_confidence() -> None:
    flags = analyze_investigations(
        diagnosis="Dengue",
        investigation_items=["MRI Brain"],
        retrieval_chunks=[],
    )
    finalized = finalize_audit_flags(flags)
    assert finalized[0]["type"] == "GUIDELINE_SUPPORT_NOT_IDENTIFIED"
    assert finalized[0]["confidence"] == "LOW"
    assert "not identified" in finalized[0]["reason"].lower()
