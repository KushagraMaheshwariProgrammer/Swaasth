"""CGHS city-wise costs from cleaned production CSV."""

from __future__ import annotations

import csv
import logging
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.cghs_rates import normalize_item_name

logger = logging.getLogger(__name__)

HOSPITAL_STRONG_MATCH = 0.84
HOSPITAL_CANDIDATE_MATCH = 0.52
SYNONYM_STRONG_MATCH = 0.78
LIMITED_CITY_ROW_THRESHOLD = 200

SOURCE_FILE = "cghs_all_cities_cleaned_for_app.csv"
CITY_COSTS_SOURCE_LABEL = "CGHS city-wise costs CSV"
CITY_COSTS_SOURCE_DISPLAY = "CGHS city-wise costs data"

EXTRA_CITY_ALIASES: dict[str, tuple[str, tuple[str, ...]]] = {
    "kanpur and gwalior": ("Kanpur and Gwalior", ("Kanpur", "Gwalior")),
}

GENERIC_PHARMACY_EXACT = frozenset(
    {
        "pharmacy",
        "medicines",
        "medicine",
        "medicine charges",
        "drug charges",
        "drugs",
        "pharmaceuticals",
        "pharmaceutical charges",
    }
)

CGHS_BILL_SYNONYMS: list[dict[str, Any]] = [
    {
        "patterns": (
            "consultation",
            "consultations",
            "doctor consultation",
            "consultation charges",
            "consultation charge",
            "opd consultation",
            "consultation fees",
            "consultation fee",
        ),
        "terms": (
            "consultation opd",
            "consultation for inpatients",
            "consultation ipd",
            "specialist consultation",
            "opd consultation",
        ),
    },
    {
        "patterns": (
            "room rent",
            "room rent general ward",
            "room charges",
            "ward charges",
            "general ward",
            "ward rent",
        ),
        "terms": (
            "room rent general ward",
            "new room rent general ward",
            "room rent semi private ward",
            "room rent private ward",
            "room rent",
            "general ward",
            "room charges",
            "ward charges",
        ),
    },
    {
        "patterns": (
            "laboratory investigations",
            "laboratory investigation",
            "lab tests",
            "lab test",
            "laboratory",
            "pathology",
            "investigation charges",
            "investigations",
        ),
        "terms": (
            "laboratory",
            "investigation",
            "lab test",
            "pathology",
        ),
    },
    {
        "patterns": (
            "medical equipment",
            "equipment charges",
            "consumables",
            "medical consumables",
            "disposable",
            "disposables",
        ),
        "terms": (
            "consumables",
            "medical consumables",
            "equipment",
            "disposable",
        ),
    },
]


def _dev_logging_enabled() -> bool:
    return os.getenv("ENV", "").lower() in {"dev", "development", "local"} or os.getenv(
        "RAJIV_AAROGYASRI_DEBUG", ""
    ).lower() in {"1", "true", "yes"}


def format_rate_type_display(rate_type: str | None) -> str | None:
    if not rate_type:
        return None
    mapping = {
        "nabh": "NABH",
        "non_nabh": "Non-NABH",
        "cghs": "CGHS Rate",
    }
    return mapping.get(str(rate_type).strip().lower(), str(rate_type))


def build_city_costs_source_fields(
    *,
    city: str,
    source_page: str,
    source_pdf: str,
) -> dict[str, Any]:
    return {
        "source_label": CITY_COSTS_SOURCE_LABEL,
        "source_display": CITY_COSTS_SOURCE_DISPLAY,
        "source_city": city,
        "source_page": source_page.strip() if source_page else None,
        "source_file_internal": source_pdf.strip() if source_pdf else None,
    }


