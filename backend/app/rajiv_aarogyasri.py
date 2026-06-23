"""Rajiv Aarogyasri / Aarogyasri Cheyutha scheme data layer and report builder."""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import time
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _BACKEND_ROOT / "data" / "aarogyasri_June2026"

HOSPITAL_STRONG_MATCH = 0.82
HOSPITAL_CANDIDATE_MATCH = 0.55
PACKAGE_STRONG_MATCH = 0.72
PACKAGE_CANDIDATE_MATCH = 0.50
MIN_MATCH_TOKEN_LEN = 4
MAX_PACKAGE_SEARCH_TERMS = 15
PACKAGE_MATCH_TIME_BUDGET_SEC = 3.0
MAX_PACKAGE_CANDIDATES = 200

AAROGYASRI_MATCH_FAILED_ADVISORY = (
    "Aarogyasri package matching failed. CGHS fallback is shown as a general benchmark."
)

DISCLAIMER = (
    "This report is based on OCR-extracted bill data and available Rajiv "
    "Aarogyasri package/hospital data in the app. OCR errors, package "
    "conditions, exclusions, hospital empanelment status, and final "
    "eligibility must be verified with the Aarogyasri Trust, official "
    "portal, or concerned hospital helpdesk."
)

_STRIP_TOKENS = frozenset(
    {
        "hospital",
        "hospitals",
        "hosp",
        "medical",
        "med",
        "centre",
        "center",
        "clinic",
        "institute",
        "inst",
        "pvt",
        "ltd",
        "llp",
        "trust",
        "hyderabad",
        "telangana",
        "and",
        "the",
        "of",
        "a",
        "private",
        "limited",
        "care",
        "nursing",
        "home",
    }
)

_OLD_CITY_HOSPITALS = frozenset(
    {
        "owaisi hospital",
        "princess esra hospital",
    }
)

_CANCER_KEYWORDS = frozenset(
    {
        "cancer",
        "oncology",
        "chemotherapy",
        "chemo",
        "radiotherapy",
        "radiation",
        "tumor",
        "tumour",
        "malignancy",
        "carcinoma",
    }
)

_OLD_CITY_HOSPITAL_PHRASES = (
    "owaisi hospital",
    "owaisi hospital and research centre",
    "princess esra hospital",
    "old city",
    "hyderabad old city",
)

_HOSPITAL_NOT_FOUND_STATUS = (
    "Hospital not found in Rajiv Aarogyasri empanelled hospital data — "
    "manual verification required."
)

_PACKAGE_NOT_MATCHED_MESSAGE = (
    "Aarogyasri package was not matched from OCR/package data. "
    "CGHS fallback is shown only as a general benchmark."
)

def _dev_logging_enabled() -> bool:
    return os.getenv("ENV", "").lower() in {"dev", "development", "local"} or os.getenv(
        "RAJIV_AAROGYASRI_DEBUG", ""
    ).lower() in {"1", "true", "yes"}


_CODE_COLUMN_ALIASES = frozenset(
    {"code", "package code", "procedure code", "surgery code"}
)
_NAME_COLUMN_ALIASES = frozenset(
    {
        "procedure",
        "package name",
        "procedure name",
        "therapy name",
        "name",
        "system",
    }
)
_SPECIALTY_COLUMN_ALIASES = frozenset(
    {"speciality", "specialty", "specialities", "category"}
)
_RATE_COLUMN_ALIASES = frozenset(
    {
        "rate",
        "amount",
        "package amount",
        "approved rate",
        "package type",
    }
)
_HOSPITAL_NAME_ALIASES = frozenset({"hospital name", "hospital", "name"})
_DISTRICT_ALIASES = frozenset({"district"})
_CITY_ALIASES = frozenset({"city", "municipality", "mandal"})
_STATE_ALIASES = frozenset({"state"})
_HOSPITAL_TYPE_ALIASES = frozenset({"hospital type", "type"})
_EMPANELLED_ALIASES = frozenset(
    {"empanelled status", "empanelment status", "status", "empanelled"}
)
_ALIAS_COLUMN_ALIASES = frozenset({"aliases", "alias"})


def _clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_key(header: str) -> str:
    return _clean_spaces(re.sub(r"[^a-z0-9 ]+", " ", (header or "").lower()))


def _pick_column(headers: list[str], aliases: frozenset[str]) -> str | None:
    normalized = {_normalize_key(header): header for header in headers}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    for header in headers:
        key = _normalize_key(header)
        if any(alias in key for alias in aliases):
            return header
    return None


