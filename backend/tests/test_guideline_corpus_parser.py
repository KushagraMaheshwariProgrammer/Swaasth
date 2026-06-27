"""Tests for primary guideline corpus parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.guideline_corpus_parser import (
    CEA_DIR,
    GuidelineChunk,
    build_chunks_from_file,
    build_primary_guideline_corpus,
)


def test_build_chunks_from_clinical_establishments_pdf() -> None:
    files = sorted(CEA_DIR.glob("*.pdf"))
    if not files:
        pytest.skip("Clinical Establishments Act STG PDFs are not available")
    chunks = build_chunks_from_file(
        files[0],
        corpus="clinical_establishments",
        use_ocr_fallback=False,
    )
    assert chunks
    assert chunks[0].corpus == "clinical_establishments"
    assert chunks[0].source_file == files[0].name


def test_build_primary_guideline_corpus_combines_icmr_and_cea(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.guideline_corpus_parser.build_chunks_from_directory",
        lambda directory, corpus, use_ocr_fallback=True, max_files=None: [
            type(
                "Chunk",
                (),
                {
                    "chunk_id": f"{corpus}-sample-0001",
                    "condition": "Sample",
                    "corpus": corpus,
                    "document": "Sample",
                    "source_file": "sample.pdf",
                    "chapter": corpus,
                    "section_type": "general",
                    "page_start": 1,
                    "page_end": 1,
                    "text": "Sample text " * 40,
                    "to_stg_chunk": lambda self=None: None,
                },
            )()
        ],
    )
    monkeypatch.setattr(
        "app.services.guideline_corpus_parser.load_legacy_icmr_chunks",
        lambda: [
            GuidelineChunk(
                chunk_id="icmr-test-0001",
                condition="Malaria",
                corpus="icmr",
                document="Malaria",
                source_file="malaria.pdf",
                chapter="ICMR",
                section_type="general",
                page_start=1,
                page_end=1,
                text="Sample malaria guidance text " * 40,
            )
        ],
    )

    documents, chunks = build_primary_guideline_corpus(reuse_icmr_manifest=True)
    assert documents
    assert chunks
    corpora = {chunk.corpus for chunk in chunks}
    assert "icmr" in corpora
    assert "clinical_establishments" in corpora