def _parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def _parse_rate(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    try:
        amount = float(text)
        return amount if amount > 0 else 0.0
    except ValueError:
        return 0.0


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _is_generic_pharmacy_item(normalized_name: str) -> bool:
    if not normalized_name:
        return False
    if normalized_name in GENERIC_PHARMACY_EXACT:
        return True
    tokens = normalized_name.split()
    return len(tokens) <= 2 and tokens[0] == "pharmacy"


def _pattern_matches_bill_item(normalized_bill: str, pattern: str) -> bool:
    if not normalized_bill or not pattern:
        return False
    if normalized_bill == pattern:
        return True
    if pattern in normalized_bill or normalized_bill in pattern:
        return True
    pattern_tokens = pattern.split()
    bill_tokens = normalized_bill.split()
    if pattern_tokens and all(token in bill_tokens for token in pattern_tokens):
        return True
    return False


def build_search_terms(item_name: str) -> list[str]:
    normalized = normalize_item_name(item_name)
    terms: list[str] = []
    if normalized:
        terms.append(normalized)

    for group in CGHS_BILL_SYNONYMS:
        if any(
            _pattern_matches_bill_item(normalized, pattern)
            for pattern in group["patterns"]
        ):
            for term in group["terms"]:
                normalized_term = normalize_item_name(term)
                if normalized_term and normalized_term not in terms:
                    terms.append(normalized_term)

    return terms


@dataclass(frozen=True)
class CghsCostRow:
    city: str
    source_pdf: str
    source_page: str
    procedure_name: str
    nabh_rate: float
    non_nabh_rate: float
    cghs_rate: float
    rate_type: str
    remarks: str
    extraction_method: str
    quality_status: str
    normalized_procedure: str
    procedure_tokens: frozenset[str]


def _default_csv_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent
    path = (
        backend_root
        / "data"
        / "CGHS costs"
        / "converted_csv"
        / "cghs_all_cities_cleaned_for_app.csv"
    )
    if not path.exists():
        raise FileNotFoundError(f"CGHS cleaned costs CSV not found: {path}")
    return path


def _build_city_alias_index() -> dict[str, str]:
    alias_to_city: dict[str, str] = {}
    try:
        from app.cghs_covered_cities import get_cghs_covered_cities_store

        for city in get_cghs_covered_cities_store().cities:
            canonical = city.city_display_name.strip()
            alias_to_city[_normalize_key(canonical)] = canonical
            for alias in city.aliases:
                alias_to_city[_normalize_key(alias)] = canonical
    except Exception as exc:
        logger.warning("CGHS covered cities unavailable for alias map: %s", exc)

    for canonical_key, (canonical, aliases) in EXTRA_CITY_ALIASES.items():
        alias_to_city[canonical_key] = canonical
        for alias in aliases:
            alias_to_city[_normalize_key(alias)] = canonical
    return alias_to_city


class CghsCostsStore:
    def __init__(self, csv_path: Path | None = None) -> None:
        path = csv_path or _default_csv_path()
        self.csv_path = path
        self.rows: list[CghsCostRow] = []
        self._by_city: dict[str, list[CghsCostRow]] = {}
        self._by_city_token: dict[str, dict[str, list[CghsCostRow]]] = {}
        self._city_alias = _build_city_alias_index()
        self._load(path)

    def _load(self, path: Path) -> None:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fieldnames = {name.strip().lower() for name in (reader.fieldnames or [])}
            required = {"city", "procedure_name"}
            if not required.issubset(fieldnames):
                raise ValueError(
                    f"CGHS cleaned CSV missing required columns. Found: {reader.fieldnames}"
                )

            for raw in reader:
                if _parse_bool(raw.get("needs_manual_review")):
                    continue
                procedure = str(
                    raw.get("procedure_name") or raw.get("procedure") or ""
                ).strip()
                if not procedure:
                    continue

                city = str(raw.get("city") or raw.get("city_folder") or "").strip()
                if not city:
                    continue

                nabh_rate = _parse_rate(raw.get("nabh_rate"))
                non_nabh_rate = _parse_rate(raw.get("non_nabh_rate"))
                cghs_rate = _parse_rate(raw.get("cghs_rate"))
                if not any((nabh_rate, non_nabh_rate, cghs_rate)):
                    continue

                normalized = normalize_item_name(procedure)
                row = CghsCostRow(
                    city=city,
                    source_pdf=str(raw.get("source_pdf", "")).strip(),
                    source_page=str(raw.get("source_page", "")).strip(),
                    procedure_name=procedure,
                    nabh_rate=nabh_rate,
                    non_nabh_rate=non_nabh_rate,
                    cghs_rate=cghs_rate,
                    rate_type=str(raw.get("rate_type", "")).strip().lower(),
                    remarks=str(raw.get("remarks", "")).strip(),
                    extraction_method=str(raw.get("extraction_method", "")).strip().lower(),
                    quality_status=str(raw.get("quality_status", "")).strip().lower(),
                    normalized_procedure=normalized,
                    procedure_tokens=frozenset(
                        token for token in normalized.split() if len(token) >= 3
                    ),
                )
                self.rows.append(row)
                self._by_city.setdefault(city, []).append(row)
                city_tokens = self._by_city_token.setdefault(city, {})
                for token in row.procedure_tokens:
                    city_tokens.setdefault(token, []).append(row)

        if not self.rows:
            raise ValueError(f"No usable CGHS cost rows loaded from {path}")

        logger.info(
            "Loaded %d CGHS city-wise cost rows across %d cities from cleaned CSV: %s",
            len(self.rows),
            len(self._by_city),
            path.name,
        )
        if _dev_logging_enabled():
            logger.info(
                "CGHS city-wise match loaded from cleaned CSV: %s",
                SOURCE_FILE,
            )

    @property
    def cities(self) -> list[str]:
        return sorted(self._by_city.keys())

    def normalize_city(self, city: str | None) -> str | None:
        if not city or not str(city).strip():
            return None
        key = _normalize_key(city)
        if key in self._city_alias:
            return self._city_alias[key]
        for canonical in self._by_city:
            if _normalize_key(canonical) == key:
                return canonical
        return None

    def city_row_count(self, city: str | None) -> int:
        canonical = self.normalize_city(city)
        if not canonical:
            return 0
        return len(self._by_city.get(canonical, []))

    def city_has_limited_data(self, city: str | None) -> bool:
        count = self.city_row_count(city)
        return 0 < count < LIMITED_CITY_ROW_THRESHOLD

    def select_rate(
        self,
        row: CghsCostRow,
        *,
        nabh_accredited: bool,
        hospital_type: str = "general",
    ) -> tuple[float, str]:
        if hospital_type == "speciality" and row.nabh_rate > 0:
            return row.nabh_rate, "nabh"
        if nabh_accredited and row.nabh_rate > 0:
            return row.nabh_rate, "nabh"
        if row.non_nabh_rate > 0:
            return row.non_nabh_rate, "non_nabh"
        if row.nabh_rate > 0:
            return row.nabh_rate, "nabh"
        if row.cghs_rate > 0:
            return row.cghs_rate, "cghs"
        return 0.0, ""

    def _candidate_rows(
        self, normalized_name: str, city_rows: list[CghsCostRow]
    ) -> list[CghsCostRow]:
        tokens = [token for token in normalized_name.split() if len(token) >= 3]
        if not tokens:
            return city_rows[:400]

        canonical_city = city_rows[0].city if city_rows else ""
        token_index = self._by_city_token.get(canonical_city, {})
        seen: set[int] = set()
        candidates: list[CghsCostRow] = []
        city_ids = {id(row) for row in city_rows}

        for token in tokens:
            for row in token_index.get(token, ()):
                if id(row) not in city_ids or id(row) in seen:
                    continue
                seen.add(id(row))
                candidates.append(row)
                if len(candidates) >= 500:
                    return candidates
        return candidates if candidates else city_rows[:400]

    def _top_fuzzy_candidates(
        self,
        normalized_name: str,
        city_rows: list[CghsCostRow],
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        candidate_rows = self._candidate_rows(normalized_name, city_rows)
        input_tokens = set(normalized_name.split())
        scored: list[tuple[float, CghsCostRow]] = []
        for row in candidate_rows:
            ref_tokens = row.procedure_tokens
            if not ref_tokens or not input_tokens:
                continue
            overlap = len(input_tokens & ref_tokens) / len(input_tokens | ref_tokens)
            sequence = SequenceMatcher(None, normalized_name, row.normalized_procedure).ratio()
            score = (0.6 * overlap) + (0.4 * sequence)
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "procedure_name": row.procedure_name,
                "score": round(score, 3),
            }
            for score, row in scored[:limit]
            if score >= 0.35
        ]

    def _match_term_in_city(
        self,
        normalized_term: str,
        city_rows: list[CghsCostRow],
        *,
        canonical_city: str,
        nabh_accredited: bool,
        hospital_type: str,
        from_synonym: bool,
    ) -> dict[str, Any] | None:
        exact_index = {row.normalized_procedure: row for row in city_rows}
        if normalized_term in exact_index:
            return self._match_payload(
                exact_index[normalized_term],
                canonical_city,
                nabh_accredited=nabh_accredited,
                hospital_type=hospital_type,
                confidence=1.0,
                match_reason="Exact normalized match",
                approximate=False,
                searched_term=normalized_term,
            )

        candidate_rows = self._candidate_rows(normalized_term, city_rows)
        for row in candidate_rows:
            ref = row.normalized_procedure
            if ref in normalized_term or normalized_term in ref:
                return self._match_payload(
                    row,
                    canonical_city,
                    nabh_accredited=nabh_accredited,
                    hospital_type=hospital_type,
                    confidence=0.92 if from_synonym else 0.9,
                    match_reason="Synonym match" if from_synonym else "Contains match",
                    approximate=False,
                    searched_term=normalized_term,
                )

        input_tokens = set(normalized_term.split())
        best: tuple[float, CghsCostRow] | None = None
        for row in candidate_rows:
            ref_tokens = row.procedure_tokens
            if not ref_tokens or not input_tokens:
                continue
            overlap = len(input_tokens & ref_tokens) / len(input_tokens | ref_tokens)
            sequence = SequenceMatcher(None, normalized_term, row.normalized_procedure).ratio()
            score = (0.6 * overlap) + (0.4 * sequence)
            if best is None or score > best[0]:
                best = (score, row)

        threshold = SYNONYM_STRONG_MATCH if from_synonym else HOSPITAL_CANDIDATE_MATCH
        if best and best[0] >= threshold:
            approximate = best[0] < HOSPITAL_STRONG_MATCH
            return self._match_payload(
                best[1],
                canonical_city,
                nabh_accredited=nabh_accredited,
                hospital_type=hospital_type,
                confidence=round(best[0], 3),
                match_reason="Synonym fuzzy match"
                if from_synonym
                else ("Fuzzy match" if approximate else "Strong fuzzy match"),
                approximate=approximate,
                searched_term=normalized_term,
            )
        return None

    def find_match(
        self,
        item_name: str,
        *,
        city: str | None,
        nabh_accredited: bool = False,
        hospital_type: str = "general",
    ) -> dict[str, Any] | None:
        match, _debug = self.find_match_detailed(
            item_name,
            city=city,
            nabh_accredited=nabh_accredited,
            hospital_type=hospital_type,
        )
        return match

    def find_match_detailed(
        self,
        item_name: str,
        *,
        city: str | None,
        nabh_accredited: bool = False,
        hospital_type: str = "general",
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        normalized_bill = normalize_item_name(item_name)
        search_terms = build_search_terms(item_name)
        canonical_city = self.normalize_city(city)

        debug: dict[str, Any] = {
            "patient_city": city,
            "normalized_city": canonical_city,
            "city_rows_count": self.city_row_count(city),
            "searched_terms": search_terms,
            "city_wise_attempted": False,
            "city_wise_match_found": False,
            "city_wise_top_matches": [],
            "fallback_used": False,
            "fallback_reason": None,
            "special_handling": None,
        }

        if _is_generic_pharmacy_item(normalized_bill):
            debug["special_handling"] = "generic_pharmacy"
            debug["fallback_reason"] = (
                "Generic pharmacy charge — verify against medicine price/NPPA where applicable."
            )
            return None, debug

        if not canonical_city:
            debug["fallback_reason"] = "Patient city missing or not mapped to CGHS city data."
            return None, debug

        city_rows = self._by_city.get(canonical_city, [])
        debug["city_wise_attempted"] = True
        if not city_rows:
            debug["fallback_reason"] = f"No city-wise rows loaded for {canonical_city}."
            return None, debug

        primary_term = search_terms[0] if search_terms else normalized_bill
        synonym_terms = search_terms[1:] if len(search_terms) > 1 else []

        if primary_term:
            match = self._match_term_in_city(
                primary_term,
                city_rows,
                canonical_city=canonical_city,
                nabh_accredited=nabh_accredited,
                hospital_type=hospital_type,
                from_synonym=False,
            )
            if match:
                debug["city_wise_match_found"] = True
                if _dev_logging_enabled():
                    logger.info(
                        "CGHS city-wise match loaded from cleaned CSV: %s city=%s item=%r term=%r -> %r @ %s",
                        SOURCE_FILE,
                        canonical_city,
                        item_name,
                        primary_term,
                        match.get("matched_procedure_name"),
                        match.get("selected_rate"),
                    )
                return match, debug

        for term in synonym_terms:
            match = self._match_term_in_city(
                term,
                city_rows,
                canonical_city=canonical_city,
                nabh_accredited=nabh_accredited,
                hospital_type=hospital_type,
                from_synonym=True,
            )
            if match:
                debug["city_wise_match_found"] = True
                if _dev_logging_enabled():
                    logger.info(
                        "CGHS city-wise match loaded from cleaned CSV: %s city=%s item=%r term=%r -> %r @ %s",
                        SOURCE_FILE,
                        canonical_city,
                        item_name,
                        term,
                        match.get("matched_procedure_name"),
                        match.get("selected_rate"),
                    )
                return match, debug

        debug["city_wise_top_matches"] = self._top_fuzzy_candidates(
            primary_term or normalized_bill,
            city_rows,
        )
        debug["fallback_reason"] = (
            "No city-wise CGHS cost match for searched terms in "
            f"{canonical_city} ({len(city_rows)} rows available)."
        )
        if _dev_logging_enabled():
            logger.info(
                "CGHS city miss: city=%s item=%r terms=%s top=%s",
                canonical_city,
                item_name,
                search_terms,
                debug["city_wise_top_matches"],
            )
        return None, debug

    def _match_payload(
        self,
        row: CghsCostRow,
        city: str,
        *,
        nabh_accredited: bool,
        hospital_type: str,
        confidence: float,
        match_reason: str,
        approximate: bool,
        searched_term: str,
    ) -> dict[str, Any] | None:
        selected_rate, rate_type_used = self.select_rate(
            row,
            nabh_accredited=nabh_accredited,
            hospital_type=hospital_type,
        )
        if selected_rate <= 0:
            return None
        return {
            "city": city,
            "matched_procedure_name": row.procedure_name,
            "selected_rate": selected_rate,
            "rate_type_used": rate_type_used,
            "rate_type_display": format_rate_type_display(rate_type_used),
            "nabh_rate": row.nabh_rate,
            "non_nabh_rate": row.non_nabh_rate,
            "cghs_rate": row.cghs_rate,
            "source_pdf": row.source_pdf,
            "source_page": row.source_page,
            "extraction_method": row.extraction_method,
            "quality_status": row.quality_status,
            "confidence_score": confidence,
            "match_reason": match_reason,
            "approximate_match": approximate,
            "remarks": row.remarks,
            "searched_term": searched_term,
            **build_city_costs_source_fields(
                city=city,
                source_page=row.source_page,
                source_pdf=row.source_pdf,
            ),
        }


_store: CghsCostsStore | None = None
_store_failed = False


def get_cghs_costs_store() -> CghsCostsStore | None:
    global _store, _store_failed
    if _store_failed:
        return None
    if _store is None:
        try:
            _store = CghsCostsStore()
            if _dev_logging_enabled():
                logger.info(
                    "CGHS city-wise match loaded from cleaned CSV: %s path=%s rows=%d cities=%d",
                    SOURCE_FILE,
                    _store.csv_path,
                    len(_store.rows),
                    len(_store.cities),
                )
        except Exception as exc:
            _store_failed = True
            logger.warning("CGHS city-wise costs unavailable: %s", exc)
            return None
    return _store


def _comparison_source_label(compared_item: dict[str, Any]) -> str:
    if compared_item.get("cghs_generic_pharmacy"):
        return "Verify medicine pricing"
    if compared_item.get("comparison_source") == "cghs_city_costs":
        return "City-wise CGHS costs"
    if compared_item.get("comparison_source") == "cghs" and compared_item.get("cghs_rate") is not None:
        return "Existing CGHS fallback"
    return "Manual verification"


def _comparison_status_label(compared_item: dict[str, Any]) -> str:
    if compared_item.get("cghs_generic_pharmacy"):
        return "Verify Medicine Pricing"
    if compared_item.get("comparison_source") == "cghs_city_costs":
        return "City-wise CGHS Match"
    if compared_item.get("comparison_source") == "cghs" and compared_item.get("cghs_rate") is not None:
        return "Existing CGHS Fallback Used"
    return "Manual Verification Required"


def _comparison_detail_text(compared_item: dict[str, Any]) -> str:
    if compared_item.get("cghs_generic_pharmacy"):
        return (
            "Generic pharmacy charge detected. "
            "Verify medicine-wise pricing/NPPA where applicable."
        )
    if compared_item.get("comparison_source") == "cghs_city_costs":
        return "Matched from CGHS city-wise costs data."
    if compared_item.get("comparison_source") == "cghs" and compared_item.get("cghs_rate") is not None:
        return (
            "City-wise CGHS cost not matched. Existing CGHS fallback rate used."
        )
    return (
        "CGHS rate not found in city-wise or fallback data — manual verification required."
    )


def build_cghs_costs_report(
    *,
    enabled: bool,
    patient_city: str | None,
    hospital_type: str,
    nabh_accredited: bool,
    line_items: list[dict[str, Any]],
    compared_line_items: list[dict[str, Any]] | None = None,
    include_debug: bool = False,
) -> dict[str, Any] | None:
    if not enabled:
        return None

    store = get_cghs_costs_store()
    city_used = store.normalize_city(patient_city) if store else None
    city_rows_count = store.city_row_count(city_used) if store and city_used else 0
    city_data_available = bool(city_used and city_rows_count > 0)
    limited_city_data = bool(store and city_used and store.city_has_limited_data(city_used))

    comparisons: list[dict[str, Any]] = []
    advisories: list[str] = []
    debug_items: list[dict[str, Any]] = []
    any_city_match = False
    any_fallback = False
    any_manual = False
    any_pharmacy = False

    compared = compared_line_items or line_items
    for index, item in enumerate(line_items):
        bill_item_name = str(item.get("item_name", "")).strip()
        charged_amount = _parse_rate(item.get("total_price"))
        compared_item = compared[index] if index < len(compared) else {}
        source = str(compared_item.get("comparison_source", ""))

        if compared_item.get("cghs_match_debug"):
            debug_items.append(
                {
                    "bill_item_name": bill_item_name,
                    **compared_item["cghs_match_debug"],
                }
            )

        if compared_item.get("cghs_generic_pharmacy"):
            any_pharmacy = True
            comparisons.append(
                {
                    "bill_item_name": bill_item_name,
                    "charged_amount": charged_amount,
                    "matched_procedure_name": None,
                    "selected_rate": None,
                    "rate_type_used": None,
                    "rate_type_display": None,
                    "nabh_rate": None,
                    "non_nabh_rate": None,
                    "source_page": None,
                    "extraction_method": None,
                    "quality_status": None,
                    "confidence_score": None,
                    "match_reason": compared_item.get("cghs_costs_match_reason"),
                    "excess_amount": None,
                    "status": "Verify Medicine Pricing",
                    "source_label": "Verify medicine pricing",
                    "source_display": "Verify medicine pricing",
                    "source_city": None,
                    "source_file_internal": None,
                    "detail_text": _comparison_detail_text(compared_item),
                    "fallback_used": False,
                    "generic_pharmacy": True,
                }
            )
            continue

        if source == "cghs_city_costs":
            any_city_match = True
            selected_rate = _parse_rate(compared_item.get("cghs_rate"))
            excess = round(max(charged_amount - selected_rate, 0.0), 2) if selected_rate else None
            status = (
                "Within CGHS City Rate"
                if selected_rate and charged_amount <= selected_rate
                else "Excess Over CGHS City Rate"
                if selected_rate
                else "Manual Verification Required"
            )
            source_fields = build_city_costs_source_fields(
                city=str(
                    compared_item.get("cghs_costs_source_city")
                    or city_used
                    or ""
                ),
                source_page=str(compared_item.get("cghs_costs_source_page") or ""),
                source_pdf=str(compared_item.get("cghs_costs_source_pdf") or ""),
            )
            comparisons.append(
                {
                    "bill_item_name": bill_item_name,
                    "charged_amount": charged_amount,
                    "matched_procedure_name": compared_item.get("matched_reference_item"),
                    "selected_rate": selected_rate,
                    "rate_type_used": compared_item.get("cghs_costs_rate_type"),
                    "rate_type_display": compared_item.get("cghs_costs_rate_type_display")
                    or format_rate_type_display(compared_item.get("cghs_costs_rate_type")),
                    "nabh_rate": compared_item.get("nabh_rate"),
                    "non_nabh_rate": compared_item.get("non_nabh_rate"),
                    "source_page": source_fields["source_page"],
                    "extraction_method": compared_item.get("cghs_costs_extraction_method"),
                    "quality_status": compared_item.get("cghs_costs_quality_status"),
                    "confidence_score": compared_item.get("cghs_costs_confidence"),
                    "match_reason": compared_item.get("cghs_costs_match_reason"),
                    "excess_amount": excess,
                    "status": status,
                    "source_label": source_fields["source_label"],
                    "source_display": source_fields["source_display"],
                    "source_city": source_fields["source_city"],
                    "source_file_internal": source_fields["source_file_internal"],
                    "detail_text": _comparison_detail_text(compared_item),
                    "fallback_used": False,
                    "generic_pharmacy": False,
                }
            )
            continue

        if source == "cghs" and compared_item.get("cghs_rate") is not None:
            any_fallback = True
            selected_rate = _parse_rate(compared_item.get("cghs_rate"))
            excess = round(max(charged_amount - selected_rate, 0.0), 2)
            comparisons.append(
                {
                    "bill_item_name": bill_item_name,
                    "charged_amount": charged_amount,
                    "matched_procedure_name": compared_item.get("matched_reference_item"),
                    "selected_rate": selected_rate,
                    "rate_type_used": compared_item.get("rate_type"),
                    "rate_type_display": format_rate_type_display(
                        compared_item.get("rate_type")
                    ),
                    "nabh_rate": compared_item.get("nabh_rate"),
                    "non_nabh_rate": compared_item.get("non_nabh_rate"),
                    "source_page": None,
                    "extraction_method": "tier_cghs",
                    "quality_status": "clean",
                    "confidence_score": None,
                    "match_reason": compared_item.get("cghs_costs_match_reason")
                    or "Existing CGHS fallback rate used",
                    "excess_amount": excess,
                    "status": "Existing CGHS Fallback Used",
                    "source_label": "Existing CGHS fallback",
                    "source_display": "Existing CGHS fallback",
                    "source_city": None,
                    "source_file_internal": None,
                    "detail_text": _comparison_detail_text(compared_item),
                    "fallback_used": True,
                    "generic_pharmacy": False,
                }
            )
            continue

        any_manual = True
        comparisons.append(
            {
                "bill_item_name": bill_item_name,
                "charged_amount": charged_amount,
                "matched_procedure_name": None,
                "selected_rate": None,
                "rate_type_used": None,
                "rate_type_display": None,
                "nabh_rate": None,
                "non_nabh_rate": None,
                "source_page": None,
                "extraction_method": None,
                "quality_status": None,
                "confidence_score": None,
                "match_reason": compared_item.get("cghs_costs_match_reason")
                or "No CGHS city-wise or tier fallback rate found",
                "excess_amount": None,
                "status": "Manual Verification Required",
                "source_label": "Manual verification",
                "source_display": "Manual verification required",
                "source_city": None,
                "source_file_internal": None,
                "detail_text": _comparison_detail_text(compared_item),
                "fallback_used": False,
                "generic_pharmacy": False,
            }
        )

    if store is None:
        advisories.append(
            "CGHS city-wise costs file unavailable. Existing CGHS fallback used."
        )
    elif city_data_available:
        advisories.append(
            f"CGHS city-wise cost data searched for {city_used} "
            f"({city_rows_count} clean rows)."
        )
    elif patient_city:
        advisories.append(
            "No city-wise CGHS cost data found for this location. "
            "Existing CGHS fallback/manual verification may be required."
        )

    if limited_city_data:
        advisories.append(
            "City-wise CGHS cost data for this city may be limited. "
            "Existing CGHS fallback/manual verification may be required."
        )

    if any_fallback:
        advisories.append("Existing CGHS fallback rate used for some items.")

    if any_manual:
        advisories.append(
            "CGHS rate not found for some items — manual verification required."
        )

    if any_pharmacy:
        advisories.append(
            "Generic pharmacy charge detected on bill. Verify medicine-wise pricing/NPPA where applicable."
        )

    ocr_items = [
        row
        for row in comparisons
        if row.get("extraction_method") == "ocr" and not row.get("fallback_used")
    ]
    if ocr_items:
        advisories.append(
            "OCR-extracted CGHS cost row used for some matches. Verify if needed."
        )

    report: dict[str, Any] = {
        "enabled": True,
        "data_source_file": SOURCE_FILE,
        "data_source_display": CITY_COSTS_SOURCE_DISPLAY,
        "source_file": SOURCE_FILE,
        "city_used": city_used or patient_city,
        "city_rows_count": city_rows_count,
        "city_data_available": city_data_available,
        "limited_city_data": limited_city_data,
        "match_found": any_city_match,
        "fallback_used": any_fallback,
        "manual_verification_required": any_manual,
        "comparisons": comparisons,
        "advisories": advisories,
    }
    if include_debug:
        report["match_debug"] = debug_items
    return report
