"""Tests for primary guideline corpus parsing."""

from __future__ import annotations

from pathlib import Path

from app.services.guideline_corpus_parser import (
    CEA_DIR,
    build_chunks_from_file,
    build_primary_guideline_corpus,
    load_legacy_icmr_chunks,
)


def test_build_chunks_from_clinical_establishments_pdf() -> None:
    files = sorted(CEA_DIR.glob("*.pdf"))
    assert files
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
        lambda: load_legacy_icmr_chunks()[:1],
    )

    documents, chunks = build_primary_guideline_corpus(reuse_icmr_manifest=True)
    assert documents
    assert chunks
    corpora = {chunk.corpus for chunk in chunks}
    assert "icmr" in corpora
    assert "clinical_establishments" in corpora
