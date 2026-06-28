"""Tests for ICMR document curation."""

from __future__ import annotations

from pathlib import Path

from app.services.icmr_corpus_curator import (
    extract_clinical_title_from_text,
    normalize_document_title,
    should_exclude_document,
    strip_filename_artifacts,
)

CURATOR = Path(__file__).resolve().parents[1] / "data" / "icmr_document_curator.json"

BUCCAL_MUCOSA_COVER = """
Indian Council of Medical Research
(Department of Health Research)
Ansari Nagar, New Delhi – 110029
2014
CONSENSUS DOCUMENT FOR
MANAGEMENT
OF BUCCAL MUCOSA CANCER
Prepared as an outcome of ICMR Subcommittee
on Buccal Mucosa Cancer
"""


def test_should_exclude_biosafety_document() -> None:
    assert should_exclude_document(
        "1736402847 biosaftylevel3 ver3 101020243",
        "1736402847 biosaftylevel3 ver3 101020243.pdf",
        curator_path=CURATOR,
    )


def test_should_keep_clinical_document() -> None:
    assert not should_exclude_document("HYPERTENSION", "HYPERTENSION.pdf", curator_path=CURATOR)


def test_normalize_document_title_applies_alias() -> None:
    assert normalize_document_title(
        "ICMR GuidelinesType2diabetes2018 0",
        curator_path=CURATOR,
    ) == "Type 2 Diabetes Mellitus"


def test_extract_clinical_title_from_buccal_mucosa_cover() -> None:
    assert extract_clinical_title_from_text(BUCCAL_MUCOSA_COVER) == "Buccal Mucosa Cancer"


def test_strip_filename_artifacts_removes_pdf_metadata() -> None:
    assert strip_filename_artifacts("Gastric Cancer Final pdf for farrow 0") == "Gastric Cancer"
    assert strip_filename_artifacts("SARCOMA AND OSTEOSARCOMA final pdf 0") == "SARCOMA AND OSTEOSARCOMA"
    assert strip_filename_artifacts("Esophagus final ICMR2014 0") == "Esophagus"


def test_normalize_document_title_prefers_cover_text() -> None:
    assert normalize_document_title(
        "Buccal Mucosa Cancer final pdf 9.6.14",
        cover_text=BUCCAL_MUCOSA_COVER,
        curator_path=CURATOR,
    ) == "Buccal Mucosa Cancer"

