"""Indian pharmaceutical reference prices (primary + backup Kaggle datasets)."""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

from app.cghs_rates import normalize_item_name

PRICE_TOLERANCE = float(os.getenv("PHARMA_PRICE_TOLERANCE", "0.15"))
FUZZY_MATCH_THRESHOLD = 0.58
BACKUP_FUZZY_MATCH_THRESHOLD = 0.50

DatabaseLabel = Literal["primary", "backup"]


@dataclass(frozen=True)
class PharmaProductRow:
    product_id: int
    brand_name: str
    manufacturer: str
    price_inr: float
    is_discontinued: bool
    dosage_form: str
    pack_size: float
    pack_unit: str
    primary_ingredient: str
    normalized_name: str
    name_tokens: frozenset[str]
    database: DatabaseLabel


def _to_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _parse_bool(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def _parse_pack_size_label(label: str) -> float:
    if not label:
        return 1.0
    match = re.search(r"(\d+(?:\.\d+)?)", label.lower())
    if match:
        return max(_to_float(match.group(1)), 1.0)
    return 1.0


def _resolve_pack_size(raw: dict[str, str]) -> float:
    explicit = _to_float(raw.get("pack_size"))
    if explicit > 0:
        return explicit
    return _parse_pack_size_label(
        (raw.get("pack_size_label") or raw.get("packaging_raw") or "").strip()
    )


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


def _default_primary_csv_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent
    env_path = os.getenv("PHARMA_DATASET_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"PHARMA_DATASET_PATH does not exist: {path}")

    candidates = [
        backend_root / "data" / "indian_pharmaceutical_products.csv",
        backend_root / "data" / "indian_pharmaceutical_products_clean.csv",
        _kaggle_cache_csv(
            ("rishgeeky", "indian-pharmaceutical-products"),
            "indian_pharmaceutical_products_clean.csv",
        ),
    ]
    for path in candidates:
        if path and path.exists():
            return path

    raise FileNotFoundError(
        "Primary pharmaceutical dataset not found. Run: "
        "python backend/scripts/download_pharma_dataset.py"
    )


def _default_backup_csv_path() -> Path | None:
    backend_root = Path(__file__).resolve().parent.parent
    env_path = os.getenv("PHARMA_BACKUP_DATASET_PATH", "").strip()
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
    ]
    for path in candidates:
        if path and path.exists():
            return path
    return None


def _reference_unit_price(row: PharmaProductRow) -> tuple[float, str]:
    pack_price = row.price_inr
    pack_size = max(row.pack_size, 1.0)
    per_unit = round(pack_price / pack_size, 2)
    return pack_price, per_unit


def _pick_billed_reference(
    *,
    unit_price: float,
    total_price: float,
    quantity: float,
    pack_price: float,
    per_unit_price: float,
) -> tuple[float, str]:
    if unit_price <= 0 and quantity > 0 and total_price > 0:
        unit_price = round(total_price / quantity, 2)

    if unit_price <= 0:
        return pack_price, "pack"

    candidates: list[tuple[float, str]] = [(pack_price, "pack"), (per_unit_price, "unit")]
    best = min(
        candidates,
        key=lambda entry: abs(unit_price - entry[0]) / max(entry[0], 0.01),
    )
    return best


def _expected_total(
    *,
    quantity: float,
    pack_price: float,
    pack_size: float,
    basis: str,
) -> float:
    if quantity <= 0:
        return pack_price
    if basis == "unit":
        return round((pack_price / max(pack_size, 1.0)) * quantity, 2)
    packs = max(1.0, quantity / max(pack_size, 1.0)) if pack_size > 1 else quantity
    if packs <= 1.5 and quantity <= pack_size:
        return round(pack_price * max(quantity / max(pack_size, 1.0), 1.0), 2)
    return round(pack_price * packs, 2)


class PharmaRatesStore:
    def __init__(
        self,
        csv_path: Path,
        *,
        database: DatabaseLabel,
        id_offset: int = 0,
        fuzzy_threshold: float = FUZZY_MATCH_THRESHOLD,
    ) -> None:
        self.csv_path = csv_path
        self.database = database
        self.id_offset = id_offset
        self.fuzzy_threshold = fuzzy_threshold
        self.rows: list[PharmaProductRow] = []
        self._by_normalized: dict[str, list[PharmaProductRow]] = {}
        self._by_token: dict[str, list[PharmaProductRow]] = {}
        self._load(csv_path)

    def _load(self, path: Path) -> None:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                brand = (raw.get("brand_name") or raw.get("name") or "").strip()
                if not brand:
                    continue

                normalized = normalize_item_name(brand)
                raw_id = _to_int(raw.get("product_id") or raw.get("id"))
                row = PharmaProductRow(
                    product_id=self.id_offset + raw_id,
                    brand_name=brand,
                    manufacturer=(
                        raw.get("manufacturer")
                        or raw.get("manufacturer_name")
                        or ""
                    ).strip(),
                    price_inr=_to_float(
                        raw.get("price_inr") or raw.get("price(₹)") or raw.get("price")
                    ),
                    is_discontinued=_parse_bool(
                        raw.get("is_discontinued") or raw.get("Is_discontinued")
                    ),
                    dosage_form=(raw.get("dosage_form") or raw.get("type") or "").strip(),
                    pack_size=_resolve_pack_size(raw),
                    pack_unit=(raw.get("pack_unit") or "").strip(),
                    primary_ingredient=(
                        raw.get("primary_ingredient") or raw.get("short_composition1") or ""
                    ).strip(),
                    normalized_name=normalized,
                    name_tokens=frozenset(normalized.split()),
                    database=self.database,
                )
                if row.price_inr <= 0:
                    continue
                self.rows.append(row)
                self._by_normalized.setdefault(normalized, []).append(row)
                for token in row.name_tokens:
                    if len(token) >= 3:
                        self._by_token.setdefault(token, []).append(row)

        if not self.rows:
            raise ValueError(f"No pharmaceutical rows loaded from {path}")

    def _candidate_rows(self, normalized_name: str) -> list[PharmaProductRow]:
        tokens = [token for token in normalized_name.split() if len(token) >= 3]
        if not tokens:
            return []

        seen: set[int] = set()
        candidates: list[PharmaProductRow] = []
        for token in tokens:
            for row in self._by_token.get(token, ()):
                if row.product_id in seen:
                    continue
                seen.add(row.product_id)
                candidates.append(row)
        return candidates

    def find_match(self, item_name: str, *, quantity: float = 1.0) -> dict[str, Any] | None:
        normalized_name = normalize_item_name(item_name)
        if not normalized_name:
            return None

        exact_rows = self._by_normalized.get(normalized_name)
        if exact_rows:
            return self._match_payload(
                self._best_pack_match(exact_rows, quantity), approximate=False
            )

        candidates = self._candidate_rows(normalized_name)
        substring_matches: list[PharmaProductRow] = []
        for row in candidates:
            ref = row.normalized_name
            if ref in normalized_name or normalized_name in ref:
                substring_matches.append(row)
        if substring_matches:
            return self._match_payload(
                self._best_pack_match(substring_matches[:40], quantity),
                approximate=False,
            )

        input_tokens = set(normalized_name.split())
        best: tuple[float, PharmaProductRow] | None = None
        for row in candidates[:800]:
            ref_tokens = row.name_tokens
            if not ref_tokens or not input_tokens:
                continue
            overlap_score = len(input_tokens & ref_tokens) / len(input_tokens | ref_tokens)
            sequence_score = SequenceMatcher(None, normalized_name, row.normalized_name).ratio()
            score = (0.65 * overlap_score) + (0.35 * sequence_score)
            if best is None or score > best[0]:
                best = (score, row)

        if best and best[0] >= self.fuzzy_threshold:
            return self._match_payload(best[1], approximate=True)

        return None

    def _best_pack_match(
        self, rows: list[PharmaProductRow], quantity: float
    ) -> PharmaProductRow:
        if len(rows) == 1:
            return rows[0]
        if quantity <= 0:
            return rows[0]
        return min(rows, key=lambda row: abs(row.pack_size - quantity))

    def _match_payload(
        self, row: PharmaProductRow, *, approximate: bool
    ) -> dict[str, Any]:
        pack_price, per_unit_price = _reference_unit_price(row)
        return {
            "reference_item": row.brand_name,
            "rate": pack_price,
            "per_unit_rate": per_unit_price,
            "product_id": row.product_id,
            "manufacturer": row.manufacturer,
            "pack_size": row.pack_size,
            "approximate_match": approximate,
            "database": row.database,
            "_row": row,
        }


class CombinedPharmaRatesStore:
    """Primary Indian pharmaceutical DB with AZ dataset as fallback."""

    BACKUP_ID_OFFSET = 1_000_000_000

    def __init__(self) -> None:
        self.primary = PharmaRatesStore(
            _default_primary_csv_path(), database="primary"
        )
        self.backup: PharmaRatesStore | None = None
        backup_path = _default_backup_csv_path()
        if backup_path:
            try:
                self.backup = PharmaRatesStore(
                    backup_path,
                    database="backup",
                    id_offset=self.BACKUP_ID_OFFSET,
                    fuzzy_threshold=BACKUP_FUZZY_MATCH_THRESHOLD,
                )
            except ValueError as exc:
                print(f"WARNING: Backup pharmaceutical dataset failed: {exc}")

    @property
    def csv_path(self) -> Path:
        return self.primary.csv_path

    @property
    def rows(self) -> list[PharmaProductRow]:
        combined = list(self.primary.rows)
        if self.backup:
            combined.extend(self.backup.rows)
        return combined

    def find_match(self, item_name: str, *, quantity: float = 1.0) -> dict[str, Any] | None:
        """Try primary DB first; fall back to AZ dataset when primary has no match."""
        match = self.primary.find_match(item_name, quantity=quantity)
        if match is not None:
            return match
        if self.backup is None:
            return None
        return self.backup.find_match(item_name, quantity=quantity)

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
            return enriched

        row: PharmaProductRow = match["_row"]
        pack_price, per_unit_price = _reference_unit_price(row)
        reference_value, basis = _pick_billed_reference(
            unit_price=unit_price,
            total_price=total_price,
            quantity=quantity,
            pack_price=pack_price,
            per_unit_price=per_unit_price,
        )
        expected_total = _expected_total(
            quantity=quantity,
            pack_price=pack_price,
            pack_size=row.pack_size,
            basis=basis,
        )
        billed_amount = total_price if total_price > 0 else round(reference_value * quantity, 2)
        allowed = expected_total * (1 + PRICE_TOLERANCE)
        price_difference = round(billed_amount - expected_total, 2)

        enriched["pharma_rate"] = round(expected_total, 2)
        enriched["pharma_unit_reference"] = round(reference_value, 2)
        enriched["price_difference"] = price_difference
        enriched["flag"] = "overpriced" if billed_amount > allowed else "acceptable"
        enriched["matched_reference_item"] = row.brand_name
        enriched["approximate_match"] = bool(match.get("approximate_match"))
        enriched["pharma_product_id"] = row.product_id
        enriched["pharma_manufacturer"] = row.manufacturer
        enriched["pharma_pack_size"] = row.pack_size
        enriched["pharma_price_basis"] = basis
        enriched["pharma_is_discontinued"] = row.is_discontinued
        enriched["pharma_database"] = match.get("database", row.database)
        return enriched


_store: CombinedPharmaRatesStore | None = None


def get_pharma_store() -> CombinedPharmaRatesStore:
    global _store
    if _store is None:
        _store = CombinedPharmaRatesStore()
    return _store
