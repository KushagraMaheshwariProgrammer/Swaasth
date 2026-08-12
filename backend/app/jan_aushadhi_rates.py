"""Jan Aushadhi (PMBJP) subsidized medicine catalog matching."""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.pharma_rates import (
    MIN_INGREDIENT_KEY_LEN,
    ORAL_SOLID_FORMS,
    _detect_form,
    _extract_strength_from_text,
    _ingredient_keys,
    _resolve_query_strength,
    _to_float,
    _to_int,
    get_pharma_store,
)

# Jan Aushadhi catalog names often include pharmacopoeia markers (e.g. "Tablets IP").
_PHARMACOPOEIA_RE = re.compile(r"\bIP\b", re.IGNORECASE)


def _catalog_ingredient_keys(name: str) -> list[str]:
    normalized = _PHARMACOPOEIA_RE.sub(" ", name)
    return _ingredient_keys(normalized)


def _default_csv_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent
    env_path = os.getenv("JAN_AUSHADHI_DATASET_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"JAN_AUSHADHI_DATASET_PATH does not exist: {path}")

    candidates = [
        backend_root / "data" / "Jan_Aushadhi_Product_List.csv",
    ]
    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Jan Aushadhi product list not found. Place the CSV in backend/data/ "
        "or set JAN_AUSHADHI_DATASET_PATH."
    )


@dataclass(frozen=True)
class JanAushadhiRow:
    sr_no: int
    drug_code: str
    generic_name: str
    unit_size: str
    mrp_inr: float
    group_name: str
    ingredient_keys: tuple[str, ...]
    ingredient_set: frozenset[str]
    form: str | None
    strength_mg: float


