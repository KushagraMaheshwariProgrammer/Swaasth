"""Tests for lab interpretation flags."""

from __future__ import annotations

from app.services.lab_interpretation import analyze_lab_results


def test_analyze_lab_results_flags_high_numeric_value() -> None:
    flags = analyze_lab_results(
        [
            {
                "test_name": "Haemoglobin",
                "value": "16.5",
                "unit": "g/dL",
                "reference_range": "12 - 15",
                "result": "",
            }
        ]
    )
    assert len(flags) == 1
    assert flags[0]["type"] == "ABNORMAL_LAB_VALUE"
    assert flags[0]["lab_status"] == "high"


def test_analyze_lab_results_flags_qualitative_abnormal() -> None:
    flags = analyze_lab_results(
        [{"test_name": "Blood glucose", "value": "180", "result": "high"}]
    )
    assert len(flags) == 1
    assert flags[0]["type"] == "ABNORMAL_LAB_VALUE"


def test_analyze_lab_results_ignores_normal_results() -> None:
    flags = analyze_lab_results(
        [{"test_name": "CBC", "value": "12", "reference_range": "11-14", "result": "normal"}]
    )
    assert flags == []
