"""Tests for prescription rationality checks."""

from __future__ import annotations

from app.services.prescription_rationality import analyze_prescription_rationality


def test_duplicate_therapeutic_class_flags_two_ppis() -> None:
    flags = analyze_prescription_rationality(
        diagnosis="Gastritis",
        prescription_items=[
            {"name": "Omeprazole 20mg", "category": "medicine"},
            {"name": "Pantoprazole 40mg", "category": "medicine"},
        ],
    )
    types = {flag["type"] for flag in flags}
    assert "DUPLICATE_THERAPEUTIC_CLASS" in types


def test_broader_spectrum_antibiotic_for_dengue() -> None:
    flags = analyze_prescription_rationality(
        diagnosis="Dengue",
        prescription_items=[{"name": "Azithromycin 500mg", "category": "medicine"}],
    )
    types = {flag["type"] for flag in flags}
    assert "BROADER_SPECTRUM_ANTIBIOTIC" in types


def test_drug_interaction_pair() -> None:
    flags = analyze_prescription_rationality(
        diagnosis="Hypertension",
        prescription_items=[
            {"name": "Warfarin", "category": "medicine"},
            {"name": "Aspirin", "category": "medicine"},
        ],
    )
    types = {flag["type"] for flag in flags}
    assert "DRUG_INTERACTION" in types


def test_pediatric_fluoroquinolone_caution() -> None:
    flags = analyze_prescription_rationality(
        diagnosis="UTI",
        prescription_items=[{"name": "Ciprofloxacin", "category": "medicine"}],
        patient_age=10,
        patient_gender="male",
    )
    types = {flag["type"] for flag in flags}
    assert "PEDIATRIC_DOSING_CAUTION" in types


def test_pregnancy_contraindication_for_doxycycline() -> None:
    flags = analyze_prescription_rationality(
        diagnosis="Acne",
        prescription_items=[{"name": "Doxycycline", "category": "medicine"}],
        patient_age=28,
        patient_gender="female",
    )
    types = {flag["type"] for flag in flags}
    assert "PREGNANCY_CONTRAINDICATION" in types


def test_no_accusatory_language_in_recommendations() -> None:
    flags = analyze_prescription_rationality(
        diagnosis="Dengue",
        prescription_items=[
            {"name": "Azithromycin", "category": "medicine"},
            {"name": "Omeprazole", "category": "medicine"},
            {"name": "Pantoprazole", "category": "medicine"},
        ],
    )
    blob = " ".join(
        str(flag.get("recommendation") or "") + " " + str(flag.get("reason") or "")
        for flag in flags
    ).lower()
    assert "wrong" not in blob
    assert "fraud" not in blob
    assert "unnecessary" not in blob
