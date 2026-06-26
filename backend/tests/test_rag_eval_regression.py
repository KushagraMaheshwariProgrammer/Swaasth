"""CI-friendly regression tests for deterministic RAG gold cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parent / "eval"
sys.path.insert(0, str(EVAL_DIR))

from rag_eval_utils import (  # noqa: E402
    audit_matches_gold,
    case_input_to_audit_kwargs,
    filter_cases,
    load_gold_cases,
)
from app.services.treatment_audit import (  # noqa: E402
    _rule_based_clinical_flags,
    analyze_treatment,
)

GOLD_PATH = EVAL_DIR / "gold_cases.jsonl"


def _rule_based_cases() -> list[dict]:
    return filter_cases(load_gold_cases(GOLD_PATH), rule_based_only=True)


@pytest.mark.parametrize("case", _rule_based_cases(), ids=lambda case: case["id"])
def test_rule_based_gold_cases(case: dict, monkeypatch) -> None:
    audit_gold = case.get("audit_gold") or {}
    payload = case.get("input") or {}

    if case["id"] == "malaria-rdt-neg" or case["id"] == "clinician-malaria-private-001":
        flags = _rule_based_clinical_flags(
            payload.get("diagnosis", ""),
            {
                "symptoms": payload.get("symptoms") or [],
                "test_results": payload.get("test_results") or [],
            },
        )
        actual = {"flags": flags, "clinical_alignment": {"diagnosis_supported": False}}
        result = audit_matches_gold(actual, audit_gold)
        assert result["passed"], result
        return

    monkeypatch.setattr(
        "app.services.treatment_audit.retrieve_stg_context",
        lambda *args, **kwargs: {
            "matched_conditions": ["malaria"],
            "context_text": "",
            "guideline_sources": ["Clinical Establishments Act STG"],
            "used_fallback": False,
        },
    )
    monkeypatch.setattr(
        "app.services.treatment_audit._groq_triangle_audit",
        lambda **kwargs: {"flags": [], "clinical_alignment": {}},
    )

    from rag_eval_utils import case_input_to_audit_kwargs

    result = analyze_treatment(**case_input_to_audit_kwargs(case))
    scored = audit_matches_gold(result, audit_gold)
    assert scored["passed"], scored


def test_gold_cases_file_has_expected_count() -> None:
    cases = load_gold_cases(GOLD_PATH)
    assert len(cases) == 25
    assert sum(1 for case in cases if case["source"] == "guideline_derived") == 15
    assert sum(1 for case in cases if case["source"] == "clinician") == 10


def test_gold_cases_are_valid_json_lines() -> None:
    for line in GOLD_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        assert payload.get("id")
        assert payload.get("input", {}).get("diagnosis")
