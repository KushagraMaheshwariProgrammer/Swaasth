"""Tests for Jan Aushadhi catalog matching."""

from pathlib import Path

import pytest

from app.jan_aushadhi_rates import (
    JanAushadhiRatesStore,
    build_jan_aushadhi_summary,
    enrich_line_items_with_jan_aushadhi,
)


@pytest.fixture(scope="module")
def store() -> JanAushadhiRatesStore:
    csv_path = (
        Path(__file__).resolve().parent.parent / "data" / "Jan_Aushadhi_Product_List.csv"
    )
    if not csv_path.exists():
        pytest.skip("Jan Aushadhi product list CSV not available")
    return JanAushadhiRatesStore(csv_path)


class TestJanAushadhiDirectMatch:
    def test_paracetamol_500mg_tablets(self, store: JanAushadhiRatesStore) -> None:
        match = store.find_match("Paracetamol 500mg Tablets")
        assert match is not None
        assert "paracetamol" in match["generic_name"].lower()
        assert match["mrp_inr"] > 0

    def test_azithromycin_250mg(self, store: JanAushadhiRatesStore) -> None:
        match = store.find_match("Azithromycin 250 mg Tablet")
        assert match is not None
        assert "azithromycin" in match["generic_name"].lower()


class TestJanAushadhiEnrichment:
    def test_enrich_medicine_line_item(self, store: JanAushadhiRatesStore) -> None:
        enriched = store.enrich_line_item(
            {
                "item_name": "Paracetamol 500mg Tablet",
                "category": "medicine",
                "total_price": 50,
            }
        )
        assert enriched["jan_aushadhi_available"] is True
        assert enriched["jan_aushadhi_generic_name"]
        assert enriched["jan_aushadhi_mrp"] is not None

    def test_non_medicine_skipped_in_batch(self) -> None:
        items = [
            {"item_name": "X-Ray Chest", "category": "procedure", "total_price": 500},
            {
                "item_name": "Paracetamol 500mg Tablet",
                "category": "medicine",
                "comparison_source": "pharma",
                "total_price": 50,
            },
        ]
        enriched, summary = enrich_line_items_with_jan_aushadhi(items)
        assert enriched[0].get("jan_aushadhi_available") is not True
        assert summary is not None
        assert summary["matches_count"] >= 1

    def test_summary_structure(self) -> None:
        items = [
            {
                "item_name": "Paracetamol 500mg",
                "jan_aushadhi_available": True,
                "jan_aushadhi_generic_name": "Paracetamol Tablets IP 500 mg",
                "jan_aushadhi_mrp": 6.57,
                "jan_aushadhi_unit_size": "10's",
                "jan_aushadhi_drug_code": "23",
            }
        ]
        summary = build_jan_aushadhi_summary(items)
        assert summary["matches_count"] == 1
        assert summary["matches"][0]["mrp"] == 6.57
        assert "Jan Aushadhi" in summary["advisory"]
