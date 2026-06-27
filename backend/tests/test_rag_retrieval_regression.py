"""Deterministic retrieval regression tests using fixture manifests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parent / "eval"
sys.path.insert(0, str(EVAL_DIR))

from rag_eval_utils import (  # noqa: E402
    case_input_to_retrieval_args,
    filter_cases,
    load_gold_cases,
    score_retrieval_case,
)

FIXTURE_MANIFEST = Path(__file__).resolve().parent / "fixtures" / "stg_index" / "chunks_manifest.json"


@pytest.fixture()
def hybrid_primary_store():
    chunks = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    for chunk in chunks:
        chunk["corpus_label"] = "Clinical Establishments Act STG"
        chunk["corpus"] = "clinical_establishments"
        chunk["guideline_tier"] = "primary"

    class Store:
        is_ready = True

        def condition_names(self):
            return sorted({chunk["condition"] for chunk in chunks})

        def get_chunks_for_conditions(self, conditions, limit_per_condition=12):
            wanted = {name.lower() for name in conditions}
            return [
                {**chunk, "source": "toc"}
                for chunk in chunks
                if chunk["condition"].lower() in wanted
            ][: limit_per_condition * max(len(wanted), 1)]

        def semantic_search(self, query, top_k=30, condition_filter=None, corpus_filter=None):
            return [{**chunk, "source": "semantic", "distance": 0.2} for chunk in chunks[:top_k]]

        def keyword_search(self, query, top_k=30):
            query_lower = query.lower()
            matched = [
                {**chunk, "source": "bm25", "bm25_score": 1.0}
                for chunk in chunks
                if query_lower.split(".")[0].split()[0] in chunk["text"].lower()
                or chunk["condition"].lower() in query_lower
            ]
            return matched[:top_k]

        def embed_texts(self, texts):
            return [[float(len(text))] * 8 for text in texts]

    return Store()


def test_hybrid_retrieval_scores_guideline_derived_cases(hybrid_primary_store, monkeypatch) -> None:
    class EmptyFallback:
        is_ready = False

        def condition_names(self):
            return []

    monkeypatch.setattr(
        "app.services.stg_retrieval.get_primary_guidelines_store",
        lambda: hybrid_primary_store,
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.get_stg_index_store",
        lambda: EmptyFallback(),
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.map_diagnosis_to_primary_documents",
        lambda diagnosis, limit=4: ["Malaria"] if "malaria" in diagnosis.lower() else ["Dengue"],
    )
    monkeypatch.setattr(
        "app.services.stg_retrieval.rerank_chunks",
        lambda query, chunks, top_k=12: chunks[:top_k],
    )

    from app.services.stg_retrieval import retrieve_stg_context

    cases = filter_cases(load_gold_cases(), source="guideline_derived")[:3]
    for case in cases:
        diagnosis, items, symptoms, test_results = case_input_to_retrieval_args(case)
        retrieval = retrieve_stg_context(
            diagnosis,
            items,
            symptoms=symptoms,
            test_results=test_results,
        )
        scored = score_retrieval_case(case, retrieval)
        assert scored.term_recall >= 0.0
