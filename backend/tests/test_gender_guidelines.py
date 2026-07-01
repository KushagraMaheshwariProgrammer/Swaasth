"""Tests for gender-aware STG retrieval rules."""

from __future__ import annotations

from app.services.gender_guidelines import (
    chunk_applies_to_gender,
    condition_applies_to_gender,
    filter_chunks_by_gender,
    filter_conditions_by_gender,
    infer_gender_applicability,
)
from app.services.patient_gender import resolve_patient_gender
from app.services.stg_retrieval import _build_semantic_query


def test_resolve_patient_gender_normalizes_values() -> None:
    assert resolve_patient_gender("male") == "male"
    assert resolve_patient_gender("Female") == "female"
    assert resolve_patient_gender("prefer_not_to_say") is None
    assert resolve_patient_gender("other") is None


def test_infer_gender_applicability_for_obstetric_topics() -> None:
    assert infer_gender_applicability("Hypertensive Disorders of Pregnancy") == frozenset(
        {"female"}
    )
    assert infer_gender_applicability("Prostate Cancer") == frozenset({"male"})
    assert infer_gender_applicability("Cervical Spondylosis") is None
    assert infer_gender_applicability("Hypertension") is None


def test_filter_conditions_by_gender() -> None:
    conditions = [
        "Hypertension",
        "Prostate Cancer",
        "Vaginal Discharge",
        "Cervical Spondylosis",
    ]
    male_filtered = filter_conditions_by_gender(conditions, "male")
    assert "Prostate Cancer" in male_filtered
    assert "Vaginal Discharge" not in male_filtered
    assert "Hypertension" in male_filtered
    assert "Cervical Spondylosis" in male_filtered

    female_filtered = filter_conditions_by_gender(conditions, "female")
    assert "Vaginal Discharge" in female_filtered
    assert "Prostate Cancer" not in female_filtered


def test_chunk_filtering_removes_opposite_sex_sections() -> None:
    pregnancy_chunk = {
        "condition": "Hypertension",
        "chapter": "Cardiovascular Diseases",
        "text": "Hypertension in pregnancy: ACEI and ARBs are contraindicated.",
    }
    general_chunk = {
        "condition": "Hypertension",
        "chapter": "Cardiovascular Diseases",
        "text": "Lifestyle modification and first-line antihypertensive therapy.",
    }
    prostate_chunk = {
        "condition": "Hypertension",
        "chapter": "Cardiovascular Diseases",
        "text": "Screening for prostate cancer is not part of hypertension workup.",
    }

    assert chunk_applies_to_gender(pregnancy_chunk, "female")
    assert not chunk_applies_to_gender(pregnancy_chunk, "male")
    assert chunk_applies_to_gender(general_chunk, "male")
    assert not chunk_applies_to_gender(prostate_chunk, "female")

    filtered = filter_chunks_by_gender(
        [pregnancy_chunk, general_chunk, prostate_chunk],
        "male",
    )
    assert general_chunk in filtered
    assert prostate_chunk in filtered
    assert pregnancy_chunk not in filtered


def test_condition_applies_to_gender_respects_neutral_override() -> None:
    assert condition_applies_to_gender(
        "Cervical Spondylosis",
        patient_gender="male",
    )
    assert not condition_applies_to_gender(
        "Cervical Cancer",
        patient_gender="male",
    )


def test_build_semantic_query_includes_patient_gender() -> None:
    query = _build_semantic_query(
        "Hypertension",
        ["Amlodipine"],
        patient_gender="female",
    )
    assert "Patient sex: female" in query


def test_build_semantic_query_omits_gender_when_missing() -> None:
    query = _build_semantic_query("Hypertension", ["Amlodipine"])
    assert "Patient sex" not in query
