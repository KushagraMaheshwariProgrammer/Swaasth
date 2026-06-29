"""Shared NPPA ceiling-price and Jan Aushadhi enrichment for bill review."""

from __future__ import annotations

from typing import Any

from app.jan_aushadhi_rates import enrich_line_items_with_jan_aushadhi
from app.pharma_rates import get_pharma_store


def compare_line_item_with_nppa(raw_item: dict[str, Any]) -> dict[str, Any]:
    """Compare a bill line against the NPPA ceiling list (with brand→generic fallback)."""
    try:
        store = get_pharma_store()
    except (FileNotFoundError, ValueError) as exc:
        item = dict(raw_item)
        item["comparison_source"] = "pharma"
        item["pharma_rate"] = None
        item["price_difference"] = None
        item["flag"] = "no_reference"
        item["matched_reference_item"] = None
        item["approximate_match"] = False
        item["pharma_error"] = str(exc)
        return item

    return store.compare_line_item(dict(raw_item))


def should_use_nppa_result(
    raw_item: dict[str, Any], pharma_item: dict[str, Any]
) -> bool:
    """True when NPPA matched or the line is categorized as a medicine."""
    if pharma_item.get("matched_reference_item"):
        return True
    if pharma_item.get("pharma_rate") is not None:
        return True
    return str(raw_item.get("category", "")).strip().lower() == "medicine"


def enrich_bill_line_items_with_jan_aushadhi(
    line_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Apply Jan Aushadhi catalog matching to medicine / NPPA line items."""
    return enrich_line_items_with_jan_aushadhi(line_items)
