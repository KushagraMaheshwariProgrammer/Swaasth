"""Tests for STG PDF parsing."""

from __future__ import annotations

import fitz

from app.services.stg_parser import extract_toc_from_pages


def test_extract_toc_includes_common_conditions() -> None:
    pages = [
        "Contents\n1. Common Diseases\nAcute Fever\n1\nMalaria\n58\nDengue\n64\n",
        "2. Emergencies\nCardiopulmonary Resuscitation (CPR)\n86\n",
    ]
    toc = extract_toc_from_pages(pages)
    names = {entry.condition for entry in toc}
    assert "Acute Fever" in names
    assert "Malaria" in names
    assert "Dengue" in names


def test_extract_toc_handles_inline_page_numbers() -> None:
    pages = ["Contents\nRickettsial Diseases (Scrub Typhus)\t474\n"]
    toc = extract_toc_from_pages(pages)
    assert any(entry.condition.startswith("Rickettsial Diseases") for entry in toc)


def test_extract_toc_from_real_pdf_if_available() -> None:
    from pathlib import Path

    pdf_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "Standard Treatment Guidelines"
        / "STG.pdf"
    )
    if not pdf_path.exists():
        return

    doc = fitz.open(str(pdf_path))
    pages = [doc[index].get_text() for index in range(min(120, doc.page_count))]
    doc.close()
    toc = extract_toc_from_pages(pages)
    names = {entry.condition.lower() for entry in toc}
    assert "malaria" in names
    assert len(toc) > 100
