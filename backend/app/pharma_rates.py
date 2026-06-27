"""NPPA ceiling price reference for medicine cost checking.

Uses NPPA (National Pharmaceutical Pricing Authority) ceiling prices as the
authoritative reference. Matching is by generic ingredient identity (exact and
ingredient-set based), NOT loose character similarity, so a bill line only
matches an NPPA drug when the actual generic ingredient(s) align. Brand names
are resolved to their generic ingredients via the AZ Kaggle dataset when a
direct NPPA match is not found.
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.cghs_rates import normalize_item_name

PRICE_TOLERANCE = float(os.getenv("PHARMA_PRICE_TOLERANCE", "0.0"))
MIN_INGREDIENT_KEY_LEN = 3

DatabaseLabel = Literal["nppa", "nppa_via_az"]

MANUFACTURER_MARKERS = frozenset([
    "m/s", "mfd by", "manufactured", "marketed", "mfg by", "mfg.", "ltd.",
])

SPELLING_HARMONIZATION: dict[str, str] = {
    "amoxycillin": "amoxicillin",
    "clavulanate": "clavulanic acid",
    "atorvastatin calcium": "atorvastatin",
    "metformin hcl": "metformin",
    "metformin hydrochloride": "metformin",
    "omeprazole magnesium": "omeprazole",
    "pantoprazole sodium": "pantoprazole",
    "losartan potassium": "losartan",
    "amlodipine besylate": "amlodipine",
    "amlodipine besilate": "amlodipine",
    "cetirizine hcl": "cetirizine",
    "cetirizine hydrochloride": "cetirizine",
    "diclofenac sodium": "diclofenac",
    "diclofenac potassium": "diclofenac",
    "azithromycin dihydrate": "azithromycin",
    # NPPA names aspirin as "Acetylsalicylic acid"; brands say "Aspirin".
    "acetyl salicylic acid": "acetylsalicylic acid",
    "aspirin": "acetylsalicylic acid",
    "frusemide": "furosemide",
    "rabeprazole sodium": "rabeprazole",
    "esomeprazole magnesium": "esomeprazole",
}

# Canonical dosage form -> set of keywords/abbreviations seen in bills.
ORAL_SOLID_FORMS = frozenset(["tablet", "capsule"])

FORM_CANONICAL: dict[str, str] = {
    "tablet": "tablet", "tablets": "tablet", "tab": "tablet", "tabs": "tablet",
    "capsule": "capsule", "capsules": "capsule", "cap": "capsule", "caps": "capsule",
    "injection": "injection", "inj": "injection", "vial": "injection",
    "ampoule": "injection", "amp": "injection",
    "syrup": "syrup", "syp": "syrup", "syr": "syrup",
    "suspension": "suspension", "susp": "suspension",
    "drops": "drops", "drop": "drops",
    "cream": "cream", "ointment": "ointment", "oint": "ointment",
    "gel": "gel", "lotion": "lotion", "spray": "spray",
    "inhaler": "inhalation", "inhalation": "inhalation",
    "suppository": "suppository", "enema": "enema",
    "solution": "solution", "soln": "solution", "powder": "powder",
}

# Words that are dosage forms or marketing/strength noise, stripped from
# ingredient names so they do not pollute generic identity.
NOISE_WORDS = frozenset([
    "tablet", "tablets", "tab", "tabs", "capsule", "capsules", "cap", "caps",
    "injection", "inj", "vial", "ampoule", "amp", "syrup", "syp", "syr",
    "suspension", "susp", "drops", "drop", "cream", "ointment", "oint", "gel",
    "lotion", "spray", "inhaler", "inhalation", "suppository", "enema",
    "solution", "soln", "powder", "oral", "liquid", "dose", "metered",
    "respirator", "nebulizer", "dry", "chewable", "effervescent", "dispersible",
    "enteric", "coated", "conventional", "sustained", "release", "extended",
    "sr", "er", "xr", "xl", "cr", "dt", "md", "od", "ds",
    "plus", "forte", "duo", "junior", "kid", "kids", "infusion", "eye", "ear",
    "film", "uncoated", "bilayered", "bilayer", "hard", "gelatin",
])

STRENGTH_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|gm|g|ml|iu|%|units?|lac|lacs|kiu|miu)\b"
)
INGREDIENT_SPLIT_RE = re.compile(r"\s*\+\s*|\s*&\s*|\s+and\s+|\s*,\s*", re.IGNORECASE)


def compact_medicine_key(name: str) -> str:
    """Normalize medicine name and remove all spaces to handle PDF split-word artifacts.

    'Parac etamol' / 'Paracetamol' -> 'paracetamol'
    'Azith romycin' / 'Azithromycin' -> 'azithromycin'
    """
    normalized = normalize_item_name(name)
    return normalized.replace(" ", "")


def _harmonize(text: str) -> str:
    for source, target in SPELLING_HARMONIZATION.items():
        if source in text:
            text = text.replace(source, target)
    return text


def _clean_ingredient(part: str) -> str:
    """Reduce a single ingredient fragment to its bare generic name.

    Removes parentheticals, strengths, dosage-form/marketing words, stray
    numbers and single letters, then applies spelling harmonization.
    'Clavulanic acid (B)' -> 'clavulanic acid'
    'Paracetamol IP 500mg' -> 'paracetamol'
    """
    text = part.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = STRENGTH_RE.sub(" ", text)
    text = normalize_item_name(text)
    text = _harmonize(text)

    tokens = []
    for tok in text.split():
        if tok in NOISE_WORDS:
            continue
        if len(tok) <= 1:
            continue
        if tok[0].isdigit():
            continue
        tokens.append(tok)
    return " ".join(tokens).strip()


def _ingredient_keys(name: str) -> list[str]:
    """Split a medicine name into ordered, de-duplicated generic ingredient keys.

    'Amoxicillin (A) + Clavulanic acid (B)' -> ['amoxicillin', 'clavulanicacid']
    'Paracetamol 500mg Tablet' -> ['paracetamol']
    """
    if not name:
        return []
    keys: list[str] = []
    for part in INGREDIENT_SPLIT_RE.split(name):
        cleaned = _clean_ingredient(part)
        key = cleaned.replace(" ", "")
        if len(key) >= MIN_INGREDIENT_KEY_LEN and key not in keys:
            keys.append(key)
    return keys


def _extract_generic_from_composition(composition: str) -> str:
    """Extract generic name from a single AZ composition field.

    'Amoxycillin (500mg)' -> 'amoxicillin'
    'Paracetamol IP 500mg' -> 'paracetamol'
    """
    if not composition:
        return ""
    return _clean_ingredient(composition)


def _extract_strength_from_text(text: str) -> list[float]:
    """Extract numeric strengths from text (e.g., '500mg', '650 mg')."""
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:mg|mcg|g|ml|iu)", text.lower())
    return [float(m) for m in matches]


def _resolve_query_strength(text: str) -> float | None:
    """Best-effort strength for row selection.

    Prefer a unit-qualified strength ('500mg'); otherwise fall back to the
    largest plausible bare number in the name ('Azithral 500' -> 500), which is
    almost always the strength rather than a pack count.
    """
    unit_qualified = _extract_strength_from_text(text)
    if unit_qualified:
        return unit_qualified[0]
    bare = [float(n) for n in re.findall(r"\b(\d{1,4})\b", text)]
    bare = [n for n in bare if 1 <= n <= 2000]
    return max(bare) if bare else None


def _detect_form(text: str) -> str | None:
    """Detect the canonical dosage form mentioned in a bill line, if any."""
    for tok in normalize_item_name(text).split():
        canonical = FORM_CANONICAL.get(tok)
        if canonical:
            return canonical
    return None


def _is_manufacturer_row(medicine_name: str) -> bool:
    """Check if NPPA row is a branded/manufacturer-specific entry."""
    lower = medicine_name.lower()
    return any(marker in lower for marker in MANUFACTURER_MARKERS)


def _to_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        clean = str(value).replace(",", "").strip()
        clean = re.sub(r"[^\d.]", "", clean.split()[0] if clean else "0")
        return float(clean) if clean else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _kaggle_cache_csv(slug_parts: tuple[str, str], filename: str) -> Path | None:
    owner, dataset = slug_parts
    versions_root = (
        Path.home()
        / ".cache"
        / "kagglehub"
        / "datasets"
        / owner
        / dataset
        / "versions"
    )
    if not versions_root.exists():
        return None
    for version_dir in sorted(versions_root.iterdir(), reverse=True):
        candidate = version_dir / filename
        if candidate.exists():
            return candidate
    return None


def _default_nppa_csv_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent
    env_path = os.getenv("NPPA_DATASET_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"NPPA_DATASET_PATH does not exist: {path}")

    candidates = [
        backend_root / "data" / "NPPA_Price_List_03-06-2025.csv",
    ]
    for path in candidates:
        if path and path.exists():
            return path

    raise FileNotFoundError(
        "NPPA price list not found at backend/data/NPPA_Price_List_03-06-2025.csv"
    )


def _default_az_csv_path() -> Path | None:
    backend_root = Path(__file__).resolve().parent.parent
    env_path = os.getenv("AZ_MEDICINES_DATASET_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        return path if path.exists() else None

    candidates = [
        backend_root / "data" / "az_medicines_india.csv",
        backend_root / "data" / "A_Z_medicines_dataset_of_India.csv",
        _kaggle_cache_csv(
            ("shudhanshusingh", "az-medicine-dataset-of-india"),
            "A_Z_medicines_dataset_of_India.csv",
        ),
        backend_root / "tests" / "fixtures" / "az_brands_ci.csv",
    ]
    for path in candidates:
        if path and path.exists():
            return path
    return None


@dataclass(frozen=True)
class NppaPriceRow:
    sl_no: int
    medicine: str
    dosage_form: str
    unit: str
    ceiling_price_inr: float
    compact_key: str
    ingredient_keys: tuple[str, ...]
    ingredient_set: frozenset[str]
    form: str | None
    strength_mg: float


@dataclass(frozen=True)
class AzBrandRow:
    row_id: int
    brand_name: str
    manufacturer: str
    short_composition1: str
    short_composition2: str
    normalized_name: str
    name_tokens: frozenset[str]
    ingredient_keys: tuple[str, ...]


class NppaRatesStore:
    """Loads and indexes NPPA ceiling price data by generic ingredient identity."""

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        self.rows: list[NppaPriceRow] = []
        self._by_core: dict[str, list[NppaPriceRow]] = {}
        self._by_ingredient_set: dict[frozenset[str], list[NppaPriceRow]] = {}
        self._by_single: dict[str, list[NppaPriceRow]] = {}
        self._load(csv_path)

    def _load(self, path: Path) -> None:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                medicine = (raw.get("Medicine") or "").strip()
                if not medicine:
                    continue

                ceiling = _to_float(raw.get("Ceiling_Price_Rs", ""))
                if ceiling <= 0:
                    continue

                if _is_manufacturer_row(medicine):
                    continue

                # Skip truncated combo rows (PDF dropped the second ingredient),
                # e.g. "(PPP I-L) Pantoprazole+" — these masquerade as pure drugs.
                if medicine.rstrip().endswith("+"):
                    continue

                ing_keys = _ingredient_keys(medicine)
                if not ing_keys:
                    continue

                # Declared as a combination ("+") but only one ingredient parsed
                # cleanly: unreliable identity, skip.
                if "+" in medicine and len(ing_keys) < 2:
                    continue

                dosage_form = (raw.get("Dosage_Form_and_Strength") or "").strip()
                unit = (raw.get("Unit") or "").strip()
                strengths = _extract_strength_from_text(dosage_form)

                row = NppaPriceRow(
                    sl_no=_to_int(raw.get("Sl_No")),
                    medicine=medicine,
                    dosage_form=dosage_form,
                    unit=unit,
                    ceiling_price_inr=ceiling,
                    compact_key=compact_medicine_key(medicine),
                    ingredient_keys=tuple(ing_keys),
                    ingredient_set=frozenset(ing_keys),
                    form=_detect_form(dosage_form),
                    strength_mg=strengths[0] if strengths else 0.0,
                )
                self.rows.append(row)

                core = "".join(ing_keys)
                self._by_core.setdefault(core, []).append(row)
                self._by_ingredient_set.setdefault(row.ingredient_set, []).append(row)
                for key in row.ingredient_set:
                    self._by_single.setdefault(key, []).append(row)

        if not self.rows:
            raise ValueError(f"No NPPA rows loaded from {path}")

    def match_keys(
        self,
        ingredient_keys: list[str],
        *,
        prefer_strength: float | None = None,
        prefer_form: str | None = None,
    ) -> dict[str, Any] | None:
        """Find the NPPA row matching the given generic ingredient key(s)."""
        keys = [k for k in ingredient_keys if len(k) >= MIN_INGREDIENT_KEY_LEN]
        if not keys:
            return None

        query_set = frozenset(keys)

        # 1. Exact ordered core match (fast, precise).
        core_rows = self._by_core.get("".join(keys))
        if core_rows:
            return self._build(core_rows, False, prefer_strength, prefer_form)

        # 2. Exact ingredient-set match (order independent).
        set_rows = self._by_ingredient_set.get(query_set)
        if set_rows:
            return self._build(set_rows, False, prefer_strength, prefer_form)

        # 3. Single ingredient: prefer pure single-ingredient drugs.
        if len(query_set) == 1:
            (only_key,) = tuple(query_set)
            rows = self._by_single.get(only_key)
            if rows:
                pure = [r for r in rows if r.ingredient_set == query_set]
                pool = pure if pure else rows
                return self._build(pool, not pure, prefer_strength, prefer_form)
            return None

        # 4. Combination: smallest NPPA row whose ingredients cover the query.
        supersets = [
            r for r in self._by_single.get(next(iter(query_set)), [])
            if query_set <= r.ingredient_set
        ]
        if supersets:
            best_size = min(len(r.ingredient_set) for r in supersets)
            smallest = [r for r in supersets if len(r.ingredient_set) == best_size]
            return self._build(
                smallest, best_size != len(query_set), prefer_strength, prefer_form
            )

        return None

    def _build(
        self,
        rows: list[NppaPriceRow],
        base_approximate: bool,
        prefer_strength: float | None,
        prefer_form: str | None,
    ) -> dict[str, Any]:
        row = self._pick(rows, prefer_strength, prefer_form)
        form_mismatch = (
            prefer_form is not None
            and row.form is not None
            and row.form != prefer_form
        )
        return self._payload(row, base_approximate or form_mismatch)

    def _pick(
        self,
        rows: list[NppaPriceRow],
        prefer_strength: float | None,
        prefer_form: str | None,
    ) -> NppaPriceRow:
        if len(rows) == 1:
            return rows[0]

        def score(row: NppaPriceRow) -> tuple[int, float]:
            form_score = 0
            if prefer_form and row.form == prefer_form:
                form_score = 2
            elif prefer_form is None and row.form in ORAL_SOLID_FORMS:
                form_score = 1

            strength_score = 0.0
            if prefer_strength and row.strength_mg > 0:
                strength_score = -abs(prefer_strength - row.strength_mg)

            return (form_score, strength_score)

        return max(rows, key=score)

    def _payload(self, row: NppaPriceRow, approximate: bool) -> dict[str, Any]:
        return {
            "reference_item": f"{row.medicine} · {row.dosage_form}",
            "rate": row.ceiling_price_inr,
            "per_unit_rate": row.ceiling_price_inr,
            "sl_no": row.sl_no,
            "medicine": row.medicine,
            "dosage_form": row.dosage_form,
            "unit": row.unit,
            "approximate_match": approximate,
            "database": "nppa",
            "_row": row,
        }

    def find_match(
        self,
        item_name: str,
        *,
        quantity: float = 1.0,
        prefer_strength: float | None = None,
        prefer_form: str | None = None,
    ) -> dict[str, Any] | None:
        """Match a free-text medicine name against NPPA generics by ingredient identity."""
        if prefer_strength is None:
            prefer_strength = _resolve_query_strength(item_name)
        if prefer_form is None:
            prefer_form = _detect_form(item_name)
        return self.match_keys(
            _ingredient_keys(item_name),
            prefer_strength=prefer_strength,
            prefer_form=prefer_form,
        )


class BrandToGenericStore:
    """Resolves brand names to generic ingredients using the AZ dataset.

    Prices from this dataset are never used; only the brand -> generic mapping.
    """

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        self.rows: list[AzBrandRow] = []
        self._by_normalized: dict[str, list[AzBrandRow]] = {}
        self._by_token: dict[str, list[AzBrandRow]] = {}
        self._load(csv_path)

    def _load(self, path: Path) -> None:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            row_id = 0
            for raw in reader:
                brand = (raw.get("name") or "").strip()
                if not brand:
                    continue

                comp1 = (raw.get("short_composition1") or "").strip()
                comp2 = (raw.get("short_composition2") or "").strip()
                if not comp1:
                    continue

                normalized = normalize_item_name(brand)
                ing_keys: list[str] = []
                for comp in (comp1, comp2):
                    for key in _ingredient_keys(comp):
                        if key not in ing_keys:
                            ing_keys.append(key)
                if not ing_keys:
                    continue

                # Index only meaningful brand tokens (exclude dosage forms/numbers).
                brand_tokens = frozenset(
                    tok for tok in normalized.split()
                    if len(tok) >= 3 and tok not in NOISE_WORDS and not tok[0].isdigit()
                )

                row = AzBrandRow(
                    row_id=row_id,
                    brand_name=brand,
                    manufacturer=(raw.get("manufacturer_name") or "").strip(),
                    short_composition1=comp1,
                    short_composition2=comp2,
                    normalized_name=normalized,
                    name_tokens=brand_tokens,
                    ingredient_keys=tuple(ing_keys),
                )
                row_id += 1
                self.rows.append(row)
                self._by_normalized.setdefault(normalized, []).append(row)
                for token in brand_tokens:
                    self._by_token.setdefault(token, []).append(row)

    def _candidate_rows(self, brand_tokens: set[str]) -> list[AzBrandRow]:
        seen: set[int] = set()
        candidates: list[AzBrandRow] = []
        for token in brand_tokens:
            for row in self._by_token.get(token, ()):
                if row.row_id in seen:
                    continue
                seen.add(row.row_id)
                candidates.append(row)
        return candidates

    def resolve(self, item_name: str) -> dict[str, Any] | None:
        """Resolve a brand name to its generic ingredient(s).

        Requires a real shared brand token; never matches on dosage-form words
        or loose character similarity alone.
        """
        normalized = normalize_item_name(item_name)
        if not normalized:
            return None

        exact_rows = self._by_normalized.get(normalized)
        if exact_rows:
            return self._payload(exact_rows[0])

        input_tokens = {
            tok for tok in normalized.split()
            if len(tok) >= 3 and tok not in NOISE_WORDS and not tok[0].isdigit()
        }
        if not input_tokens:
            return None

        candidates = self._candidate_rows(input_tokens)

        # Prefer the brand whose token set best overlaps the bill's brand tokens.
        best: tuple[float, int, AzBrandRow] | None = None
        for row in candidates:
            shared = input_tokens & row.name_tokens
            if not shared:
                continue
            # Require the principal (longest) bill token to be present, so e.g.
            # "Volini Gel" cannot match a random "... Gel" product.
            principal = max(input_tokens, key=len)
            if principal not in row.name_tokens:
                continue
            overlap = len(shared) / len(input_tokens | row.name_tokens)
            # Prefer fewer extra tokens (closer brand match).
            extra = len(row.name_tokens - input_tokens)
            score = overlap
            if best is None or (score, -extra) > (best[0], -best[1]):
                best = (score, extra, row)

        if best is not None:
            return self._payload(best[2])

        return None

    def _payload(self, row: AzBrandRow) -> dict[str, Any]:
        return {
            "brand_name": row.brand_name,
            "manufacturer": row.manufacturer,
            "generic_name": _extract_generic_from_composition(row.short_composition1),
            "generic_name_2": _extract_generic_from_composition(row.short_composition2),
            "ingredient_keys": list(row.ingredient_keys),
            "composition1": row.short_composition1,
            "composition2": row.short_composition2,
        }


class CombinedPharmaRatesStore:
    """NPPA ceiling prices with AZ brand-to-generic resolution fallback."""

    def __init__(self) -> None:
        self.nppa = NppaRatesStore(_default_nppa_csv_path())
        self.az: BrandToGenericStore | None = None
        az_path = _default_az_csv_path()
        if az_path:
            try:
                self.az = BrandToGenericStore(az_path)
            except Exception as exc:  # noqa: BLE001 - log and continue without AZ
                print(f"WARNING: AZ brand dataset failed to load: {exc}")

    @property
    def csv_path(self) -> Path:
        return self.nppa.csv_path

    @property
    def rows(self) -> list[NppaPriceRow]:
        return self.nppa.rows

    @property
    def primary(self):
        """Compatibility property for main.py startup logging."""
        return self.nppa

    @property
    def backup(self):
        """Compatibility property for main.py startup logging."""
        return self.az

    def find_match(self, item_name: str, *, quantity: float = 1.0) -> dict[str, Any] | None:
        """Direct NPPA match by ingredient; else resolve brand->generic via AZ and retry."""
        prefer_strength = _resolve_query_strength(item_name)
        prefer_form = _detect_form(item_name)

        # 1. Direct match: the bill already names the generic ingredient(s).
        match = self.nppa.match_keys(
            _ingredient_keys(item_name),
            prefer_strength=prefer_strength,
            prefer_form=prefer_form,
        )
        if match is not None:
            return match

        # 2. Resolve brand -> generic via AZ, then match the generic in NPPA.
        if self.az is None:
            return None

        resolution = self.az.resolve(item_name)
        if resolution is None:
            return None

        generic_keys = resolution.get("ingredient_keys") or []
        if not generic_keys:
            return None

        # The brand's own composition carries the strength when the bill text
        # only had a bare number (e.g. "Azithral 500" -> "Azithromycin (500mg)").
        if prefer_strength is None:
            comp_strength = _extract_strength_from_text(
                f"{resolution.get('composition1', '')} {resolution.get('composition2', '')}"
            )
            if comp_strength:
                prefer_strength = comp_strength[0]

        generic_match = self.nppa.match_keys(
            generic_keys,
            prefer_strength=prefer_strength,
            prefer_form=prefer_form,
        )
        # For combos, also try the primary ingredient alone as a fallback.
        if generic_match is None and len(generic_keys) > 1:
            generic_match = self.nppa.match_keys(
                generic_keys[:1],
                prefer_strength=prefer_strength,
                prefer_form=prefer_form,
            )

        if generic_match is None:
            return None

        generic_match["database"] = "nppa_via_az"
        generic_match["resolved_generic_name"] = resolution.get("generic_name")
        generic_match["resolved_from_brand"] = resolution.get("brand_name")
        return generic_match

    def compare_line_item(self, item: dict[str, Any]) -> dict[str, Any]:
        item_name = str(item.get("item_name", "")).strip()
        quantity = max(_to_float(item.get("quantity")), 0.0) or 1.0
        unit_price = max(_to_float(item.get("unit_price")), 0.0)
        total_price = _to_float(item.get("total_price"))
        if total_price <= 0 and quantity > 0 and unit_price > 0:
            total_price = round(quantity * unit_price, 2)

        match = self.find_match(item_name, quantity=quantity)
        enriched = dict(item)
        enriched["comparison_source"] = "pharma"

        if match is None:
            enriched["pharma_rate"] = None
            enriched["price_difference"] = None
            enriched["flag"] = "no_reference"
            enriched["matched_reference_item"] = None
            enriched["approximate_match"] = False
            enriched["pharma_product_id"] = None
            enriched["pharma_manufacturer"] = None
            enriched["pharma_pack_size"] = None
            enriched["pharma_price_basis"] = None
            enriched["pharma_database"] = None
            enriched["resolved_generic_name"] = None
            return enriched

        row: NppaPriceRow = match["_row"]
        ceiling_per_unit = row.ceiling_price_inr
        expected_total = round(ceiling_per_unit * quantity, 2)

        billed_amount = total_price if total_price > 0 else round(unit_price * quantity, 2)
        allowed = expected_total * (1 + PRICE_TOLERANCE)
        price_difference = round(billed_amount - expected_total, 2)

        enriched["pharma_rate"] = expected_total
        enriched["pharma_unit_reference"] = ceiling_per_unit
        enriched["price_difference"] = price_difference
        enriched["flag"] = "overpriced" if billed_amount > allowed else "acceptable"
        enriched["matched_reference_item"] = match["reference_item"]
        enriched["approximate_match"] = bool(match.get("approximate_match"))
        enriched["pharma_product_id"] = row.sl_no
        enriched["pharma_manufacturer"] = None
        enriched["pharma_pack_size"] = 1.0
        enriched["pharma_price_basis"] = "unit"
        enriched["pharma_database"] = match.get("database", "nppa")
        enriched["resolved_generic_name"] = match.get("resolved_generic_name")
        return enriched


_store: CombinedPharmaRatesStore | None = None


def get_pharma_store() -> CombinedPharmaRatesStore:
    global _store
    if _store is None:
        _store = CombinedPharmaRatesStore()
    return _store
