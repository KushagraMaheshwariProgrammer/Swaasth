"""Tests for symptom-enriched STG retrieval."""

from __future__ import annotations

from pathlib import Path

from app.services.stg_retrieval import retrieve_stg_context


class FakeStore:
    def __init__(self) -> None:
        fixture_dir = Path(__file__).resolve().parent / "fixtures" / "stg_index"
        manifest = fixture_dir / "chunks_manifest.json"
        import json

        self._chunks = json.loads(manifest.read_text(encoding="utf-8"))
        self.is_ready = True
        self._queries: list[str] = []

    def get_chunks_for_conditions(self, conditions: list[str], limit_per_condition: int = 16):
        selected = []
        for chunk in self._chunks:
            if chunk["condition"] in conditions:
                selected.append(chunk)
        return selected[: limit_per_condition * max(len(conditions), 1)]

    def semantic_search(self, query: str, top_k: int = 10, condition_filter=None):
        self._queries.append(query)
        return self._chunks[:top_k]


def test_retrieve_stg_context_includes_symptoms_in_semantic_query(monkeypatch) -> None:
    store = FakeStore()

    monkeypatch.setattr(
        "app.services.stg_retrieval.get_stg_index_store",
        lambda: store,
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.map_diagnosis_to_stg_conditions",
        lambda diagnosis, limit=3: ["Malaria"],
    )

    result = retrieve_stg_context(
        "Malaria",
        ["Chloroquine"],
        symptoms=[{"name": "fever"}, {"name": "chills"}],
        test_results=[{"test_name": "Malaria RDT", "result": "negative"}],
    )

    assert result["matched_conditions"] == ["Malaria"]
    assert store._queries
    assert "fever" in store._queries[0].lower()
    assert "malaria rdt" in store._queries[0].lower()
    assert "negative" in store._queries[0].lower()
    assert any("Salient features" in chunk.get("section_type", "") for chunk in result["chunks"])
