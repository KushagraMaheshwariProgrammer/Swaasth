"""Tests for treatment audit prescription item shaping."""

from __future__ import annotations

from app.services.treatment_audit import _prescription_items_for_audit


def test_prescription_items_for_audit_includes_dose_fields() -> None:
    items = _prescription_items_for_audit(
        [
            {
                "name": "Paracetamol 500mg",
                "category": "medicine",
                "dose": "500mg",
                "frequency": "twice daily",
                "duration": "5 days",
            }
        ]
    )
    assert len(items) == 1
    assert items[0]["dose"] == "500mg"
    assert items[0]["frequency"] == "twice daily"
    assert items[0]["duration"] == "5 days"
