"""Tests for repeat investigation detection."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.investigation_history_audit import analyze_repeat_investigations


def test_analyze_repeat_investigations_flags_recent_cbc() -> None:
    recent = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d")
    flags = analyze_repeat_investigations(
        prescription_items=[{"name": "CBC", "category": "test"}],
        filtered_history={
            "prior_reports": [
                {
                    "date": recent,
                    "test_results": [{"test_name": "Complete Blood Count"}],
                    "medicines": [],
                }
            ],
            "legacy_documents": [],
            "profile": {"conditions": [], "surgeries": [], "allergies": []},
        },
    )
    assert len(flags) == 1
    assert flags[0]["type"] == "REPEAT_INVESTIGATION"
    assert flags[0]["severity"] == "HIGH"
