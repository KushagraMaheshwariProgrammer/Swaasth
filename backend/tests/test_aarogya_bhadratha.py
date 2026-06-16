"""Tests for the Aarogya Bhadratha data layer, matching and comparison."""

from __future__ import annotations

import pytest

from app.aarogya_bhadratha import (
    AarogyaDataStore,
    get_aarogya_store,
    normalize_hospital_name,
    normalize_procedure_name,
    parse_rate_amount,
)


@pytest.fixture(scope="module")
def store() -> AarogyaDataStore:
    try:
        return get_aarogya_store()
    except Exception as exc:  # pragma: no cover - data missing in CI
        pytest.skip(f"Aarogya Bhadratha data unavailable: {exc}")


class TestNormalization:
    def test_hospital_abbreviations_and_suffixes(self) -> None:
        a = normalize_hospital_name("Apollo Hospitals Pvt. Ltd.")
        b = normalize_hospital_name("Apollo Hosp")
        assert "apollo" in a
        assert "apollo" in b
        # legal suffixes / 'hospital' token stripped
        assert "ltd" not in a and "pvt" not in a

    def test_brand_name_not_fully_stripped(self) -> None:
        assert normalize_hospital_name("Care Hospital") == "care hospital"

    def test_procedure_normalization(self) -> None:
        assert normalize_procedure_name("General Anaesthesia (GA)") == "general anaesthesia"

    def test_rate_amount_parsing(self) -> None:
        assert parse_rate_amount("Rs.2,000/- per Day") == (2000.0, "per day")
        assert parse_rate_amount("6000 per Day") == (6000.0, "per day")
        assert parse_rate_amount("Rs.50/- Per Hour") == (50.0, "per hour")
        # formula based -> not numeric
        assert parse_rate_amount("50% increase on NIMS tariff") == (None, "")
        assert parse_rate_amount("") == (None, "")


class TestDirectory:
    def test_districts_present(self, store: AarogyaDataStore) -> None:
        districts = store.list_districts()
        assert districts
        assert any(d.lower() == "hyderabad" for d in districts)

    def test_search_by_name(self, store: AarogyaDataStore) -> None:
        res = store.search_hospitals(query="apollo", limit=50)
        assert res["total"] >= 1
        assert all("apollo" in h["full_name"].lower() for h in res["results"])

    def test_search_by_district_filter(self, store: AarogyaDataStore) -> None:
        res = store.search_hospitals(district="Hyderabad", limit=100)
        assert res["total"] >= 1
        assert all(h["district"].lower() == "hyderabad" for h in res["results"])

    def test_pagination(self, store: AarogyaDataStore) -> None:
        page1 = store.search_hospitals(page=1, limit=5)
        page2 = store.search_hospitals(page=2, limit=5)
        assert len(page1["results"]) == 5
        ids1 = {h["id"] for h in page1["results"]}
        ids2 = {h["id"] for h in page2["results"]}
        assert ids1.isdisjoint(ids2)


class TestHospitalVerification:
    def test_exact_match(self, store: AarogyaDataStore) -> None:
        result = store.verify_hospital(
            "Apollo Hospital, Hyderguda, Hyderabad", district="Hyderabad"
        )
        assert result["empanelment_status"] == "empanelled"
        assert result["matched_hospital"] is not None
        assert result["match_confidence"] >= 0.8

    def test_normalized_fuzzy_match(self, store: AarogyaDataStore) -> None:
        result = store.verify_hospital("APOLLO HOSPITALS HYDERGUDA", district="Hyderabad")
        assert result["empanelment_status"] in {"empanelled", "multiple"}

    def test_brand_only_name_returns_candidates(self, store: AarogyaDataStore) -> None:
        result = store.verify_hospital("Apollo Hospital", district="Hyderabad")
        assert result["empanelment_status"] == "multiple"
        assert len(result["candidates"]) >= 2

    def test_care_hospital_brand(self, store: AarogyaDataStore) -> None:
        result = store.verify_hospital("Care Hospital", district="Hyderabad")
        assert result["empanelment_status"] in {"empanelled", "multiple"}
        assert result["empanelment_status"] != "name_missing"

    def test_kims_brand(self, store: AarogyaDataStore) -> None:
        result = store.verify_hospital("KIMS Hospital", district="Hyderabad")
        assert result["empanelment_status"] in {"empanelled", "multiple"}

    def test_not_found(self, store: AarogyaDataStore) -> None:
        result = store.verify_hospital("Totally Unrelated Wellness XYZ", district="")
        assert result["empanelment_status"] in {"not_found", "multiple"}
        if result["empanelment_status"] == "not_found":
            assert result["matched_hospital"] is None

    def test_missing_name(self, store: AarogyaDataStore) -> None:
        result = store.verify_hospital("", district="Hyderabad")
        assert result["empanelment_status"] == "name_missing"


class TestRateMatching:
    def test_exact_icd_code(self, store: AarogyaDataStore) -> None:
        match = store.match_rate("Medical Management of Acute Bronchitis", code_hint="J20.0")
        assert match is not None
        assert match["match_method"] == "exact_code"
        # Rate may come from EHS (65500 NABH) or annexure (66600) depending on data source
        assert match["rate"] is not None and match["rate"] > 0
        # Verify hospital-type-specific rates are available (from EHS)
        if match.get("rate_nabh") is not None:
            assert match["rate_non_nabh"] is not None

    def test_exact_name(self, store: AarogyaDataStore) -> None:
        match = store.match_rate("General Anaesthesia")
        assert match is not None
        assert match["rate"] and match["rate"] > 0

    def test_unrelated_not_matched(self, store: AarogyaDataStore) -> None:
        assert store.match_rate("Deluxe Television Rental Charges Zzqq") is None


class TestComparison:
    def test_mixed_matched_unmatched(self, store: AarogyaDataStore) -> None:
        items = [
            {"item_name": "General Anaesthesia", "quantity": 1, "total_price": 2500},
            {"item_name": "General Anaesthesia", "quantity": 1, "total_price": 1500},
            {"item_name": "Zzqq Unknown Charge", "quantity": 1, "total_price": 999},
        ]
        result = store.compare_bill_items(items)
        summary = result["summary"]
        assert summary["total_items"] == 3
        assert summary["unmatched_items"] >= 1
        statuses = {i["status"] for i in result["items"]}
        assert "Above Approved Rate" in statuses
        assert "Rate Not Found" in statuses
        assert summary["total_charged"] == pytest.approx(5000 - 1, abs=1)

    def test_within_rate(self, store: AarogyaDataStore) -> None:
        items = [{"item_name": "General Anaesthesia", "quantity": 1, "total_price": 1000}]
        result = store.compare_bill_items(items)
        item = result["items"][0]
        assert item["status"] in {"Below Approved Rate", "Within Approved Rate"}
        # charged 1000 < approved 1500 => below
        assert item["excess_amount"] == 0.0

    def test_unmatched_not_overcharged(self, store: AarogyaDataStore) -> None:
        items = [{"item_name": "Zzqq Unknown Charge", "quantity": 1, "total_price": 9999}]
        result = store.compare_bill_items(items)
        item = result["items"][0]
        assert item["status"] == "Rate Not Found"
        assert item["excess_amount"] is None
        assert result["summary"]["total_possible_excess"] == 0.0
