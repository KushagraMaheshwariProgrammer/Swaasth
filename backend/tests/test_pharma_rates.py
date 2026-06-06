"""Unit tests for NPPA ceiling price matching and brand-to-generic resolution."""

import pytest
from app.pharma_rates import (
    compact_medicine_key,
    _extract_generic_from_composition,
    _extract_strength_from_text,
    _is_manufacturer_row,
    get_pharma_store,
)


class TestCompactMedicineKey:
    """Tests for PDF split-word artifact repair."""

    def test_paracetamol_split(self):
        assert compact_medicine_key("Parac etamol") == "paracetamol"

    def test_paracetamol_normal(self):
        assert compact_medicine_key("Paracetamol") == "paracetamol"

    def test_azithromycin_split(self):
        assert compact_medicine_key("Azith romycin") == "azithromycin"

    def test_azithromycin_normal(self):
        assert compact_medicine_key("Azithromycin") == "azithromycin"

    def test_baclofen_split(self):
        assert compact_medicine_key("Baclo fen") == "baclofen"

    def test_baclofen_normal(self):
        assert compact_medicine_key("Baclofen") == "baclofen"

    def test_betamethasone_split(self):
        assert compact_medicine_key("Betam ethasone") == "betamethasone"

    def test_budesonide_split(self):
        assert compact_medicine_key("Bude sonide") == "budesonide"

    def test_case_insensitive(self):
        assert compact_medicine_key("PARACETAMOL") == "paracetamol"
        assert compact_medicine_key("parac etamol") == "paracetamol"

    def test_with_strength(self):
        key = compact_medicine_key("Paracetamol 500mg Tablet")
        assert "paracetamol" in key
        assert "500" in key
        assert "tablet" in key

    def test_split_and_normal_match(self):
        split_key = compact_medicine_key("Parac etamol")
        normal_key = compact_medicine_key("Paracetamol")
        assert split_key == normal_key


class TestExtractGenericFromComposition:
    """Tests for extracting generic names from AZ composition strings."""

    def test_simple_composition(self):
        result = _extract_generic_from_composition("Azithromycin (500mg)")
        assert "azithromycin" in result

    def test_composition_with_ip(self):
        result = _extract_generic_from_composition("Paracetamol IP 500mg")
        assert "paracetamol" in result

    def test_amoxycillin_harmonization(self):
        result = _extract_generic_from_composition("Amoxycillin (500mg)")
        assert "amoxicillin" in result

    def test_empty_input(self):
        assert _extract_generic_from_composition("") == ""
        assert _extract_generic_from_composition(None) == ""


class TestExtractStrength:
    """Tests for strength extraction from medicine names."""

    def test_mg_strength(self):
        strengths = _extract_strength_from_text("Paracetamol 500mg")
        assert 500.0 in strengths

    def test_mcg_strength(self):
        strengths = _extract_strength_from_text("Budesonide 200mcg")
        assert 200.0 in strengths

    def test_multiple_strengths(self):
        strengths = _extract_strength_from_text("Amoxicillin 500mg + Clavulanic Acid 125mg")
        assert 500.0 in strengths
        assert 125.0 in strengths

    def test_no_strength(self):
        strengths = _extract_strength_from_text("Paracetamol Tablet")
        assert len(strengths) == 0


class TestManufacturerRowDetection:
    """Tests for filtering branded/manufacturer-specific NPPA rows."""

    def test_generic_row(self):
        assert not _is_manufacturer_row("Paracetamol")
        assert not _is_manufacturer_row("Azithromycin")

    def test_manufacturer_row_ms(self):
        assert _is_manufacturer_row("Paracetamol Drops M/s Macleods Pharmaceuticals")

    def test_manufacturer_row_mfd_by(self):
        assert _is_manufacturer_row("Azithromycin Tablet Mfd by Cipla Ltd")

    def test_manufacturer_row_manufactured(self):
        assert _is_manufacturer_row("Paracetamol manufactured and marketed by XYZ")


class TestNppaDirectMatch:
    """Tests for direct NPPA ceiling price matching."""

    @pytest.fixture
    def store(self):
        return get_pharma_store()

    def test_paracetamol_500mg_match(self, store):
        match = store.find_match("Paracetamol 500mg", quantity=10)
        assert match is not None
        assert match["database"] == "nppa"
        assert match["rate"] == 0.92

    def test_paracetamol_split_word_match(self, store):
        match = store.find_match("Parac etamol 500mg", quantity=10)
        assert match is not None
        assert match["rate"] == 0.92

    def test_azithromycin_500mg_match(self, store):
        match = store.find_match("Azithromycin 500mg Tablet", quantity=5)
        assert match is not None
        assert match["database"] == "nppa"
        assert match["rate"] == 23.98

    def test_azithromycin_split_word_match(self, store):
        match = store.find_match("Azith romycin 500mg Tablet", quantity=5)
        assert match is not None
        assert match["rate"] == 23.98


class TestAzFallback:
    """Tests for brand-to-generic resolution via AZ dataset."""

    @pytest.fixture
    def store(self):
        return get_pharma_store()

    def test_azithral_resolves_to_azithromycin(self, store):
        if store.az is None:
            pytest.skip("AZ dataset not loaded")
        
        resolution = store.az.resolve("Azithral 500 Tablet")
        assert resolution is not None
        assert "azithromycin" in resolution["generic_name"]

    def test_brand_match_uses_nppa_ceiling(self, store):
        if store.az is None:
            pytest.skip("AZ dataset not loaded")
        
        match = store.find_match("Azithral 500 Tablet", quantity=5)
        if match and match.get("resolved_generic_name"):
            assert match["database"] == "nppa_via_az"


