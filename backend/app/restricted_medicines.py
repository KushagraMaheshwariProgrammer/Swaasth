"""Restricted / controlled medicine detection against a backend CSV catalog."""

from __future__ import annotations

import csv
import logging
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.services.legal_guardrails import sanitize_text, sanitize_value

logger = logging.getLogger(__name__)

MIN_MATCH_LEN = 4
EXACT_CONFIDENCE = 0.97
STRONG_FUZZY_CONFIDENCE = 0.9
MEDIUM_FUZZY_CONFIDENCE = 0.85
MIN_FUZZY_RATIO = 0.88

ADVISORY = "A medicine on this document matches the restricted medicines list."
DISCLAIMER = "OCR-based check only · not medical advice."
MANUAL_VERIFICATION_NOTE = ""

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "medicine_name": ("medicine_name", "medicine name", "name", "drug_name", "drug name"),
    "generic_name": ("generic_name", "generic name", "generic"),
    "aliases": ("aliases", "alias", "alternate_names", "alternate names"),
    "brand_names": ("brand_names", "brand names", "brands", "brand"),
    "restriction_type": ("restriction_type", "restriction type", "type"),
    "schedule_or_category": (
        "schedule_or_category",
        "schedule or category",
        "schedule",
        "category",
    ),
    "reason": ("reason",),
    "severity": ("severity", "risk"),
    "source": ("source",),
    "notes": ("notes", "note"),
}

_OCR_NOISE_RE = re.compile(
    r"\b(tablet|tablets|tab|capsule|capsules|cap|syrup|injection|inj|mg|ml|gm|g|ip)\b",
    re.IGNORECASE,
)
_STRENGTH_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|ml|gm|g|mcg|iu|%)\b", re.IGNORECASE)


