"""Tests for tiered primary/fallback guideline retrieval."""

from __future__ import annotations

from pathlib import Path

from app.services.guideline_corpus_parser import (
    GuidelineChunk,
    _title_from_filename,
    build_chunks_from_file,
    load_legacy_icmr_chunks,
)
from app.services.stg_retrieval import (
    _build_semantic_query,
    _primary_is_sufficient,
    retrieve_stg_context,
)


def test_title_from_filename_normalizes_underscores() -> None:
    assert _title_from_filename("HYPERTENSION.pdf") == "HYPERTENSION"
    assert "Diabetes" in _title_from_filename("ICMR_Guidelines_for_Management_of_Type_1_Diabetes.pdf")


def test_load_legacy_icmr_chunks_has_entries(monkeypatch) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "icmr_index" / "chunks_manifest.json"
    monkeypatch.setattr(
        "app.services.guideline_corpus_parser.LEGACY_ICMR_MANIFEST",
        fixture,
    )
    chunks = load_legacy_icmr_chunks()
    assert chunks
    assert chunks[0].corpus == "icmr"


def test_build_semantic_query_includes_symptoms_and_tests() -> None:
    query = _build_semantic_query(
        "Malaria",
        ["Chloroquine"],
        symptoms=[{"name": "fever"}],
        test_results=[{"test_name": "Malaria RDT", "result": "negative"}],
    )
    assert "fever" in query.lower()
    assert "malaria rdt" in query.lower()


def test_primary_is_sufficient_requires_enough_text() -> None:
    assert not _primary_is_sufficient([])
    assert not _primary_is_sufficient([{"text": "short", "distance": 0.2}])
    assert _primary_is_sufficient(
        [{"text": "x" * 1600, "distance": 0.3}],
    )


def test_retrieve_stg_context_uses_primary_without_fallback(monkeypatch) -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "stg_index"
    manifest = fixture_dir / "chunks_manifest.json"
    import json

    primary_chunks = json.loads(manifest.read_text(encoding="utf-8"))[:3]
    for chunk in primary_chunks:
        chunk["corpus_label"] = "ICMR"
        chunk["guideline_tier"] = "primary"
        chunk["text"] = ("Salient features and diagnostic criteria. " * 80)[:2000]

    class PrimaryStore:
        is_ready = True

        def condition_names(self):
            return ["Malaria"]

        def get_chunks_for_conditions(self, conditions, limit_per_condition=12):
            return primary_chunks

        def semantic_search(self, query, top_k=10, condition_filter=None, corpus_filter=None):
            return primary_chunks

        def keyword_search(self, query, top_k=30):
            return primary_chunks

        def embed_texts(self, texts):
            return [[1.0] * 8 for _ in texts]

    class EmptyFallbackStore:
        is_ready = False

        def condition_names(self):
            return []

    monkeypatch.setattr(
        "app.services.stg_retrieval.get_primary_guidelines_store",
        lambda: PrimaryStore(),
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.get_stg_index_store",
        lambda: EmptyFallbackStore(),
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.map_diagnosis_to_primary_documents",
        lambda diagnosis, limit=4: ["Malaria"],
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.rerank_chunks",
        lambda query, chunks, top_k=12: chunks[:top_k],
    )

    result = retrieve_stg_context(
        "Malaria",
        ["Chloroquine"],
        symptoms=[{"name": "fever"}],
        test_results=[{"test_name": "Malaria RDT", "result": "negative"}],
    )
    assert result["primary_chunk_count"] > 0
    assert result["fallback_chunk_count"] == 0
    assert result["used_fallback"] is False
    assert "ICMR" in result["guideline_sources"]


def test_retrieve_stg_context_falls_back_when_primary_insufficient(monkeypatch) -> None:
    class WeakPrimaryStore:
        is_ready = True

        def condition_names(self):
            return ["Malaria"]

        def get_chunks_for_conditions(self, conditions, limit_per_condition=12):
            return []

        def semantic_search(self, query, top_k=10, condition_filter=None, corpus_filter=None):
            return [{"chunk_id": "p1", "text": "tiny", "distance": 0.95, "corpus_label": "ICMR"}]

        def keyword_search(self, query, top_k=30):
            return []

        def embed_texts(self, texts):
            return [[1.0] * 8 for _ in texts]

    class FallbackStore:
        is_ready = True

        def condition_names(self):
            return ["Malaria"]

        def get_chunks_for_conditions(self, conditions, limit_per_condition=16):
            fixture = Path(__file__).resolve().parent / "fixtures" / "stg_index" / "chunks_manifest.json"
            import json

            chunks = json.loads(fixture.read_text(encoding="utf-8"))[:2]
            for chunk in chunks:
                chunk["source"] = "toc"
            return chunks

        def semantic_search(self, query, top_k=10, condition_filter=None):
            return []

        def keyword_search(self, query, top_k=30):
            return []

    monkeypatch.setattr(
        "app.services.stg_retrieval.get_primary_guidelines_store",
        lambda: WeakPrimaryStore(),
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.get_stg_index_store",
        lambda: FallbackStore(),
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.map_diagnosis_to_primary_documents",
        lambda diagnosis, limit=4: [],
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.map_diagnosis_to_stg_conditions",
        lambda diagnosis, limit=3: ["Malaria"],
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.rerank_chunks",
        lambda query, chunks, top_k=12: chunks[:top_k],
    )

    result = retrieve_stg_context("Malaria", ["Chloroquine"])
    assert result["used_fallback"] is True
    assert result["fallback_chunk_count"] > 0
    assert "CRC STG" in result["guideline_sources"]