class TestMatchCorrectness:
    """Regression tests: a bill line must only match the correct generic drug.

    These guard against loose character-similarity matching that previously
    returned unrelated drugs (e.g. Crocin -> Mupirocin, Pan 40 -> Dextran-40).
    """

    @pytest.fixture
    def store(self):
        return get_pharma_store()

    def _medicine(self, store, name):
        match = store.find_match(name, quantity=10)
        return match["medicine"].lower() if match else None

    def test_crocin_is_paracetamol_not_mupirocin(self, store):
        med = self._medicine(store, "Crocin 650")
        assert med is not None
        assert "mupirocin" not in med
        assert "paracetamol" in med.replace(" ", "")

    def test_pan40_is_pantoprazole_not_dextran(self, store):
        med = self._medicine(store, "Pan 40")
        assert med is not None
        assert "dextran" not in med
        assert "pantoprazole" in med.replace(" ", "")

    def test_ecosprin_is_aspirin_not_cyclosporine(self, store):
        med = self._medicine(store, "Ecosprin 75")
        assert med is not None
        assert "cyclosporine" not in med
        # NPPA lists aspirin as "Acetylsalicylic acid".
        assert "acetylsalicylic" in med.replace(" ", "")

    def test_aspirin_synonym_maps_to_acetylsalicylic_acid(self, store):
        med = self._medicine(store, "Aspirin 75mg")
        assert med is not None
        assert "acetylsalicylic" in med.replace(" ", "")

    def test_unrelated_brand_returns_no_match(self, store):
        # Digene (antacid) is not in the NPPA schedule and must NOT mis-match
        # to a similarly spelled drug like Digoxin.
        match = store.find_match("Digene", quantity=10)
        if match is not None:
            assert "digoxin" not in match["medicine"].lower()

    def test_strength_selection_picks_correct_row(self, store):
        # Brand with bare strength number should pick the 500mg tablet, not 250mg.
        match = store.find_match("Azithral 500 Tablet", quantity=5)
        assert match is not None
        assert match["rate"] == 23.98

    def test_paracetamol_strength_variants(self, store):
        m500 = store.find_match("Paracetamol 500mg", quantity=10)
        m650 = store.find_match("Paracetamol 650", quantity=10)
        assert m500 is not None and m500["rate"] == 0.92
        assert m650 is not None and m650["rate"] == 2.04

    def test_amlodipine_strength_variants(self, store):
        m5 = store.find_match("Amlodipine 5mg", quantity=10)
        m10 = store.find_match("Amlodipine 10mg", quantity=10)
        assert m5 is not None and m5["rate"] == 2.54
        assert m10 is not None and m10["rate"] == 5.54

    def test_combination_drug_matches_combo_row(self, store):
        # Amoxicillin + Clavulanic acid must match the NPPA combination row.
        match = store.find_match("Amoxicillin 500mg + Clavulanic Acid 125mg", quantity=10)
        assert match is not None
        med = match["medicine"].lower()
        assert "amoxicillin" in med.replace(" ", "")
        assert "clavulanic" in med


class TestStrictOverpricing:
    """Tests for strict (0% tolerance) ceiling price comparison."""

    @pytest.fixture
    def store(self):
        return get_pharma_store()

    def test_at_ceiling_acceptable(self, store):
        result = store.compare_line_item({
            "item_name": "Paracetamol 500mg",
            "quantity": 10,
            "total_price": 9.20,
        })
        assert result["flag"] == "acceptable"

    def test_below_ceiling_acceptable(self, store):
        result = store.compare_line_item({
            "item_name": "Paracetamol 500mg",
            "quantity": 10,
            "total_price": 8.00,
        })
        assert result["flag"] == "acceptable"

    def test_above_ceiling_overpriced(self, store):
        result = store.compare_line_item({
            "item_name": "Paracetamol 500mg",
            "quantity": 10,
            "total_price": 15.00,
        })
        assert result["flag"] == "overpriced"
        assert result["price_difference"] > 0

    def test_slightly_above_ceiling_overpriced(self, store):
        result = store.compare_line_item({
            "item_name": "Paracetamol 500mg",
            "quantity": 10,
            "total_price": 9.21,
        })
        assert result["flag"] == "overpriced"

    def test_no_reference_flag(self, store):
        result = store.compare_line_item({
            "item_name": "NonexistentMedicine XYZ 999mg",
            "quantity": 1,
            "total_price": 100.00,
        })
        assert result["flag"] == "no_reference"
        assert result["pharma_rate"] is None


class TestCompareLineItemFields:
    """Tests for compare_line_item response field structure."""

    @pytest.fixture
    def store(self):
        return get_pharma_store()

    def test_required_fields_present(self, store):
        result = store.compare_line_item({
            "item_name": "Paracetamol 500mg",
            "quantity": 10,
            "total_price": 9.20,
        })
        
        required_fields = [
            "comparison_source",
            "pharma_rate",
            "price_difference",
            "flag",
            "matched_reference_item",
            "approximate_match",
            "pharma_product_id",
            "pharma_database",
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_comparison_source_is_pharma(self, store):
        result = store.compare_line_item({
            "item_name": "Paracetamol 500mg",
            "quantity": 10,
            "total_price": 9.20,
        })
        assert result["comparison_source"] == "pharma"

    def test_price_basis_is_unit(self, store):
        result = store.compare_line_item({
            "item_name": "Paracetamol 500mg",
            "quantity": 10,
            "total_price": 9.20,
        })
        assert result["pharma_price_basis"] == "unit"
