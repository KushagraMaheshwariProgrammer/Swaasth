"""Shared NPPA ceiling-price and Jan Aushadhi enrichment for all bill schemes."""

from __future__ import annotations

from typing import Any

from app.jan_aushadhi_rates import enrich_line_items_with_jan_aushadhi
from app.pharma_rates import get_pharma_store


def _to_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return 0.0


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


def pharma_to_aarogya_item(
    raw_item: dict[str, Any], pharma_item: dict[str, Any]
) -> dict[str, Any]:
    """Map an NPPA comparison into the Aarogya Bhadratha item report shape."""
    item_name = str(pharma_item.get("item_name", "")).strip()
    quantity = max(_to_float(pharma_item.get("quantity")), 0.0) or 1.0
    unit_price = max(_to_float(pharma_item.get("unit_price")), 0.0)
    charged = _to_float(pharma_item.get("total_price"))
    if charged <= 0 and unit_price > 0:
        charged = round(quantity * unit_price, 2)

    entry: dict[str, Any] = {
        "item_name": item_name,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_price": round(charged, 2),
        "category": "medicine",
        "comparison_source": "pharma",
        "matched_name": pharma_item.get("matched_reference_item"),
        "matched_code": pharma_item.get("pharma_product_id"),
        "approved_unit_rate": pharma_item.get("pharma_unit_reference"),
        "approved_amount": pharma_item.get("pharma_rate"),
        "difference": pharma_item.get("price_difference"),
        "excess_amount": None,
        "percentage_difference": None,
        "match_confidence": 1.0 if pharma_item.get("matched_reference_item") else 0.0,
        "match_method": pharma_item.get("pharma_database") or "nppa",
        "rate_source": "nppa",
        "pharma_rate": pharma_item.get("pharma_rate"),
        "pharma_unit_reference": pharma_item.get("pharma_unit_reference"),
        "pharma_database": pharma_item.get("pharma_database"),
        "pharma_product_id": pharma_item.get("pharma_product_id"),
        "resolved_generic_name": pharma_item.get("resolved_generic_name"),
        "resolved_from_brand": pharma_item.get("resolved_from_brand"),
        "approximate_match": bool(pharma_item.get("approximate_match")),
        "flag": pharma_item.get("flag"),
        "price_difference": pharma_item.get("price_difference"),
        "status": "Rate Not Found",
        "note": "Medicine not found in the NPPA ceiling price list.",
    }

    approved = pharma_item.get("pharma_rate")
    if approved is None:
        return entry

    price_diff = _to_float(pharma_item.get("price_difference"))
    flag = pharma_item.get("flag")
    entry["approved_amount"] = approved
    entry["difference"] = price_diff
    if approved:
        entry["percentage_difference"] = round((price_diff / approved) * 100, 2)

    if flag == "overpriced":
        entry["excess_amount"] = max(price_diff, 0.0)
        entry["status"] = "Above Approved Rate"
        entry["note"] = ""
    elif flag == "acceptable":
        entry["excess_amount"] = 0.0
        entry["status"] = "Within Approved Rate"
        entry["note"] = ""
    else:
        entry["excess_amount"] = 0.0
        entry["status"] = "Within Approved Rate"
        entry["note"] = ""

    if pharma_item.get("pharma_database") == "nppa_via_az" and pharma_item.get(
        "resolved_generic_name"
    ):
        entry["note"] = (
            f"Brand name resolved to generic: {pharma_item['resolved_generic_name']}."
        )

    return entry


def enrich_scheme_line_items_with_jan_aushadhi(
    line_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Apply Jan Aushadhi catalog matching to medicine / NPPA line items."""
    return enrich_line_items_with_jan_aushadhi(line_items)
