"""Tests for clinical history relevance filtering."""

from __future__ import annotations

from unittest.mock import patch

from app.services.clinical_history_relevance import filter_relevant_clinical_history


def _history_with_profile(*, conditions=None, surgeries=None, allergies=None):
    return {
        "profile": {
            "conditions": conditions or [],
            "surgeries": surgeries or [],
            "allergies": allergies or [],
        },
        "prior_reports": [],
        "legacy_documents": [],
    }


def test_knee_surgery_excluded_for_headache() -> None:
    history = _history_with_profile(
        surgeries=[{"name": "Knee arthroscopy", "year": 2019}],
    )
    result = filter_relevant_clinical_history(
        "Tension headache",
        ["headache"],
        [],
        history,
    )
    assert result["excluded_count"] >= 1
    assert any("knee" in item["label"].lower() for item in result["excluded"])
    assert not result["profile"]["surgeries"]


def test_diabetes_included_for_bacterial_infection() -> None:
    history = _history_with_profile(
        conditions=[{"name": "Type 2 diabetes", "status": "active"}],
    )
    result = filter_relevant_clinical_history(
        "Bacterial skin infection",
        ["fever"],
        [],
        history,
    )
    assert result["included_count"] >= 1
    assert result["profile"]["conditions"]
    assert any("diabetes" in item["label"].lower() for item in result["included"])


def test_prior_malaria_included_for_fever_workup() -> None:
    history = {
        "profile": {"conditions": [], "surgeries": [], "allergies": []},
        "prior_reports": [
            {
                "date": "2024-01-10",
                "diagnosis": "Malaria",
                "symptoms": [{"name": "fever"}],
                "test_results": [],
                "medicines": ["Artemether"],
                "source": "saved_report",
            }
        ],
        "legacy_documents": [],
    }
    result = filter_relevant_clinical_history(
        "Fever of unknown origin",
        ["fever", "chills"],
        [],
        history,
    )
    assert result["prior_reports"]
    assert any("malaria" in item["label"].lower() for item in result["included"])


def test_relevance_cache_avoids_duplicate_work() -> None:
    history = _history_with_profile(
        conditions=[{"name": "Hypertension", "status": "active"}],
    )
    cache: dict[str, dict] = {}
    first = filter_relevant_clinical_history(
        "Hypertension follow-up",
        [],
        [],
        history,
        _cache=cache,
    )
    second = filter_relevant_clinical_history(
        "Hypertension follow-up",
        [],
        [],
        history,
        _cache=cache,
    )
    assert first == second
    assert len(cache) == 1


def test_groq_classifier_can_exclude_items() -> None:
    history = _history_with_profile(
        surgeries=[{"name": "Knee arthroscopy", "year": 2018}],
    )
    groq_response = {
        "included": [],
        "excluded": [
            {
                "category": "surgery",
                "label": "Knee arthroscopy",
                "relevance_reason": "Orthopaedic history unrelated to headache",
            }
        ],
    }
    with patch(
        "app.services.clinical_history_relevance.groq_json_chat",
        return_value=groq_response,
    ):
        result = filter_relevant_clinical_history(
            "Migraine",
            ["headache"],
            [],
            history,
        )
    assert result["excluded_count"] == 1
    assert result["excluded"][0]["relevance_reason"] == (
        "Orthopaedic history unrelated to headache"
    )