class JanAushadhiRatesStore:
    """Loads and indexes Jan Aushadhi generic medicine catalog."""

    def __init__(self, csv_path: Path | None = None) -> None:
        path = csv_path or _default_csv_path()
        self.csv_path = path
        self.rows: list[JanAushadhiRow] = []
        self._by_core: dict[str, list[JanAushadhiRow]] = {}
        self._by_ingredient_set: dict[frozenset[str], list[JanAushadhiRow]] = {}
        self._by_single: dict[str, list[JanAushadhiRow]] = {}
        self._load(path)

    def _load(self, path: Path) -> None:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                generic_name = (raw.get("Generic Name") or "").strip()
                if not generic_name:
                    continue

                ing_keys = _catalog_ingredient_keys(generic_name)
                if not ing_keys:
                    continue

                strengths = _extract_strength_from_text(generic_name)
                row = JanAushadhiRow(
                    sr_no=_to_int(raw.get("Sr No")),
                    drug_code=(raw.get("Drug Code") or "").strip(),
                    generic_name=generic_name,
                    unit_size=(raw.get("Unit Size") or "").strip(),
                    mrp_inr=_to_float(raw.get("MRP")),
                    group_name=(raw.get("Group Name") or "").strip(),
                    ingredient_keys=tuple(ing_keys),
                    ingredient_set=frozenset(ing_keys),
                    form=_detect_form(generic_name),
                    strength_mg=strengths[0] if strengths else 0.0,
                )
                self.rows.append(row)

                core = "".join(ing_keys)
                self._by_core.setdefault(core, []).append(row)
                self._by_ingredient_set.setdefault(row.ingredient_set, []).append(row)
                for key in row.ingredient_set:
                    self._by_single.setdefault(key, []).append(row)

        if not self.rows:
            raise ValueError(f"No Jan Aushadhi rows loaded from {path}")

    def match_keys(
        self,
        ingredient_keys: list[str],
        *,
        prefer_strength: float | None = None,
        prefer_form: str | None = None,
    ) -> dict[str, Any] | None:
        keys = [k for k in ingredient_keys if len(k) >= MIN_INGREDIENT_KEY_LEN]
        if not keys:
            return None

        query_set = frozenset(keys)

        core_rows = self._by_core.get("".join(keys))
        if core_rows:
            return self._build(core_rows, False, prefer_strength, prefer_form)

        set_rows = self._by_ingredient_set.get(query_set)
        if set_rows:
            return self._build(set_rows, False, prefer_strength, prefer_form)

        if len(query_set) == 1:
            (only_key,) = tuple(query_set)
            rows = self._by_single.get(only_key)
            if rows:
                pure = [r for r in rows if r.ingredient_set == query_set]
                pool = pure if pure else rows
                return self._build(pool, not pure, prefer_strength, prefer_form)
            return None

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
        rows: list[JanAushadhiRow],
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
        rows: list[JanAushadhiRow],
        prefer_strength: float | None,
        prefer_form: str | None,
    ) -> JanAushadhiRow:
        if len(rows) == 1:
            return rows[0]

        def score(row: JanAushadhiRow) -> tuple[int, float]:
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

    def _payload(self, row: JanAushadhiRow, approximate: bool) -> dict[str, Any]:
        return {
            "generic_name": row.generic_name,
            "drug_code": row.drug_code,
            "unit_size": row.unit_size,
            "mrp_inr": row.mrp_inr,
            "group_name": row.group_name,
            "approximate_match": approximate,
            "_row": row,
        }

    def find_match(self, item_name: str) -> dict[str, Any] | None:
        prefer_strength = _resolve_query_strength(item_name)
        prefer_form = _detect_form(item_name)

        match = self.match_keys(
            _ingredient_keys(item_name),
            prefer_strength=prefer_strength,
            prefer_form=prefer_form,
        )
        if match is not None:
            return match

        try:
            pharma = get_pharma_store()
        except (FileNotFoundError, ValueError):
            return None

        if pharma.az is None:
            return None

        resolution = pharma.az.resolve(item_name)
        if resolution is None:
            return None

        generic_keys = resolution.get("ingredient_keys") or []
        if not generic_keys:
            return None

        if prefer_strength is None:
            comp_strength = _extract_strength_from_text(
                f"{resolution.get('composition1', '')} {resolution.get('composition2', '')}"
            )
            if comp_strength:
                prefer_strength = comp_strength[0]

        generic_match = self.match_keys(
            generic_keys,
            prefer_strength=prefer_strength,
            prefer_form=prefer_form,
        )
        if generic_match is None and len(generic_keys) > 1:
            generic_match = self.match_keys(
                generic_keys[:1],
                prefer_strength=prefer_strength,
                prefer_form=prefer_form,
            )

        if generic_match is None:
            return None

        generic_match["resolved_from_brand"] = resolution.get("brand_name")
        return generic_match

    def enrich_line_item(self, item: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(item)
        item_name = str(item.get("item_name", "")).strip()
        match = self.find_match(item_name)

        if match is None:
            enriched["jan_aushadhi_available"] = False
            enriched["jan_aushadhi_generic_name"] = None
            enriched["jan_aushadhi_mrp"] = None
            enriched["jan_aushadhi_unit_size"] = None
            enriched["jan_aushadhi_drug_code"] = None
            enriched["jan_aushadhi_approximate_match"] = False
            return enriched

        enriched["jan_aushadhi_available"] = True
        enriched["jan_aushadhi_generic_name"] = match["generic_name"]
        enriched["jan_aushadhi_mrp"] = match["mrp_inr"] if match["mrp_inr"] > 0 else None
        enriched["jan_aushadhi_unit_size"] = match["unit_size"]
        enriched["jan_aushadhi_drug_code"] = match["drug_code"]
        enriched["jan_aushadhi_approximate_match"] = bool(match.get("approximate_match"))
        if match.get("resolved_from_brand"):
            enriched["jan_aushadhi_resolved_from_brand"] = match["resolved_from_brand"]
        return enriched


def build_jan_aushadhi_summary(line_items: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [
        {
            "bill_item_name": item.get("item_name"),
            "generic_name": item.get("jan_aushadhi_generic_name"),
            "mrp": item.get("jan_aushadhi_mrp"),
            "unit_size": item.get("jan_aushadhi_unit_size"),
            "drug_code": item.get("jan_aushadhi_drug_code"),
            "approximate_match": item.get("jan_aushadhi_approximate_match", False),
            "resolved_from_brand": item.get("jan_aushadhi_resolved_from_brand"),
        }
        for item in line_items
        if item.get("jan_aushadhi_available")
    ]
    return {
        "matches_count": len(matches),
        "matches": matches,
        "scheme_name": "Pradhan Mantri Bhartiya Janaushadhi Pariyojana (PMBJP)",
        "advisory": (
            "These Jan Aushadhi catalogue prices are listed for discussion with "
            "your prescriber or pharmacist. They are not a recommendation to "
            "substitute a prescribed brand. Ask whether a generic equivalent is "
            "appropriate for your case before changing any medicine."
        ),
    }


_store: JanAushadhiRatesStore | None = None


def get_jan_aushadhi_store() -> JanAushadhiRatesStore:
    global _store
    if _store is None:
        _store = JanAushadhiRatesStore()
    return _store


def enrich_line_items_with_jan_aushadhi(
    line_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    try:
        store = get_jan_aushadhi_store()
    except (FileNotFoundError, ValueError) as exc:
        return line_items, {"error": str(exc), "matches_count": 0, "matches": []}

    enriched = [
        store.enrich_line_item(item)
        if item.get("category") == "medicine"
        or item.get("comparison_source") == "pharma"
        else item
        for item in line_items
    ]
    summary = build_jan_aushadhi_summary(enriched)
    return enriched, summary
