"""Tests for cross-scheme NPPA + Jan Aushadhi medicine comparison."""

from __future__ import annotations

import pytest

from app.aarogya_bhadratha import get_aarogya_store
from app.medicine_comparison import (
    compare_line_item_with_nppa,
    enrich_scheme_line_items_with_jan_aushadhi,
    should_use_nppa_result,
)


def test_nppa_matches_generic_medicine_name() -> None:
    result = compare_line_item_with_nppa(
        {
            "item_name": "Paracetamol 500mg Tablet",
            "quantity": 10,
            "total_price": 20,
            "category": "medicine",
        }
    )
    assert should_use_nppa_result({"category": "medicine"}, result)
    assert result.get("matched_reference_item")
    assert result.get("pharma_rate") is not None


def test_nppa_resolves_brand_name() -> None:
    result = compare_line_item_with_nppa(
        {
            "item_name": "Crocin 650",
            "quantity": 1,
            "total_price": 30,
            "category": "other",
        }
    )
    assert should_use_nppa_result({"category": "other"}, result)
    assert result.get("pharma_database") in {"nppa", "nppa_via_az"}


def test_aarogya_compare_uses_nppa_for_medicines() -> None:
    store = get_aarogya_store()
    comparison = store.compare_bill_items(
        [
            {
                "item_name": "Paracetamol 500mg Tablet",
                "quantity": 10,
                "total_price": 20,
                "category": "medicine",
            }
        ]
    )
    item = comparison["items"][0]
    assert item.get("comparison_source") == "pharma"
    assert item.get("matched_name")


def test_jan_aushadhi_enrichment_for_aarogya_items() -> None:
    store = get_aarogya_store()
    comparison = store.compare_bill_items(
        [
            {
                "item_name": "Paracetamol 500mg Tablet",
                "quantity": 10,
                "total_price": 20,
                "category": "medicine",
            }
        ]
    )
    enriched, summary = enrich_scheme_line_items_with_jan_aushadhi(comparison["items"])
    if summary is None:
        pytest.skip("Jan Aushadhi dataset unavailable")
    assert enriched[0].get("jan_aushadhi_available") in {True, False}
