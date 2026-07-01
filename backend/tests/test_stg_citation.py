"""Tests for STG citation payloads."""

from __future__ import annotations

from app.services.rag_pipeline import validate_stg_citations
from app.services.stg_citation import build_stg_citation_from_chunk, resolve_source_metadata


def test_build_stg_citation_from_icmr_chunk() -> None:
    chunk = {
        "chunk_id": "icmr-1",
        "text": "Malaria rapid diagnostic test should be done before starting treatment.",
        "corpus": "icmr",
        "corpus_label": "ICMR",
        "condition": "Malaria",
        "section_type": "diagnosis",
        "page_start": 12,
        "page_end": 12,
        "source_file": "ICMR/Malaria.pdf",
    }
    citation = build_stg_citation_from_chunk(chunk)
    assert "Malaria rapid diagnostic" in citation["full_text"]
    assert citation["source"]["corpus_label"] == "ICMR"
    assert citation["source"]["authority"].startswith("Indian Council")


def test_validate_stg_citations_attaches_stg_citation() -> None:
    chunk = {
        "chunk_id": "cea-1",
        "text": "Ultrasound is not routinely required for uncomplicated urinary tract infection.",
        "corpus": "clinical_establishments",
        "corpus_label": "Clinical Establishments Act STG",
        "condition": "Urinary tract infection",
        "section_type": "investigations",
        "page_start": 4,
        "page_end": 4,
    }
    flags = [
        {
            "type": "EXCESSIVE_WORKUP",
            "item": "CT KUB",
            "stg_reference": {
                "condition": "Urinary tract infection",
                "section": "investigations",
                "page": 4,
            },
            "reason": "Imaging may not be routinely indicated.",
            "recommendation": "Ask whether imaging is necessary.",
        }
    ]
    validated = validate_stg_citations(flags, [chunk])
    assert validated[0]["citation_verified"] is True
    assert validated[0]["stg_citation"]["full_text"]
    assert (
        resolve_source_metadata(chunk)["corpus_label"]
        == "Clinical Establishments Act STG"
    )
