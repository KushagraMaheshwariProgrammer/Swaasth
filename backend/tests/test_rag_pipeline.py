"""Unit tests for shared RAG pipeline utilities."""

from __future__ import annotations

from app.services.rag_pipeline import (
    Bm25Index,
    build_context_text,
    prefilter_titles_by_embedding,
    reciprocal_rank_fusion,
    validate_stg_citations,
)


def test_reciprocal_rank_fusion_prefers_chunks_in_multiple_lists() -> None:
    list_a = [{"chunk_id": "a", "text": "alpha", "source": "toc"}]
    list_b = [{"chunk_id": "a", "text": "alpha", "source": "semantic"}, {"chunk_id": "b", "text": "beta", "source": "semantic"}]
    merged = reciprocal_rank_fusion([list_a, list_b])
    assert merged[0]["chunk_id"] == "a"
    assert "toc" in merged[0]["retrieval_sources"]
    assert "semantic" in merged[0]["retrieval_sources"]


def test_bm25_finds_acronym_terms(tmp_path) -> None:
    manifest = tmp_path / "chunks_manifest.json"
    manifest.write_text(
        """
[
  {"chunk_id": "c1", "condition": "Malaria", "text": "Malaria RDT rapid diagnostic test for plasmodium parasite detection.", "section_type": "diagnosis", "page_start": 1, "page_end": 1},
  {"chunk_id": "c2", "condition": "Hypertension", "text": "Blood pressure management and lifestyle advice for hypertension.", "section_type": "treatment", "page_start": 2, "page_end": 2}
]
""".strip(),
        encoding="utf-8",
    )
    index = Bm25Index(manifest)
    results = index.search("Malaria RDT", top_k=2)
    assert results
    assert results[0]["chunk_id"] == "c1"


def test_validate_stg_citations_strips_ungrounded_reference() -> None:
    chunks = [
        {
            "condition": "Malaria",
            "document": "Malaria",
            "section_type": "diagnosis",
            "page_start": 10,
            "page_end": 12,
            "text": "Diagnostic criteria for malaria.",
        }
    ]
    flags = [
        {
            "type": "UNNECESSARY_TEST",
            "reason": "Test not indicated.",
            "stg_reference": {
                "condition": "Fake Condition",
                "section": "diagnosis",
                "page": 10,
            },
        }
    ]
    validated = validate_stg_citations(flags, chunks)
    assert validated[0]["stg_reference"] is None
    assert "could not be verified" in validated[0]["reason"].lower()


def test_validate_stg_citations_keeps_grounded_reference() -> None:
    chunks = [
        {
            "condition": "HYPERTENSION",
            "document": "HYPERTENSION",
            "section_type": "investigations",
            "page_start": 5,
            "page_end": 6,
            "text": "Routine investigations for hypertension.",
        }
    ]
    flags = [
        {
            "type": "UNNECESSARY_TEST",
            "reason": "MRI not indicated.",
            "stg_reference": {
                "condition": "HYPERTENSION",
                "section": "investigations",
                "page": 5,
            },
        }
    ]
    validated = validate_stg_citations(flags, chunks)
    assert validated[0]["stg_reference"]["condition"] == "HYPERTENSION"


def test_build_context_text_respects_char_budget() -> None:
    chunks = [{"condition": "A", "section_type": "general", "page_start": 1, "page_end": 1, "text": "x" * 5000} for _ in range(5)]
    text = build_context_text(chunks, max_chars=8000)
    assert len(text) <= 8000


def test_prefilter_titles_by_embedding_returns_subset() -> None:
    titles = ["Malaria", "Hypertension", "Dental caries", "Burn Injuries"]
    filtered = prefilter_titles_by_embedding(
        "fever and chills from plasmodium",
        titles,
        top_k=2,
        embed_fn=lambda texts: [[float(i) for i in range(8)] for _ in texts],
    )
    assert len(filtered) == 2
