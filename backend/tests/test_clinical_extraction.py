"""Tests for clinical context normalization and extraction helpers."""

from __future__ import annotations

from app.services.document_extraction import (
    merge_clinical_contexts,
    normalize_clinical_context,
)


def test_normalize_clinical_context_dedupes_symptoms() -> None:
    ctx = normalize_clinical_context(
        symptoms=[
            {"name": "Fever", "duration": "3 days"},
            {"name": "fever", "duration": "4 days"},
            {"name": "  ", "duration": ""},
        ],
        test_results=[
            {
                "test_name": "Malaria RDT",
                "result": "negative",
                "value": None,
                "unit": None,
            }
        ],
    )
    assert len(ctx["symptoms"]) == 1
    assert ctx["symptoms"][0]["name"] == "Fever"
    assert ctx["test_results"][0]["test_name"] == "Malaria RDT"
    assert ctx["test_results"][0]["result"] == "negative"


def test_merge_clinical_contexts_manual_overrides_upload() -> None:
    merged = merge_clinical_contexts(
        normalize_clinical_context(
            symptoms=[{"name": "cough"}],
            test_results=[{"test_name": "CBC", "result": "normal"}],
            symptoms_source="lab_report",
            test_results_source="lab_report",
        ),
        manual_symptoms=[{"name": "fever", "duration": "2 days"}],
        manual_test_results=[{"test_name": "Malaria RDT", "result": "negative"}],
    )
    names = [item["name"] for item in merged["symptoms"]]
    assert names[0] == "fever"
    assert "cough" in names
    test_names = [item["test_name"] for item in merged["test_results"]]
    assert "Malaria RDT" in test_names
    assert merged["symptoms_source"] == "manual"
    assert merged["test_results_source"] == "manual"


def test_normalize_clinical_context_normalizes_test_result_labels() -> None:
    ctx = normalize_clinical_context(
        test_results=[
            {
                "test_name": "  Dengue NS1 ",
                "result": "POSITIVE",
                "value": " reactive ",
                "unit": "",
            }
        ]
    )
    assert ctx["test_results"][0]["test_name"] == "Dengue NS1"
    assert ctx["test_results"][0]["result"] == "positive"
    assert ctx["test_results"][0]["value"] == "reactive"