def _parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if not text or text in {".", "-", "-."}:
        return None
    try:
        amount = float(text)
    except ValueError:
        return None
    return amount if amount >= 0 else None


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching."""
    normalized = (text or "").lower().strip()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = _clean_spaces(normalized)
    normalized = re.sub(r"(.)\1{2,}", r"\1\1", normalized)
    tokens = [token for token in normalized.split() if token not in _STRIP_TOKENS]
    return _clean_spaces(" ".join(tokens))


def build_aliases(name: str, extra_aliases: Iterable[str] | None = None) -> set[str]:
    """Build alternate match keys from a display name."""
    aliases: set[str] = set()
    raw = _clean_spaces(name)
    if not raw:
        return aliases

    aliases.add(normalize_text(raw))

    no_punct = _clean_spaces(re.sub(r"[^a-zA-Z0-9 ]+", " ", raw))
    if no_punct:
        aliases.add(normalize_text(no_punct))

    words = [word for word in no_punct.split() if word.lower() not in _STRIP_TOKENS]
    if words:
        aliases.add(normalize_text(" ".join(words)))
        if len(words) >= 2:
            initials = "".join(word[0].lower() for word in words if word)
            if len(initials) >= 4:
                aliases.add(initials)

    if extra_aliases:
        for alias in extra_aliases:
            cleaned = _clean_spaces(str(alias))
            if cleaned:
                aliases.add(normalize_text(cleaned))

    aliases.discard("")
    return aliases


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    formats = (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    match = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", text)
    if match:
        day, month, year = match.groups()
        year = year if len(year) == 4 else f"20{year}"
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
class AarogyasriHospitalRecord:
    hospital_name: str
    hospital_type: str
    district: str
    city: str
    state: str
    empanelled_status: str
    specialities: str
    aliases: frozenset[str] = frozenset()
    normalized_name: str = ""
    tokens: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "normalized_name",
            normalize_text(self.hospital_name),
        )
        object.__setattr__(
            self,
            "tokens",
            frozenset(token for token in self.normalized_name.split() if len(token) >= 3),
        )


@dataclass(frozen=True)
class AarogyasriPackageRecord:
    package_code: str
    package_name: str
    specialty: str
    approved_rate: float
    source_file: str
    aliases: frozenset[str] = frozenset()
    normalized_name: str = ""
    tokens: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "normalized_name",
            normalize_text(self.package_name),
        )
        object.__setattr__(
            self,
            "tokens",
            frozenset(
                token
                for token in self.normalized_name.split()
                if len(token) >= MIN_MATCH_TOKEN_LEN
            ),
        )


def _meaningful_tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize_text(text).split()
        if len(token) >= MIN_MATCH_TOKEN_LEN
    }


def _package_score_boost(query_norm: str, record: AarogyasriPackageRecord, base: float) -> float:
    boosted = base
    if "chemotherapy" in query_norm or "chemo" in query_norm.split():
        if "chemotherapy" in record.normalized_name or "chemo" in record.normalized_name:
            boosted += 0.15
    if "carcinoma" in query_norm and "lung" in query_norm:
        specialty_norm = normalize_text(record.specialty)
        if "lung" in specialty_norm or "lung" in record.normalized_name:
            boosted += 0.08
    return min(boosted, 1.0)


class RajivAarogyasriStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or _DATA_DIR
        self.hospitals: list[AarogyasriHospitalRecord] = []
        self.packages: list[AarogyasriPackageRecord] = []
        self.manifest: list[dict[str, Any]] = []
        self._hospital_alias_index: dict[str, list[AarogyasriHospitalRecord]] = {}
        self._package_alias_index: dict[str, list[AarogyasriPackageRecord]] = {}
        self._package_by_token: dict[str, list[AarogyasriPackageRecord]] = {}
        self._load()
        self._build_package_token_index()

    def _discover_package_files(self) -> list[Path]:
        patterns = (
            "CURRENT PROCEDURES*.csv",
            "FOLLOW-UP PACKAGES*.csv",
        )
        files: list[Path] = []
        for pattern in patterns:
            files.extend(sorted(self.data_dir.glob(pattern)))
        return files

    def _load_manifest(self) -> None:
        manifest_path = self.data_dir / "manifest.json"
        if not manifest_path.exists():
            logger.warning("Rajiv Aarogyasri manifest.json not found at %s", manifest_path)
            return
        try:
            self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Could not parse Rajiv Aarogyasri manifest.json: %s", exc)

    def _load_hospitals(self) -> None:
        matches = sorted(self.data_dir.glob("Rajiv_Aarogyasri_Hospitals*.csv"))
        if not matches:
            logger.warning("No Rajiv Aarogyasri hospital CSV found in %s", self.data_dir)
            return

        path = matches[0]
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            name_col = _pick_column(headers, _HOSPITAL_NAME_ALIASES)
            district_col = _pick_column(headers, _DISTRICT_ALIASES)
            city_col = _pick_column(headers, _CITY_ALIASES)
            state_col = _pick_column(headers, _STATE_ALIASES)
            type_col = _pick_column(headers, _HOSPITAL_TYPE_ALIASES)
            empanelled_col = _pick_column(headers, _EMPANELLED_ALIASES)
            speciality_col = _pick_column(headers, _SPECIALTY_COLUMN_ALIASES)
            alias_col = _pick_column(headers, _ALIAS_COLUMN_ALIASES)

            if not name_col:
                logger.warning("Hospital CSV missing hospital name column: %s", path.name)
                return

            for row in reader:
                name = _clean_spaces(row.get(name_col, ""))
                if not name:
                    continue
                extra_aliases = []
                if alias_col:
                    extra_aliases = [
                        part.strip()
                        for part in re.split(r"[;|]", row.get(alias_col, ""))
                        if part.strip()
                    ]
                record = AarogyasriHospitalRecord(
                    hospital_name=name,
                    hospital_type=_clean_spaces(row.get(type_col or "", "")),
                    district=_clean_spaces(row.get(district_col or "", "")),
                    city=_clean_spaces(row.get(city_col or "", "")),
                    state=_clean_spaces(row.get(state_col or "", "Telangana")) or "Telangana",
                    empanelled_status=_clean_spaces(row.get(empanelled_col or "", ""))
                    or "Active",
                    specialities=_clean_spaces(row.get(speciality_col or "", "")),
                    aliases=frozenset(build_aliases(name, extra_aliases)),
                )
                self.hospitals.append(record)
                for alias in record.aliases:
                    self._hospital_alias_index.setdefault(alias, []).append(record)

        logger.info("Loaded %d Rajiv Aarogyasri hospitals from %s", len(self.hospitals), path.name)

    def _load_packages_from_file(self, path: Path) -> None:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            try:
                header_row = next(reader)
            except StopIteration:
                return

            headers = [cell.strip() for cell in header_row]
            code_col = _pick_column(headers, _CODE_COLUMN_ALIASES)
            name_col = _pick_column(headers, _NAME_COLUMN_ALIASES)
            specialty_col = _pick_column(headers, _SPECIALTY_COLUMN_ALIASES)
            rate_col = None
            if "CURRENT PROCEDURES" in path.name.upper():
                rate_col = _pick_column(headers, frozenset({"package type"}))
            if not rate_col:
                rate_col = _pick_column(headers, frozenset({"package amount", "rate", "amount", "approved rate"}))
            if not rate_col:
                rate_col = _pick_column(headers, _RATE_COLUMN_ALIASES)

            if not name_col:
                logger.warning("Package CSV missing procedure/name column: %s", path.name)
                return
            if not rate_col:
                logger.warning("Package CSV missing rate column: %s", path.name)
                return

            if _dev_logging_enabled():
                logger.info(
                    "Rajiv Aarogyasri package CSV headers (%s): %s | mapped code=%s name=%s specialty=%s rate=%s",
                    path.name,
                    headers,
                    code_col,
                    name_col,
                    specialty_col,
                    rate_col,
                )

            # Skip secondary header row when present in current procedure files.
            peek = next(reader, None)
            if peek is not None:
                peek_joined = " ".join(cell.lower() for cell in peek)
                if "icd code" in peek_joined or "surgery code" in peek_joined:
                    data_rows = reader
                else:
                    data_rows = iter([peek, *reader])
            else:
                data_rows = iter([])

            header_index = {header: idx for idx, header in enumerate(headers)}

            def cell(row: list[str], column: str | None) -> str:
                if not column or column not in header_index:
                    return ""
                idx = header_index[column]
                return row[idx].strip() if idx < len(row) else ""

            loaded = 0
            for row in data_rows:
                if not any(cell.strip() for cell in row):
                    continue
                package_name = cell(row, name_col)
                if not package_name:
                    continue
                approved_rate = _parse_amount(cell(row, rate_col))
                if approved_rate is None and rate_col != headers[-1]:
                    approved_rate = _parse_amount(row[-1] if row else None)
                if approved_rate is None:
                    continue

                package_code = cell(row, code_col) if code_col else ""
                specialty = cell(row, specialty_col) if specialty_col else ""
                record = AarogyasriPackageRecord(
                    package_code=package_code,
                    package_name=package_name,
                    specialty=specialty,
                    approved_rate=approved_rate,
                    source_file=path.name,
                    aliases=frozenset(build_aliases(package_name)),
                )
                self.packages.append(record)
                for alias in record.aliases:
                    self._package_alias_index.setdefault(alias, []).append(record)
                loaded += 1

            logger.info("Loaded %d Rajiv Aarogyasri packages from %s", loaded, path.name)

    def _load_packages(self) -> None:
        discovered = self._discover_package_files()
        if _dev_logging_enabled():
            logger.info(
                "Rajiv Aarogyasri CSV folder: %s | package files found: %s",
                self.data_dir,
                [path.name for path in discovered],
            )
        for path in discovered:
            try:
                self._load_packages_from_file(path)
            except Exception as exc:
                logger.exception(
                    "Failed to load Rajiv Aarogyasri package CSV %s: %s",
                    path.name,
                    exc,
                )

    def _build_package_token_index(self) -> None:
        self._package_by_token = {}
        for record in self.packages:
            for token in _meaningful_tokens(record.package_name):
                self._package_by_token.setdefault(token, []).append(record)
            if record.specialty:
                for token in _meaningful_tokens(record.specialty):
                    self._package_by_token.setdefault(token, []).append(record)

    def _package_records_for_query(self, query: str) -> list[AarogyasriPackageRecord]:
        query_norm = normalize_text(query)
        if not query_norm:
            return []

        candidates: dict[int, AarogyasriPackageRecord] = {}
        for record in self._package_alias_index.get(query_norm, []):
            candidates[id(record)] = record

        for alias in build_aliases(query):
            for record in self._package_alias_index.get(alias, []):
                candidates[id(record)] = record

        query_tokens = _meaningful_tokens(query)
        for token in query_tokens:
            for record in self._package_by_token.get(token, []):
                candidates[id(record)] = record

        if not candidates and query_tokens:
            for record in self.packages:
                name = record.normalized_name
                specialty = normalize_text(record.specialty)
                if any(token in name for token in query_tokens):
                    candidates[id(record)] = record
                elif specialty and any(token in specialty for token in query_tokens):
                    candidates[id(record)] = record

        return list(candidates.values())[:MAX_PACKAGE_CANDIDATES]

    def _load(self) -> None:
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Rajiv Aarogyasri data directory not found: {self.data_dir}")
        self._load_manifest()
        self._load_hospitals()
        self._load_packages()
        if not self.packages:
            logger.warning("No Rajiv Aarogyasri package rows loaded from %s", self.data_dir)
        if _dev_logging_enabled():
            logger.info(
                "Rajiv Aarogyasri store ready: %d hospitals, %d packages from %s",
                len(self.hospitals),
                len(self.packages),
                self.data_dir,
            )

    def _location_bonus(
        self,
        record: AarogyasriHospitalRecord,
        *,
        patient_district: str | None,
        patient_city: str | None,
        patient_state: str | None,
    ) -> float:
        bonus = 0.0
        if patient_district and record.district:
            if normalize_text(patient_district) == normalize_text(record.district):
                bonus += 0.08
        if patient_city and record.city:
            if normalize_text(patient_city) == normalize_text(record.city):
                bonus += 0.05
        if patient_state and record.state:
            if normalize_text(patient_state) == normalize_text(record.state):
                bonus += 0.03
        return bonus

    def match_hospital(
        self,
        ocr_hospital_name: str | None,
        *,
        patient_district: str | None = None,
        patient_city: str | None = None,
        patient_state: str | None = None,
    ) -> dict[str, Any]:
        ocr_name = _clean_spaces(ocr_hospital_name or "")
        if not ocr_name:
            return {
                "matched_hospital": None,
                "matched_hospital_name": None,
                "confidence_score": 0.0,
                "match_reason": "OCR hospital name missing",
                "empanelled_status": None,
                "specialities": None,
                "state": patient_state,
                "district": patient_district,
                "city": patient_city,
                "hospital_type": None,
                "status": "Manual Verification Required",
            }

        query_aliases = build_aliases(ocr_name)
        candidates: dict[int, tuple[float, str, AarogyasriHospitalRecord]] = {}

        for alias in query_aliases:
            for record in self._hospital_alias_index.get(alias, []):
                score = 1.0
                candidates[id(record)] = (
                    score,
                    f"Exact alias match on '{alias}'",
                    record,
                )

        query_norm = normalize_text(ocr_name)
        query_tokens = set(query_norm.split())
        for record in self.hospitals:
            if id(record) in candidates:
                continue
            ratio = SequenceMatcher(None, query_norm, record.normalized_name).ratio()
            if query_tokens and record.tokens:
                overlap = len(query_tokens & record.tokens) / max(len(query_tokens), 1)
                ratio = max(ratio, overlap)
            ratio += self._location_bonus(
                record,
                patient_district=patient_district,
                patient_city=patient_city,
                patient_state=patient_state,
            )
            if ratio >= HOSPITAL_CANDIDATE_MATCH:
                candidates[id(record)] = (
                    ratio,
                    "Fuzzy name match",
                    record,
                )

        if not candidates:
            return {
                "matched_hospital": None,
                "matched_hospital_name": None,
                "confidence_score": 0.0,
                "match_reason": "No hospital match found in Rajiv Aarogyasri directory",
                "empanelled_status": None,
                "specialities": None,
                "state": patient_state,
                "district": patient_district,
                "city": patient_city,
                "hospital_type": None,
                "status": _HOSPITAL_NOT_FOUND_STATUS,
            }

        best_score, best_reason, best_record = max(candidates.values(), key=lambda item: item[0])
        if best_score < HOSPITAL_STRONG_MATCH:
            status = "Manual Verification Required"
        else:
            status = best_record.empanelled_status or "Active"

        return {
            "matched_hospital": best_record.hospital_name,
            "matched_hospital_name": best_record.hospital_name,
            "confidence_score": round(best_score, 3),
            "match_reason": best_reason,
            "empanelled_status": best_record.empanelled_status or "Active",
            "specialities": best_record.specialities or None,
            "state": best_record.state or patient_state,
            "district": best_record.district or patient_district,
            "city": best_record.city or patient_city,
            "hospital_type": best_record.hospital_type or None,
            "status": status,
        }

    def match_aarogyasri_package(
        self,
        ocr_item_or_procedure: str,
        bill_date: str | None = None,
    ) -> dict[str, Any]:
        del bill_date  # reserved for future effective-date package sets
        query = _clean_spaces(ocr_item_or_procedure)
        if not query:
            return {
                "matched_package": None,
                "package_code": None,
                "package_name": None,
                "specialty": None,
                "approved_rate": None,
                "source_file": None,
                "confidence_score": 0.0,
                "match_reason": "Empty bill item",
                "status": "Package Not Found",
            }

        query_aliases = build_aliases(query)
        query_norm = normalize_text(query)
        candidates: dict[int, tuple[float, str, AarogyasriPackageRecord]] = {}

        for alias in query_aliases:
            for record in self._package_alias_index.get(alias, []):
                ratio = SequenceMatcher(None, query_norm, record.normalized_name).ratio()
                if alias == record.normalized_name:
                    ratio = max(ratio, 1.0)
                existing = candidates.get(id(record))
                if existing is None or ratio > existing[0]:
                    candidates[id(record)] = (
                        ratio,
                        f"Exact alias match on '{alias}'",
                        record,
                    )

        query_tokens = _meaningful_tokens(query)
        for record in self._package_records_for_query(query):
            if id(record) in candidates:
                continue
            ratio = SequenceMatcher(None, query_norm, record.normalized_name).ratio()
            if query_tokens and record.tokens:
                overlap = len(query_tokens & record.tokens) / max(len(query_tokens), 1)
                ratio = max(ratio, overlap * 0.95)
            combined = normalize_text(f"{record.specialty} {record.package_name}")
            if query_norm in combined or combined in query_norm:
                ratio = max(ratio, 0.86)
            if ratio >= PACKAGE_CANDIDATE_MATCH:
                ratio = _package_score_boost(query_norm, record, ratio)
                candidates[id(record)] = (ratio, "Fuzzy procedure match", record)

        if not candidates:
            return {
                "matched_package": None,
                "package_code": None,
                "package_name": None,
                "specialty": None,
                "approved_rate": None,
                "source_file": None,
                "confidence_score": 0.0,
                "match_reason": "No Aarogyasri package match found",
                "status": "Package Not Found",
            }

        best_score, best_reason, best_record = max(candidates.values(), key=lambda item: item[0])
        if best_score < PACKAGE_STRONG_MATCH:
            return {
                "matched_package": None,
                "package_code": None,
                "package_name": None,
                "specialty": None,
                "approved_rate": None,
                "source_file": None,
                "confidence_score": round(best_score, 3),
                "match_reason": f"Weak match rejected ({best_reason})",
                "status": "Package Not Found",
            }

        return {
            "matched_package": best_record.package_name,
            "package_code": best_record.package_code or None,
            "package_name": best_record.package_name,
            "specialty": best_record.specialty or None,
            "approved_rate": best_record.approved_rate,
            "source_file": best_record.source_file,
            "confidence_score": round(best_score, 3),
            "match_reason": best_reason,
            "status": "Matched",
        }

    def find_package_candidates(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        query = _clean_spaces(query)
        if not query:
            return []

        query_norm = normalize_text(query)
        query_tokens = _meaningful_tokens(query)
        scored: list[tuple[float, AarogyasriPackageRecord, str]] = []

        for record in self._package_records_for_query(query):
            ratio = SequenceMatcher(None, query_norm, record.normalized_name).ratio()
            specialty_norm = normalize_text(record.specialty)
            if specialty_norm:
                specialty_ratio = SequenceMatcher(None, query_norm, specialty_norm).ratio()
                ratio = max(ratio, specialty_ratio * 0.95)
                if any(token in specialty_norm for token in query_tokens):
                    ratio = max(ratio, 0.78)

            combined = normalize_text(f"{record.specialty} {record.package_name}")
            combined_ratio = SequenceMatcher(None, query_norm, combined).ratio()
            ratio = max(ratio, combined_ratio)
            if query_norm in combined or combined in query_norm:
                ratio = max(ratio, 0.84)

            if query_tokens and record.tokens:
                overlap = len(query_tokens & record.tokens) / max(len(query_tokens), 1)
                ratio = max(ratio, overlap * 0.9)

            if ratio >= PACKAGE_CANDIDATE_MATCH:
                ratio = _package_score_boost(query_norm, record, ratio)
                scored.append((ratio, record, "Fuzzy package candidate"))

        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[dict[str, Any]] = []
        for score, record, reason in scored[:limit]:
            results.append(
                {
                    "package_code": record.package_code or None,
                    "package_name": record.package_name,
                    "specialty": record.specialty or None,
                    "approved_rate": record.approved_rate,
                    "source_file": record.source_file,
                    "confidence_score": round(score, 3),
                    "match_reason": reason,
                }
            )
        return results

    def match_package_from_search_terms(
        self,
        search_terms: list[str],
        bill_date: str | None = None,
    ) -> dict[str, Any]:
        searched_terms: list[str] = []
        closest_map: dict[str, dict[str, Any]] = {}
        best_match: dict[str, Any] | None = None
        best_score = 0.0
        best_term = ""
        deadline = time.monotonic() + PACKAGE_MATCH_TIME_BUDGET_SEC

        for raw_term in search_terms:
            if len(searched_terms) >= MAX_PACKAGE_SEARCH_TERMS:
                break
            term = _clean_spaces(raw_term)
            if not term:
                continue
            if term not in searched_terms:
                searched_terms.append(term)

        for term in searched_terms:
            if time.monotonic() > deadline:
                if _dev_logging_enabled():
                    logger.info(
                        "Rajiv Aarogyasri package search stopped early after %.2fs",
                        PACKAGE_MATCH_TIME_BUDGET_SEC,
                    )
                break

            match = self.match_aarogyasri_package(term, bill_date)
            if time.monotonic() <= deadline:
                for candidate in self.find_package_candidates(term, limit=3):
                    key = f"{candidate.get('package_code')}::{candidate.get('package_name')}"
                    existing = closest_map.get(key)
                    if (
                        existing is None
                        or candidate["confidence_score"] > existing["confidence_score"]
                    ):
                        closest_map[key] = candidate

            if match.get("matched_package"):
                score = float(match.get("confidence_score") or 0)
                if score > best_score:
                    best_score = score
                    best_match = dict(match)
                    best_term = term
                if score >= PACKAGE_STRONG_MATCH:
                    break

        closest_matches = sorted(
            closest_map.values(),
            key=lambda item: item.get("confidence_score") or 0,
            reverse=True,
        )[:5]

        if best_match:
            best_match["matched_search_term"] = best_term
            best_match["searched_terms"] = searched_terms
            best_match["closest_matches"] = closest_matches
            best_match["package_match_status"] = "matched"
            return best_match

        return {
            "matched_package": None,
            "package_code": None,
            "package_name": None,
            "specialty": closest_matches[0].get("specialty") if closest_matches else None,
            "approved_rate": None,
            "source_file": closest_matches[0].get("source_file") if closest_matches else None,
            "confidence_score": closest_matches[0].get("confidence_score") if closest_matches else 0.0,
            "match_reason": "No Aarogyasri package match found from OCR/package context",
            "status": "Package Not Found",
            "searched_terms": searched_terms,
            "closest_matches": closest_matches,
            "package_match_status": "not_matched",
            "matched_search_term": None,
        }


_store: RajivAarogyasriStore | None = None


def reset_rajiv_aarogyasri_store() -> None:
    """Clear cached store (used in tests after loader changes)."""
    global _store
    _store = None


def get_rajiv_aarogyasri_store() -> RajivAarogyasriStore:
    global _store
    if _store is None:
        _store = RajivAarogyasriStore()
    return _store


def _build_eligibility_preview(
    *,
    telangana_resident: bool,
    has_eligible_card: bool,
    has_aadhaar: bool,
    cancer_related: bool,
) -> list[str]:
    messages: list[str] = []
    if not telangana_resident:
        messages.append("Telangana residency is required for this scheme.")
    if not has_eligible_card:
        messages.append(
            "Aarogyasri / eligible ration card / scheme eligibility is required."
        )
    if not has_aadhaar:
        messages.append("Aadhaar may be required for beneficiary verification.")
    if cancer_related:
        messages.append(
            "Cancer-related treatment requires latest oncology hospital/package verification."
        )
    if telangana_resident and has_eligible_card and has_aadhaar:
        messages.insert(
            0,
            "Based on the information provided, the patient may be eligible for "
            "Rajiv Aarogyasri, subject to hospital/package verification and "
            "official approval.",
        )
    return messages


def _text_has_cancer_keywords(text: str | None) -> bool:
    normalized = normalize_text(text or "")
    if not normalized:
        return False
    return any(keyword in normalized for keyword in _CANCER_KEYWORDS)


def build_package_search_terms(
    *,
    ocr_text: str | None = None,
    diagnosis: str | None = None,
    department: str | None = None,
    line_items: list[dict[str, Any]] | None = None,
    prescription_items: list[dict[str, Any]] | None = None,
) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = _clean_spaces(str(value or ""))
        if not text:
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        terms.append(text)

    if diagnosis:
        add(diagnosis)
    if department:
        add(department)
    if diagnosis and department:
        add(f"{diagnosis} {department}")
    if diagnosis and "chemo" not in diagnosis.lower():
        add(f"{diagnosis} Chemotherapy")

    for item in line_items or []:
        add(item.get("item_name"))
        category = str(item.get("category") or "").strip().lower()
        if category in {"procedure", "medicine", "test"}:
            add(f"{item.get('item_name')} {diagnosis or ''}".strip())

    for item in prescription_items or []:
        add(item.get("name") or item.get("item_name"))

    if ocr_text:
        for line in ocr_text.splitlines():
            line = line.strip()
            if not line:
                continue
            add(line)
            if ":" in line:
                _, _, tail = line.partition(":")
                add(tail.strip())

    combined_phrases = [
        "Chemotherapy for Cancer Treatment",
        "Chemotherapy Cycle 1",
        "Chemotherapy Procedure Charges",
        "Carcinoma Lung Oncology",
    ]
    blob = normalize_text(
        " ".join(
            [
                diagnosis or "",
                department or "",
                ocr_text or "",
                " ".join(str(item.get("item_name", "")) for item in (line_items or [])),
            ]
        )
    )
    if "carcinoma" in blob and "lung" in blob:
        add("Carcinoma Lung")
        add("Chemotherapy for Non SMAL cell Lung Cancer")
    if "oncology" in blob or "chemotherapy" in blob or "chemo" in blob:
        for phrase in combined_phrases:
            add(phrase)

    return terms


def extract_department_from_text(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        if re.search(r"\bdepartment\b", line, re.IGNORECASE):
            _, _, tail = line.partition(":")
            if tail.strip():
                return tail.strip()
    normalized = normalize_text(text)
    if "oncology" in normalized:
        return "Oncology"
    return None


def _is_old_city_context(
    *,
    ocr_hospital_name: str | None,
    patient_city: str | None,
    ocr_text: str | None = None,
) -> bool:
    combined = normalize_text(
        f"{ocr_hospital_name or ''} {patient_city or ''} {ocr_text or ''}"
    )
    raw_combined = _clean_spaces(
        re.sub(r"[^a-z0-9 ]+", " ", f"{ocr_hospital_name or ''} {ocr_text or ''}".lower())
    )
    if any(token in combined for token in ("old city", "charminar", "oldcity")):
        return True
    if "owaisi" in raw_combined or "owaisi" in combined:
        return True
    if ("princess" in raw_combined and "esra" in raw_combined) or (
        "princess" in combined and "esra" in combined
    ):
        return True
    return any(phrase in raw_combined or phrase in combined for phrase in _OLD_CITY_HOSPITAL_PHRASES)


def _is_cancer_context(
    *,
    cancer_related: bool,
    package_specialty: str | None,
    package_name: str | None,
    search_text: str | None = None,
) -> bool:
    if cancer_related:
        return True
    if _text_has_cancer_keywords(search_text):
        return True
    combined = normalize_text(f"{package_specialty or ''} {package_name or ''}")
    return any(keyword in combined for keyword in _CANCER_KEYWORDS)


def _evaluate_advisory_rules(
    *,
    rajiv_selected: bool,
    bill_date: str | None,
    ocr_hospital_name: str | None,
    patient_city: str | None,
    ocr_text: str | None,
    search_text: str | None,
    cancer_related: bool,
    package_specialty: str | None,
    package_name: str | None,
    hospital_status: str,
    package_statuses: list[str],
    low_confidence: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    advisories: list[dict[str, Any]] = []
    advisory_debug: list[dict[str, Any]] = []
    parsed_bill_date = _parse_date(bill_date)
    cancer_detected = _is_cancer_context(
        cancer_related=cancer_related,
        package_specialty=package_specialty,
        package_name=package_name,
        search_text=search_text,
    )
    old_city_detected = _is_old_city_context(
        ocr_hospital_name=ocr_hospital_name,
        patient_city=patient_city,
        ocr_text=ocr_text,
    )
    needs_manual = (
        low_confidence
        or "not found" in hospital_status.lower()
        or "manual verification" in hospital_status.lower()
        or any(
            status in {"Package Not Found", "Manual Verification Required", "CGHS Fallback Used"}
            for status in package_statuses
        )
    )

    rules: list[dict[str, Any]] = [
        {
            "rule_key": "revised_aarogyasri_packages",
            "title": "Revised Aarogyasri Packages",
            "triggered": bool(parsed_bill_date and parsed_bill_date >= date(2024, 7, 16)),
            "trigger_reason": (
                f"Bill date {bill_date} is on or after 2024-07-16"
                if parsed_bill_date and parsed_bill_date >= date(2024, 7, 16)
                else f"Bill date {bill_date or 'missing'} is before 2024-07-16"
            ),
            "input_checked": bill_date or "",
            "payload": {
                "title": "Revised Aarogyasri Packages",
                "effective_date": "2024-07-16",
                "message": (
                    "Revised Rajiv Aarogyasri package rates apply from G.O.Ms.No.30 "
                    "dated 16 July 2024. The app uses the available Aarogyasri package "
                    "files as the primary rate source for eligible bills."
                ),
            },
        },
        {
            "rule_key": "old_city_hospital_access",
            "title": "Old City Hospital Access",
            "triggered": old_city_detected,
            "trigger_reason": (
                "Hospital/OCR text matched Old City access criteria"
                if old_city_detected
                else "No Old City hospital keyword detected"
            ),
            "input_checked": _clean_spaces(
                f"{ocr_hospital_name or ''} | {patient_city or ''} | {(ocr_text or '')[:120]}"
            ),
            "payload": {
                "title": "Old City Hospital Access",
                "effective_date": "2025-10-24",
                "message": (
                    "Government healthcare access in the Old City area was extended to "
                    "include Owaisi Hospital and Princess Esra Hospital. Verify current "
                    "empanelment and eligibility before final conclusion."
                ),
            },
        },
        {
            "rule_key": "cancer_treatment_verification",
            "title": "Cancer Treatment Verification",
            "triggered": cancer_detected,
            "trigger_reason": (
                "Cancer/oncology/chemotherapy keywords found in OCR or patient flags"
                if cancer_detected
                else "No cancer-related keywords detected"
            ),
            "input_checked": _clean_spaces(search_text or "")[:240],
            "payload": {
                "title": "Cancer Treatment Verification",
                "effective_date": "2026-02-04",
                "message": (
                    "Cancer-related Aarogyasri treatment may require verification with "
                    "MNJ Institute of Oncology and Regional Cancer Centre or other "
                    "approved oncology hospitals under the latest applicable government "
                    "instructions."
                ),
            },
        },
        {
            "rule_key": "cashless_package_scheme",
            "title": "Cashless Package Scheme Advisory",
            "triggered": rajiv_selected,
            "trigger_reason": "Rajiv Aarogyasri selected for this patient",
            "input_checked": "rajiv_aarogyasri_selected=true",
            "payload": {
                "title": "Cashless Package Scheme Advisory",
                "effective_date": None,
                "message": (
                    "Rajiv Aarogyasri is a cashless package-based healthcare scheme for "
                    "eligible beneficiaries. If the patient is eligible and the "
                    "hospital/package is covered, direct collection from the patient may "
                    "require manual verification with the Aarogyasri helpdesk or Trust."
                ),
            },
        },
        {
            "rule_key": "manual_verification",
            "title": "Manual Verification Advisory",
            "triggered": needs_manual,
            "trigger_reason": (
                "Hospital/package match missing or low confidence"
                if needs_manual
                else "Hospital and package checks passed with acceptable confidence"
            ),
            "input_checked": _clean_spaces(
                f"hospital_status={hospital_status}; package_statuses={', '.join(package_statuses)}"
            ),
            "payload": {
                "title": "Manual Verification Advisory",
                "effective_date": None,
                "message": (
                    "OCR extraction and fuzzy matching may be imperfect. Hospital "
                    "empanelment, package approval, and final eligibility must be "
                    "verified manually with official Aarogyasri sources."
                ),
            },
        },
    ]

    for rule in rules:
        advisory_debug.append(
            {
                "rule_key": rule["rule_key"],
                "title": rule["title"],
                "triggered": rule["triggered"],
                "trigger_reason": rule["trigger_reason"],
                "input_checked": rule["input_checked"],
            }
        )
        if rule["triggered"]:
            advisories.append(rule["payload"])
            logger.info(
                "Rajiv Aarogyasri rule triggered: %s because %s",
                rule["rule_key"],
                rule["trigger_reason"],
            )

    return advisories, advisory_debug


def _collect_advisories(
    *,
    rajiv_selected: bool,
    bill_date: str | None,
    ocr_hospital_name: str | None,
    patient_city: str | None,
    ocr_text: str | None = None,
    search_text: str | None = None,
    cancer_related: bool,
    package_specialty: str | None,
    package_name: str | None,
    hospital_status: str,
    package_statuses: list[str],
    low_confidence: bool,
) -> list[dict[str, Any]]:
    advisories, _ = _evaluate_advisory_rules(
        rajiv_selected=rajiv_selected,
        bill_date=bill_date,
        ocr_hospital_name=ocr_hospital_name,
        patient_city=patient_city,
        ocr_text=ocr_text,
        search_text=search_text,
        cancer_related=cancer_related,
        package_specialty=package_specialty,
        package_name=package_name,
        hospital_status=hospital_status,
        package_statuses=package_statuses,
        low_confidence=low_confidence,
    )
    return advisories


def _comparison_status(charged: float, approved_rate: float | None, *, matched: bool) -> str:
    if not matched or approved_rate is None:
        return "Aarogyasri Package Not Found — CGHS Fallback Used"
    if charged > approved_rate:
        return "Possible Excess"
    if charged < approved_rate:
        return "Below Approved Rate"
    return "Within / Below Approved Package Rate"


def build_rajiv_aarogyasri_fallback_report(
    *,
    rajiv_is_telangana_resident: bool = False,
    rajiv_has_eligible_card: bool = False,
    rajiv_has_aadhaar: bool = False,
    rajiv_is_cancer_related: bool = False,
    rajiv_family_coverage_used_amount: float | None = None,
    ocr_hospital_name: str | None = None,
    patient_state: str | None = None,
    patient_district: str | None = None,
    patient_city: str | None = None,
    line_items: list[dict[str, Any]] | None = None,
    compared_line_items: list[dict[str, Any]] | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    items = line_items or []
    cghs_items = compared_line_items or []
    package_comparisons: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        bill_item_name = str(item.get("item_name", "")).strip()
        charged_amount = _parse_amount(item.get("total_price")) or 0.0
        cghs_item = cghs_items[index] if index < len(cghs_items) else {}
        cghs_rate = _parse_amount(cghs_item.get("cghs_rate"))
        excess_amount = (
            round(max(charged_amount - cghs_rate, 0.0), 2)
            if cghs_rate is not None
            else None
        )
        package_comparisons.append(
            {
                "bill_item_name": bill_item_name,
                "charged_amount": charged_amount,
                "matched_package_code": None,
                "matched_package_name": None,
                "specialty": None,
                "approved_rate": cghs_rate,
                "source_file": None,
                "confidence_score": 0.0,
                "match_reason": AAROGYASRI_MATCH_FAILED_ADVISORY,
                "excess_amount": excess_amount,
                "status": "CGHS Fallback Used" if cghs_rate is not None else "Package Not Found",
                "fallback_used": True,
            }
        )

    return {
        "selected": True,
        "status": "manual_verification_required",
        "eligibility_snapshot": {
            "telangana_resident": rajiv_is_telangana_resident,
            "has_eligible_card": rajiv_has_eligible_card,
            "has_aadhaar": rajiv_has_aadhaar,
            "cancer_related": rajiv_is_cancer_related,
            "family_coverage_used_amount": rajiv_family_coverage_used_amount,
        },
        "eligibility_preview": _build_eligibility_preview(
            telangana_resident=rajiv_is_telangana_resident,
            has_eligible_card=rajiv_has_eligible_card,
            has_aadhaar=rajiv_has_aadhaar,
            cancer_related=rajiv_is_cancer_related,
        ),
        "hospital_verification": {
            "ocr_hospital_name": ocr_hospital_name,
            "matched_hospital_name": None,
            "confidence_score": 0.0,
            "match_reason": error_message or AAROGYASRI_MATCH_FAILED_ADVISORY,
            "state": patient_state,
            "district": patient_district,
            "city": patient_city,
            "hospital_type": None,
            "empanelled_status": None,
            "specialities": None,
            "status": "Manual Verification Required",
        },
        "package_comparisons": package_comparisons,
        "package_search": {
            "searched_terms": [],
            "package_match_status": "failed",
            "matched_package_name": None,
            "matched_package_code": None,
            "matched_search_term": None,
            "confidence_score": 0.0,
            "match_reason": AAROGYASRI_MATCH_FAILED_ADVISORY,
            "closest_matches": [],
            "source_files_searched": [],
            "not_matched_message": _PACKAGE_NOT_MATCHED_MESSAGE,
        },
        "advisories": [
            {
                "title": "Manual Verification Advisory",
                "effective_date": None,
                "message": AAROGYASRI_MATCH_FAILED_ADVISORY,
            }
        ],
        "advisory_debug": [],
        "disclaimer": DISCLAIMER,
        "error_debug": error_message if _dev_logging_enabled() else None,
    }


def build_rajiv_aarogyasri_report(
    *,
    rajiv_aarogyasri_selected: bool,
    rajiv_is_telangana_resident: bool = False,
    rajiv_has_eligible_card: bool = False,
    rajiv_has_aadhaar: bool = False,
    rajiv_is_cancer_related: bool = False,
    rajiv_family_coverage_used_amount: float | None = None,
    ocr_hospital_name: str | None = None,
    patient_state: str | None = None,
    patient_district: str | None = None,
    patient_city: str | None = None,
    bill_date: str | None = None,
    line_items: list[dict[str, Any]] | None = None,
    compared_line_items: list[dict[str, Any]] | None = None,
    ocr_text: str | None = None,
    diagnosis: str | None = None,
    department: str | None = None,
    prescription_items: list[dict[str, Any]] | None = None,
    context_match: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not rajiv_aarogyasri_selected:
        return None

    try:
        return _build_rajiv_aarogyasri_report_inner(
            rajiv_is_telangana_resident=rajiv_is_telangana_resident,
            rajiv_has_eligible_card=rajiv_has_eligible_card,
            rajiv_has_aadhaar=rajiv_has_aadhaar,
            rajiv_is_cancer_related=rajiv_is_cancer_related,
            rajiv_family_coverage_used_amount=rajiv_family_coverage_used_amount,
            ocr_hospital_name=ocr_hospital_name,
            patient_state=patient_state,
            patient_district=patient_district,
            patient_city=patient_city,
            bill_date=bill_date,
            line_items=line_items,
            compared_line_items=compared_line_items,
            ocr_text=ocr_text,
            diagnosis=diagnosis,
            department=department,
            prescription_items=prescription_items,
            context_match=context_match,
        )
    except Exception as exc:
        logger.exception("Rajiv Aarogyasri report build failed: %s", exc)
        return build_rajiv_aarogyasri_fallback_report(
            rajiv_is_telangana_resident=rajiv_is_telangana_resident,
            rajiv_has_eligible_card=rajiv_has_eligible_card,
            rajiv_has_aadhaar=rajiv_has_aadhaar,
            rajiv_is_cancer_related=rajiv_is_cancer_related,
            rajiv_family_coverage_used_amount=rajiv_family_coverage_used_amount,
            ocr_hospital_name=ocr_hospital_name,
            patient_state=patient_state,
            patient_district=patient_district,
            patient_city=patient_city,
            line_items=line_items,
            compared_line_items=compared_line_items,
            error_message=(
                f"{exc}\n{traceback.format_exc()}" if _dev_logging_enabled() else str(exc)
            ),
        )


def _build_rajiv_aarogyasri_report_inner(
    *,
    rajiv_is_telangana_resident: bool = False,
    rajiv_has_eligible_card: bool = False,
    rajiv_has_aadhaar: bool = False,
    rajiv_is_cancer_related: bool = False,
    rajiv_family_coverage_used_amount: float | None = None,
    ocr_hospital_name: str | None = None,
    patient_state: str | None = None,
    patient_district: str | None = None,
    patient_city: str | None = None,
    bill_date: str | None = None,
    line_items: list[dict[str, Any]] | None = None,
    compared_line_items: list[dict[str, Any]] | None = None,
    ocr_text: str | None = None,
    diagnosis: str | None = None,
    department: str | None = None,
    prescription_items: list[dict[str, Any]] | None = None,
    context_match: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        store = get_rajiv_aarogyasri_store()
    except FileNotFoundError as exc:
        logger.warning("Rajiv Aarogyasri store unavailable: %s", exc)
        return {
            "selected": True,
            "status": "manual_verification_required",
            "eligibility_snapshot": {
                "telangana_resident": rajiv_is_telangana_resident,
                "has_eligible_card": rajiv_has_eligible_card,
                "has_aadhaar": rajiv_has_aadhaar,
                "cancer_related": rajiv_is_cancer_related,
                "family_coverage_used_amount": rajiv_family_coverage_used_amount,
            },
            "eligibility_preview": _build_eligibility_preview(
                telangana_resident=rajiv_is_telangana_resident,
                has_eligible_card=rajiv_has_eligible_card,
                has_aadhaar=rajiv_has_aadhaar,
                cancer_related=rajiv_is_cancer_related,
            ),
            "hospital_verification": {
                "ocr_hospital_name": ocr_hospital_name,
                "matched_hospital_name": None,
                "confidence_score": 0.0,
                "match_reason": str(exc),
                "state": patient_state,
                "district": patient_district,
                "city": patient_city,
                "hospital_type": None,
                "empanelled_status": None,
                "specialities": None,
                "status": "Manual Verification Required",
            },
            "package_comparisons": [],
            "package_search": {
                "searched_terms": [],
                "package_match_status": "unavailable",
                "closest_matches": [],
                "source_files_searched": [],
                "not_matched_message": _PACKAGE_NOT_MATCHED_MESSAGE,
            },
            "advisories": [],
            "advisory_debug": [],
            "disclaimer": DISCLAIMER,
        }

    search_terms = build_package_search_terms(
        ocr_text=ocr_text,
        diagnosis=diagnosis,
        department=department,
        line_items=line_items,
        prescription_items=prescription_items,
    )
    search_blob = _clean_spaces(
        " ".join(
            [
                ocr_text or "",
                diagnosis or "",
                department or "",
                ocr_hospital_name or "",
                " ".join(
                    str(item.get("item_name", ""))
                    for item in (line_items or [])
                ),
            ]
        )
    )
    if context_match is None:
        context_match = store.match_package_from_search_terms(search_terms, bill_date)
    source_files = [path.name for path in store._discover_package_files()]

    if _dev_logging_enabled():
        logger.info(
            "Rajiv Aarogyasri package search terms=%s match=%s hospital=%s",
            search_terms[:MAX_PACKAGE_SEARCH_TERMS],
            context_match.get("package_match_status"),
            ocr_hospital_name,
        )

    hospital_verification = store.match_hospital(
        ocr_hospital_name,
        patient_district=patient_district,
        patient_city=patient_city,
        patient_state=patient_state,
    )
    hospital_verification["ocr_hospital_name"] = ocr_hospital_name

    if _dev_logging_enabled():
        logger.info(
            "Rajiv Aarogyasri hospital match: ocr=%s result=%s confidence=%s",
            ocr_hospital_name,
            hospital_verification.get("matched_hospital_name"),
            hospital_verification.get("confidence_score"),
        )

    package_comparisons: list[dict[str, Any]] = []
    package_statuses: list[str] = []
    low_confidence = False
    items = line_items or []
    cghs_items = compared_line_items or []

    for index, item in enumerate(items):
        bill_item_name = str(item.get("item_name", "")).strip()
        charged_amount = _parse_amount(item.get("total_price")) or 0.0
        package_match = store.match_aarogyasri_package(bill_item_name, bill_date)
        if not package_match.get("matched_package") and context_match.get("matched_package"):
            package_match = {
                **context_match,
                "match_reason": (
                    f"Context match via '{context_match.get('matched_search_term')}' "
                    f"({context_match.get('match_reason')})"
                ),
            }

        approved_rate = package_match.get("approved_rate")
        matched = bool(package_match.get("matched_package"))
        fallback_used = not matched

        cghs_item = cghs_items[index] if index < len(cghs_items) else {}
        if fallback_used:
            cghs_rate = _parse_amount(cghs_item.get("cghs_rate"))
            if cghs_rate is not None:
                approved_rate = cghs_rate

        excess_amount = None
        if approved_rate is not None:
            excess_amount = round(max(charged_amount - approved_rate, 0.0), 2)

        if package_match.get("confidence_score", 0) < PACKAGE_STRONG_MATCH and matched:
            low_confidence = True

        if matched and package_match.get("confidence_score", 0) < PACKAGE_STRONG_MATCH:
            status = "Manual Verification Required"
        elif fallback_used:
            status = "CGHS Fallback Used" if approved_rate is not None else "Package Not Found"
        else:
            status = _comparison_status(charged_amount, approved_rate, matched=True)

        package_statuses.append(status)
        package_comparisons.append(
            {
                "bill_item_name": bill_item_name,
                "charged_amount": charged_amount,
                "matched_package_code": package_match.get("package_code"),
                "matched_package_name": package_match.get("package_name"),
                "specialty": package_match.get("specialty"),
                "approved_rate": approved_rate,
                "source_file": package_match.get("source_file"),
                "confidence_score": package_match.get("confidence_score"),
                "match_reason": package_match.get("match_reason"),
                "excess_amount": excess_amount,
                "status": status,
                "fallback_used": fallback_used,
            }
        )

    first_package = package_comparisons[0] if package_comparisons else {}
    advisories, advisory_debug = _evaluate_advisory_rules(
        rajiv_selected=True,
        bill_date=bill_date,
        ocr_hospital_name=ocr_hospital_name,
        patient_city=patient_city or patient_district,
        ocr_text=ocr_text,
        search_text=search_blob,
        cancer_related=rajiv_is_cancer_related,
        package_specialty=first_package.get("specialty")
        or context_match.get("specialty"),
        package_name=first_package.get("matched_package_name")
        or context_match.get("package_name"),
        hospital_status=str(hospital_verification.get("status", "")),
        package_statuses=package_statuses,
        low_confidence=low_confidence,
    )

    package_search = {
        "searched_terms": search_terms,
        "package_match_status": context_match.get("package_match_status"),
        "matched_package_name": context_match.get("package_name"),
        "matched_package_code": context_match.get("package_code"),
        "matched_search_term": context_match.get("matched_search_term"),
        "confidence_score": context_match.get("confidence_score"),
        "match_reason": context_match.get("match_reason"),
        "closest_matches": context_match.get("closest_matches") or [],
        "source_files_searched": source_files,
        "not_matched_message": (
            ""
            if context_match.get("matched_package")
            else _PACKAGE_NOT_MATCHED_MESSAGE
        ),
    }

    report_status = "matched"
    hospital_status_text = str(hospital_verification.get("status", "")).lower()
    if (
        low_confidence
        or "not found" in hospital_status_text
        or "manual verification" in hospital_status_text
        or any(
            status in {"Package Not Found", "Manual Verification Required", "CGHS Fallback Used"}
            for status in package_statuses
        )
    ):
        report_status = "manual_verification_required"

    return {
        "selected": True,
        "status": report_status,
        "eligibility_snapshot": {
            "telangana_resident": rajiv_is_telangana_resident,
            "has_eligible_card": rajiv_has_eligible_card,
            "has_aadhaar": rajiv_has_aadhaar,
            "cancer_related": rajiv_is_cancer_related,
            "family_coverage_used_amount": rajiv_family_coverage_used_amount,
        },
        "eligibility_preview": _build_eligibility_preview(
            telangana_resident=rajiv_is_telangana_resident,
            has_eligible_card=rajiv_has_eligible_card,
            has_aadhaar=rajiv_has_aadhaar,
            cancer_related=rajiv_is_cancer_related,
        ),
        "hospital_verification": hospital_verification,
        "package_comparisons": package_comparisons,
        "package_search": package_search,
        "advisories": advisories,
        "advisory_debug": advisory_debug,
        "disclaimer": DISCLAIMER,
    }