def _default_csv_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent
    env_path = os.getenv("RESTRICTED_MEDICINES_DATASET_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return backend_root / "data" / "medicines" / "restricted_medicines.csv"


def normalize_medicine_text(text: str) -> str:
    """Normalize medicine names and OCR text for comparison."""
    normalized = (text or "").lower().strip()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = _STRENGTH_RE.sub(" ", normalized)
    normalized = _OCR_NOISE_RE.sub(" ", normalized)
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = re.sub(r"(.)\1{2,}", r"\1\1", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _split_multi_values(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[|,;]+", value)
    return [part.strip() for part in parts if part.strip()]


def _resolve_column(raw: dict[str, str], canonical: str) -> str:
    lowered = {key.strip().lower(): value for key, value in raw.items()}
    for alias in _COLUMN_ALIASES.get(canonical, (canonical,)):
        if alias in lowered:
            return (lowered[alias] or "").strip()
    return ""


@dataclass(frozen=True)
class RestrictedMedicineRow:
    medicine_name: str
    generic_name: str
    aliases: tuple[str, ...]
    brand_names: tuple[str, ...]
    restriction_type: str
    schedule_or_category: str
    reason: str
    severity: str
    source: str
    notes: str
    search_terms: tuple[str, ...]


class RestrictedMedicinesStore:
    """Loads restricted medicine catalog from CSV."""

    def __init__(self, csv_path: Path | None = None) -> None:
        path = csv_path or _default_csv_path()
        self.csv_path = path
        self.rows: list[RestrictedMedicineRow] = []
        self._load(path)

    def _load(self, path: Path) -> None:
        if not path.exists():
            logger.warning(
                "Restricted medicines CSV not found at %s — restricted medicine checks disabled.",
                path,
            )
            return

        seen_names: set[str] = set()
        try:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    logger.warning("Restricted medicines CSV has no header row: %s", path)
                    return

                for raw in reader:
                    if not any(str(value or "").strip() for value in raw.values()):
                        continue

                    medicine_name = _resolve_column(raw, "medicine_name")
                    if not medicine_name:
                        continue

                    dedupe_key = normalize_medicine_text(medicine_name)
                    if dedupe_key in seen_names:
                        continue
                    seen_names.add(dedupe_key)

                    generic_name = _resolve_column(raw, "generic_name") or medicine_name
                    aliases = _split_multi_values(_resolve_column(raw, "aliases"))
                    brand_names = _split_multi_values(_resolve_column(raw, "brand_names"))

                    terms: list[str] = []
                    for term in [medicine_name, generic_name, *aliases, *brand_names]:
                        cleaned = normalize_medicine_text(term)
                        if cleaned and cleaned not in terms:
                            terms.append(cleaned)

                    self.rows.append(
                        RestrictedMedicineRow(
                            medicine_name=medicine_name,
                            generic_name=generic_name,
                            aliases=tuple(aliases),
                            brand_names=tuple(brand_names),
                            restriction_type=_resolve_column(raw, "restriction_type"),
                            schedule_or_category=_resolve_column(
                                raw, "schedule_or_category"
                            ),
                            reason=_resolve_column(raw, "reason"),
                            severity=_resolve_column(raw, "severity") or "Medium",
                            source=_resolve_column(raw, "source"),
                            notes=_resolve_column(raw, "notes"),
                            search_terms=tuple(terms),
                        )
                    )
        except UnicodeDecodeError:
            logger.warning(
                "Restricted medicines CSV encoding error at %s — checks disabled.",
                path,
            )
        except OSError as exc:
            logger.warning(
                "Could not read restricted medicines CSV at %s: %s",
                path,
                exc,
            )

        if path.exists() and not self.rows:
            logger.warning("No restricted medicine rows loaded from %s", path)

    def is_available(self) -> bool:
        return bool(self.rows)


def _word_boundary_match(normalized_haystack: str, term: str) -> bool:
    if not term:
        return False
    if len(term) < MIN_MATCH_LEN:
        return re.search(rf"\b{re.escape(term)}\b", normalized_haystack) is not None
    padded = f" {normalized_haystack} "
    return f" {term} " in padded


def _fuzzy_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _best_fuzzy_in_text(normalized_text: str, term: str) -> tuple[float, str]:
    if len(term) < MIN_MATCH_LEN:
        return 0.0, ""

    best_score = 0.0
    best_text = ""
    for line in normalized_text.splitlines():
        line = line.strip()
        if not line:
            continue
        score = _fuzzy_ratio(term, normalize_medicine_text(line))
        if score > best_score:
            best_score = score
            best_text = line

    words = normalized_text.split()
    for index in range(len(words)):
        for size in (1, 2, 3):
            if index + size > len(words):
                continue
            phrase = " ".join(words[index : index + size])
            if len(phrase) < MIN_MATCH_LEN:
                continue
            score = _fuzzy_ratio(term, phrase)
            if score > best_score:
                best_score = score
                best_text = phrase

    return best_score, best_text


def _match_term_against_item(
    term: str,
    item_text: str,
    *,
    field_label: str,
) -> dict[str, Any] | None:
    normalized_item = normalize_medicine_text(item_text)
    if not normalized_item or not term:
        return None

    if normalized_item == term:
        return {
            "confidence_score": EXACT_CONFIDENCE,
            "match_reason": f"Exact match on extracted {field_label}",
            "detected_text": item_text.strip(),
            "matched_alias_or_brand": term,
        }

    if _word_boundary_match(normalized_item, term):
        return {
            "confidence_score": EXACT_CONFIDENCE,
            "match_reason": f"Exact match on extracted {field_label}",
            "detected_text": item_text.strip(),
            "matched_alias_or_brand": term,
        }

    if len(term) >= MIN_MATCH_LEN:
        ratio = _fuzzy_ratio(term, normalized_item)
        if ratio >= MIN_FUZZY_RATIO:
            confidence = STRONG_FUZZY_CONFIDENCE if ratio >= 0.92 else MEDIUM_FUZZY_CONFIDENCE
            return {
                "confidence_score": round(confidence, 2),
                "match_reason": f"Fuzzy match on extracted {field_label}",
                "detected_text": item_text.strip(),
                "matched_alias_or_brand": term,
            }

    return None


def _match_term_in_ocr(normalized_ocr: str, term: str, original_ocr: str) -> dict[str, Any] | None:
    if not normalized_ocr or not term:
        return None

    if _word_boundary_match(normalized_ocr, term):
        detected = _extract_detected_snippet(original_ocr, term)
        return {
            "confidence_score": EXACT_CONFIDENCE,
            "match_reason": "Exact match in OCR text",
            "detected_text": detected or term,
            "matched_alias_or_brand": term,
        }

    if len(term) >= MIN_MATCH_LEN:
        ratio, detected = _best_fuzzy_in_text(normalized_ocr, term)
        if ratio >= MIN_FUZZY_RATIO:
            confidence = STRONG_FUZZY_CONFIDENCE if ratio >= 0.92 else MEDIUM_FUZZY_CONFIDENCE
            return {
                "confidence_score": round(confidence, 2),
                "match_reason": "Fuzzy match in OCR text",
                "detected_text": detected or term,
                "matched_alias_or_brand": term,
            }

    return None


def _extract_detected_snippet(original_ocr: str, term: str) -> str:
    if not original_ocr:
        return term
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    match = pattern.search(original_ocr)
    if match:
        start = max(0, match.start() - 20)
        end = min(len(original_ocr), match.end() + 20)
        return original_ocr[start:end].strip()
    return term


def _extract_item_names(items: list[dict[str, Any]] | None) -> list[str]:
    names: list[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("item_name") or item.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def _medicine_items_from_line_items(
    line_items: list[dict[str, Any]] | None,
) -> list[str]:
    names: list[str] = []
    for item in line_items or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip().lower()
        comparison_source = str(item.get("comparison_source") or "").strip().lower()
        if category not in {"medicine", "drug"} and comparison_source != "pharma":
            continue
        name = str(item.get("item_name") or item.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def match_restricted_medicines(
    ocr_text: str | None,
    extracted_items: list[dict[str, Any]] | None = None,
    *,
    store: RestrictedMedicinesStore | None = None,
) -> list[dict[str, Any]]:
    active_store = store or get_restricted_medicines_store()
    if not active_store.is_available():
        return []

    normalized_ocr = normalize_medicine_text(ocr_text or "")
    item_names = _extract_item_names(extracted_items)
    flags: list[dict[str, Any]] = []
    seen_medicines: set[str] = set()

    for row in active_store.rows:
        best_match: dict[str, Any] | None = None

        for term in row.search_terms:
            for item_name in item_names:
                item_match = _match_term_against_item(
                    term,
                    item_name,
                    field_label="item name",
                )
                if item_match and (
                    best_match is None
                    or item_match["confidence_score"] > best_match["confidence_score"]
                ):
                    best_match = {
                        **item_match,
                        "matched_medicine_name": row.medicine_name,
                        "generic_name": row.generic_name,
                        "restriction_type": row.restriction_type,
                        "schedule_or_category": row.schedule_or_category,
                        "reason": row.reason,
                        "severity": row.severity,
                        "source": row.source,
                        "notes": row.notes,
                    }

            ocr_match = _match_term_in_ocr(normalized_ocr, term, ocr_text or "")
            if ocr_match and (
                best_match is None
                or ocr_match["confidence_score"] > best_match["confidence_score"]
            ):
                best_match = {
                    **ocr_match,
                    "matched_medicine_name": row.medicine_name,
                    "generic_name": row.generic_name,
                    "restriction_type": row.restriction_type,
                    "schedule_or_category": row.schedule_or_category,
                    "reason": row.reason,
                    "severity": row.severity,
                    "source": row.source,
                    "notes": row.notes,
                }

        if best_match is None:
            continue

        dedupe_key = normalize_medicine_text(row.medicine_name)
        if dedupe_key in seen_medicines:
            continue
        seen_medicines.add(dedupe_key)
        flags.append(best_match)

    flags.sort(key=lambda item: item.get("confidence_score", 0), reverse=True)
    return flags


def build_restricted_medicine_flags(
    *,
    ocr_text: str | None = None,
    line_items: list[dict[str, Any]] | None = None,
    prescription_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    medicine_line_items = [
        {"item_name": name, "category": "medicine"}
        for name in _medicine_items_from_line_items(line_items)
    ]
    if not medicine_line_items and line_items:
        medicine_line_items = [
            item
            for item in line_items
            if str(item.get("category", "")).strip().lower() in {"medicine", "drug", "other", ""}
        ]

    extracted_items = list(prescription_items or []) + medicine_line_items
    flags = match_restricted_medicines(ocr_text, extracted_items)

    detected = bool(flags)
    return {
        "detected": detected,
        "flags": sanitize_value(flags),
        "advisory": sanitize_text(ADVISORY) if detected else "",
        "disclaimer": sanitize_text(DISCLAIMER),
        "manual_verification_note": sanitize_text(MANUAL_VERIFICATION_NOTE) if detected else "",
    }


_store: RestrictedMedicinesStore | None = None


def get_restricted_medicines_store() -> RestrictedMedicinesStore:
    global _store
    if _store is None:
        _store = RestrictedMedicinesStore()
    return _store


def render_restricted_medicine_flags_html(report: dict[str, Any]) -> str:
    """Render restricted medicine flags as HTML for PDF reports."""
    from html import escape

    flags_payload = report.get("restricted_medicine_flags") or {}
    flags = flags_payload.get("flags") or []
    if not flags:
        return ""

    rows = []
    for flag in flags:
        confidence = flag.get("confidence_score")
        confidence_text = (
            f"{round(float(confidence) * 100)}%"
            if confidence is not None
            else "—"
        )
        rows.append(
            "<tr>"
            f"<td>{escape(str(flag.get('detected_text', '')))}</td>"
            f"<td>{escape(str(flag.get('matched_medicine_name', '')))}</td>"
            f"<td>{escape(str(flag.get('generic_name') or '—'))}</td>"
            f"<td>{escape(str(flag.get('restriction_type') or '—'))}</td>"
            f"<td>{escape(str(flag.get('schedule_or_category') or '—'))}</td>"
            f"<td>{escape(str(flag.get('reason') or '—'))}</td>"
            f"<td>{escape(str(flag.get('severity') or '—'))}</td>"
            f"<td>{escape(confidence_text)}</td>"
            f"<td>{escape(str(flag.get('match_reason') or '—'))}</td>"
            f"<td>{escape(str(flag.get('source') or '—'))}</td>"
            "</tr>"
        )

    advisory = escape(str(flags_payload.get("advisory") or ADVISORY))
    disclaimer = escape(str(flags_payload.get("disclaimer") or DISCLAIMER))

    return (
        "<h2>Restricted Medicines Check</h2>"
        f"<p>{advisory}</p>"
        "<table><tr>"
        "<th>Detected text</th><th>Matched medicine</th><th>Generic</th>"
        "<th>Restriction type</th><th>Schedule</th><th>Reason</th>"
        "<th>Severity</th><th>Confidence</th><th>Match reason</th><th>Source</th>"
        "</tr>"
        f"{''.join(rows)}"
        "</table>"
        f"<p class='disclaimer'>{disclaimer}</p>"
    )
