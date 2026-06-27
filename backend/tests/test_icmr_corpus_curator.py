"""Tests for ICMR document curation."""

from __future__ import annotations

from pathlib import Path

from app.services.icmr_corpus_curator import (
    normalize_document_title,
    should_exclude_document,
)

CURATOR = Path(__file__).resolve().parents[1] / "data" / "icmr_document_curator.json"


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
