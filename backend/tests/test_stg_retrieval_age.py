"""Tests for STG retrieval age context."""

from __future__ import annotations

from app.services.stg_retrieval import _build_semantic_query


def test_build_semantic_query_includes_patient_age() -> None:
    query = _build_semantic_query(
        "Pneumonia",
        ["Amoxicillin"],
        patient_age=8,
    )
    assert "Patient age (approximate): 8 years" in query


def test_build_semantic_query_omits_age_when_missing() -> None:
    query = _build_semantic_query("Pneumonia", ["Amoxicillin"])
    assert "Patient age" not in query


def test_build_semantic_query_includes_patient_gender() -> None:
    query = _build_semantic_query(
        "Pneumonia",
        ["Amoxicillin"],
        patient_gender="male",
    )
    assert "Patient sex: male" in query
