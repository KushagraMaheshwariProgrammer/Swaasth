"""Unit tests for RAG evaluation scoring helpers."""

from __future__ import annotations

import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent / "eval"
sys.path.insert(0, str(EVAL_DIR))

from rag_eval_utils import (  # noqa: E402
    audit_matches_gold,
    corpus_hit,
    document_hit_at_k,
    term_recall,
)


def test_document_hit_at_k_matches_partial_titles() -> None:
    chunks = [
        {"condition": "malaria", "document": "malaria", "text": "fever"},
        {"condition": "Other", "document": "Other", "text": "x"},
    ]
    hit, mrr = document_hit_at_k(chunks, ["Malaria"], k=5)
    assert hit is True
    assert mrr == 1.0


def test_term_recall_counts_required_terms() -> None:
    assert term_recall("Malaria RDT negative smear", ["RDT", "negative", "xyz"]) == 2 / 3


def test_corpus_hit_accepts_clinical_establishments_label() -> None:
    assert corpus_hit(
        ["Clinical Establishments Act STG"],
        ["clinical_establishments"],
    )


def test_audit_matches_gold_detects_missing_expected_flag() -> None:
    result = audit_matches_gold(
        {"flags": [{"type": "UNNECESSARY_TEST"}], "clinical_alignment": {}},
        {"expected_flag_types": ["DIAGNOSIS_TEST_MISMATCH"], "forbidden_flag_types": []},
    )
    assert result["passed"] is False
    assert "DIAGNOSIS_TEST_MISMATCH" in result["expected_misses"]
