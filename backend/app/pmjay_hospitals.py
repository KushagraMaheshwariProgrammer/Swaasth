"""PM-JAY empanelled hospital directory and verification."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _BACKEND_ROOT / "data" / "schemes" / "pmjay"

HOSPITAL_STRONG_MATCH = 0.82
HOSPITAL_CANDIDATE_MATCH = 0.55
HOSPITAL_MULTIPLE_GAP = 0.08

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

_DIRECT_PAYMENT_KEYWORDS = (
    "amount paid",
    "cash paid",
    "paid by patient",
    "self pay",
    "self-pay",
    "direct payment",
    "payment received",
    "advance paid",
    "balance paid",
    "receipt no",
    "mode of payment",
    "cash payment",
)

_ADVISORY_EMPANELLED = (
    "Hospital appears in the PM-JAY empanelled hospital data. If the patient is "
    "PM-JAY eligible and treatment/package is covered, cashless treatment may "
    "apply subject to official verification."
)
_ADVISORY_NOT_FOUND = (
    "Hospital was not found in the PM-JAY empanelled hospital data available in "
    "the app. Verify on the official PM-JAY hospital search portal or with the "
    "hospital Ayushman helpdesk."
)
_ADVISORY_SUSPENDED = (
    "Hospital appears to be suspended/delisted in the available PM-JAY data. "
    "Manual verification is required before relying on PM-JAY coverage."
)
_ADVISORY_ELIGIBILITY = (
    "PM-JAY hospital empanelment alone does not confirm patient eligibility. "
    "Ayushman card / beneficiary eligibility must be verified separately."
)
_ADVISORY_DIRECT_PAYMENT = (
    "Direct payment by a PM-JAY beneficiary at an empanelled hospital may "
    "require manual verification, because PM-JAY is intended for cashless "
    "treatment for eligible covered packages."
)
_ADVISORY_DATABASE_MISSING = (
    "PM-JAY hospital database is not available. Manual verification required."
)
_ADVISORY_OCR_MISSING = (
    "OCR could not detect hospital name. Manual hospital verification required."
)


def _clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def normalize_text(text: str) -> str:
    normalized = (text or "").lower().strip()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = _clean_spaces(normalized)
    normalized = re.sub(r"(.)\1{2,}", r"\1\1", normalized)
    tokens = [token for token in normalized.split() if token not in _STRIP_TOKENS]
    return _clean_spaces(" ".join(tokens))


def _parse_aliases(raw: str | None) -> tuple[str, ...]:
    if not raw or not str(raw).strip():
        return ()
    text = str(raw).strip()
    parts: list[str] = []
    for chunk in re.split(r"[|,;]", text):
        cleaned = _clean_spaces(chunk)
        if cleaned:
            parts.append(cleaned)
    return tuple(dict.fromkeys(parts))


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return default


def _default_csv_path() -> Path:
    candidates = [
        _DATA_DIR / "pmjay_empanelled_hospitals.csv",
        _BACKEND_ROOT / "data" / "pmjay_empanelled_hospitals.csv",
        _BACKEND_ROOT / "data" / "24_June_2026.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "PM-JAY empanelled hospitals CSV not found. Expected one of: "
        + ", ".join(str(p) for p in candidates)
    )


def build_aliases(name: str, extra_aliases: Iterable[str] | None = None) -> set[str]:
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
    if extra_aliases:
        for alias in extra_aliases:
            cleaned = _clean_spaces(str(alias))
            if cleaned:
                aliases.add(normalize_text(cleaned))
    aliases.discard("")
    return aliases


@dataclass
class PmjayHospitalRecord:
    hospital_id: str
    hospital_name: str
    normalized_name: str
    aliases: tuple[str, ...]
    state: str
    district: str
    city: str
    address: str
    hospital_type: str
    empanelment_type: str
    empanelment_status: str
    specialities: str
    source: str
    last_updated: str
    alias_keys: set[str] = field(default_factory=set)

    def to_public(self) -> dict[str, Any]:
        return {
            "hospital_id": self.hospital_id,
            "hospital_name": self.hospital_name,
            "aliases": list(self.aliases),
            "state": self.state,
            "district": self.district,
            "city": self.city,
            "address": self.address,
            "hospital_type": self.hospital_type,
            "empanelment_type": self.empanelment_type,
            "empanelment_status": self.empanelment_status,
            "specialities": self.specialities,
            "source": self.source,
            "last_updated": self.last_updated,
        }


class PmjayHospitalStore:
    def __init__(self, csv_path: Path | None = None) -> None:
        self.csv_path = csv_path or _default_csv_path()
        self.hospitals: list[PmjayHospitalRecord] = []
        self._alias_index: dict[str, list[PmjayHospitalRecord]] = {}
        self._name_index: dict[str, list[PmjayHospitalRecord]] = {}
        self._states: set[str] = set()
        self._districts: set[str] = set()
        self._cities: set[str] = set()
        self._hospital_types: set[str] = set()
        self._load(self.csv_path)

    def _load(self, path: Path) -> None:
        if not path.exists():
            return

        seen: set[tuple[str, str]] = set()
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fieldnames = {name.strip().lower() for name in (reader.fieldnames or [])}
            legacy = "hospital name" in fieldnames and "hospital_name" not in fieldnames

            for raw in reader:
                if not raw:
                    continue
                if legacy:
                    empanelment_type = (raw.get("Empanelment Type") or "").strip()
                    if "PMJAY" not in empanelment_type.upper():
                        continue
                    hospital_name = (raw.get("Hospital Name") or "").strip()
                    hospital_id = (raw.get("Hospital Id") or "").strip()
                    state = (raw.get("State") or "").strip()
                    district = (raw.get("District") or "").strip()
                    city = district
                    address = ""
                    hospital_type = (raw.get("Hospital Type") or "").strip()
                    empanelment_status = _normalize_empanelment_status(
                        raw.get("Application Status")
                    )
                    specialities = (
                        raw.get("Current Specialities")
                        or raw.get("Specialities Selected")
                        or ""
                    ).strip()
                    source = path.name
                    last_updated = (raw.get("Status Updated Date") or "").strip()
                    aliases = (hospital_name,)
                else:
                    hospital_name = (raw.get("hospital_name") or "").strip()
                    hospital_id = (raw.get("hospital_id") or "").strip()
                    state = (raw.get("state") or "").strip()
                    district = (raw.get("district") or "").strip()
                    city = (raw.get("city") or district or "").strip()
                    address = (raw.get("address") or "").strip()
                    hospital_type = (raw.get("hospital_type") or "").strip()
                    empanelment_type = (raw.get("empanelment_type") or "PMJAY").strip()
                    if empanelment_type and "PMJAY" not in empanelment_type.upper():
                        continue
                    empanelment_status = _normalize_empanelment_status(
                        raw.get("empanelment_status")
                    )
                    specialities = (raw.get("specialities") or "").strip()
                    source = (raw.get("source") or path.name).strip()
                    last_updated = (raw.get("last_updated") or "").strip()
                    aliases = _parse_aliases(raw.get("aliases")) or (hospital_name,)

                if not hospital_name:
                    continue

                dedupe_key = (hospital_id or hospital_name.casefold(), hospital_name.casefold())
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                normalized_name = normalize_text(hospital_name)
                alias_keys = build_aliases(hospital_name, aliases)
                record = PmjayHospitalRecord(
                    hospital_id=hospital_id,
                    hospital_name=hospital_name,
                    normalized_name=normalized_name,
                    aliases=aliases if isinstance(aliases, tuple) else tuple(aliases),
                    state=state,
                    district=district,
                    city=city,
                    address=address,
                    hospital_type=hospital_type,
                    empanelment_type=empanelment_type if not legacy else (raw.get("Empanelment Type") or "PMJAY").strip(),
                    empanelment_status=empanelment_status,
                    specialities=specialities,
                    source=source,
                    last_updated=last_updated,
                    alias_keys=alias_keys,
                )
                self.hospitals.append(record)
                if state:
                    self._states.add(state)
                if district:
                    self._districts.add(district)
                if city:
                    self._cities.add(city)
                if hospital_type:
                    self._hospital_types.add(hospital_type)
                self._name_index.setdefault(normalized_name, []).append(record)
                for alias in alias_keys:
                    self._alias_index.setdefault(alias, []).append(record)

    def list_states(self) -> list[str]:
        return sorted(self._states, key=str.casefold)

    def list_districts(self, *, state: str = "") -> list[str]:
        state_norm = normalize_text(state)
        values = {
            record.district
            for record in self.hospitals
            if record.district
            and (not state_norm or normalize_text(record.state) == state_norm)
        }
        return sorted(values, key=str.casefold)

    def list_cities(self, *, state: str = "", district: str = "") -> list[str]:
        state_norm = normalize_text(state)
        district_norm = normalize_text(district)
        values = {
            record.city
            for record in self.hospitals
            if record.city
            and (not state_norm or normalize_text(record.state) == state_norm)
            and (not district_norm or normalize_text(record.district) == district_norm)
        }
        return sorted(values, key=str.casefold)

    def list_hospital_types(self) -> list[str]:
        return sorted(self._hospital_types, key=str.casefold)

    def search_hospitals(
        self,
        *,
        query: str = "",
        state: str = "",
        district: str = "",
        city: str = "",
        hospital_type: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        query_norm = normalize_text(query)
        state_norm = normalize_text(state)
        district_norm = normalize_text(district)
        city_norm = normalize_text(city)
        type_norm = normalize_text(hospital_type)

        filtered: list[PmjayHospitalRecord] = []
        for record in self.hospitals:
            if state_norm and normalize_text(record.state) != state_norm:
                continue
            if district_norm and normalize_text(record.district) != district_norm:
                continue
            if city_norm and normalize_text(record.city) != city_norm:
                continue
            if type_norm and normalize_text(record.hospital_type) != type_norm:
                continue
            if query_norm:
                haystack = " ".join(
                    [
                        record.hospital_name,
                        record.state,
                        record.district,
                        record.city,
                        record.specialities,
                        " ".join(record.aliases),
                    ]
                ).lower()
                if query_norm not in normalize_text(haystack) and not any(
                    query_norm in alias or alias in query_norm
                    for alias in record.alias_keys
                ):
                    alias_hit = any(
                        query_norm in alias or alias in query_norm
                        for alias in record.alias_keys
                    )
                    token_hit = any(
                        token in haystack for token in query_norm.split() if len(token) >= 3
                    )
                    if not alias_hit and not token_hit:
                        continue
            filtered.append(record)

        total = len(filtered)
        page = filtered[offset : offset + limit]
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "hospitals": [record.to_public() for record in page],
        }

    def _location_bonus(
        self,
        record: PmjayHospitalRecord,
        *,
        patient_state: str | None,
        patient_district: str | None,
        patient_city: str | None,
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

    def match_pmjay_hospital(
        self,
        ocr_hospital_name: str | None,
        *,
        patient_state: str | None = None,
        patient_district: str | None = None,
        patient_city: str | None = None,
    ) -> dict[str, Any]:
        ocr_name = _clean_spaces(ocr_hospital_name or "")
        if not ocr_name:
            return _empty_match(
                ocr_hospital_name="",
                status="manual_verification_required",
                match_reason="OCR hospital name missing",
                advisories=[_ADVISORY_OCR_MISSING],
            )

        query_norm = normalize_text(ocr_name)
        query_aliases = build_aliases(ocr_name)
        candidates: dict[int, tuple[float, str, PmjayHospitalRecord]] = {}

        for alias in query_aliases:
            for record in self._alias_index.get(alias, []):
                score = 1.0 + self._location_bonus(
                    record,
                    patient_state=patient_state,
                    patient_district=patient_district,
                    patient_city=patient_city,
                )
                candidates[id(record)] = (min(score, 1.0), "Exact alias match", record)

        for record in self._name_index.get(query_norm, []):
            score = 1.0 + self._location_bonus(
                record,
                patient_state=patient_state,
                patient_district=patient_district,
                patient_city=patient_city,
            )
            candidates[id(record)] = (min(score, 1.0), "Exact normalized name match", record)

        query_tokens = set(query_norm.split())
        for record in self.hospitals:
            if id(record) in candidates:
                continue
            ratio = SequenceMatcher(None, query_norm, record.normalized_name).ratio()
            if query_tokens and record.normalized_name:
                record_tokens = set(record.normalized_name.split())
                overlap = len(query_tokens & record_tokens) / max(len(query_tokens), 1)
                ratio = max(ratio, overlap)
            if query_norm in record.normalized_name or record.normalized_name in query_norm:
                ratio = max(ratio, 0.9)
            ratio += self._location_bonus(
                record,
                patient_state=patient_state,
                patient_district=patient_district,
                patient_city=patient_city,
            )
            if ratio >= HOSPITAL_CANDIDATE_MATCH:
                reason = (
                    "Contains match"
                    if query_norm in record.normalized_name
                    or record.normalized_name in query_norm
                    else "Fuzzy name match"
                )
                candidates[id(record)] = (min(ratio, 1.0), reason, record)

        if not candidates:
            return _empty_match(
                ocr_hospital_name=ocr_name,
                status="not_found",
                match_reason="No hospital match found in PM-JAY directory",
                patient_state=patient_state,
                patient_district=patient_district,
                patient_city=patient_city,
            )

        scored = sorted(candidates.values(), key=lambda item: item[0], reverse=True)
        best_score, best_reason, best_record = scored[0]
        strong = [item for item in scored if item[0] >= max(0.6, best_score - HOSPITAL_MULTIPLE_GAP)]

        if len(strong) > 1 and best_score < HOSPITAL_STRONG_MATCH:
            return {
                "ocr_hospital_name": ocr_name,
                "matched_hospital_name": None,
                "confidence_score": round(best_score, 3),
                "match_reason": "Multiple possible PM-JAY hospital matches",
                "state": patient_state,
                "district": patient_district,
                "city": patient_city,
                "address": None,
                "hospital_type": None,
                "empanelment_type": None,
                "empanelment_status": None,
                "specialities": None,
                "source": None,
                "status": "manual_verification_required",
                "candidates": [
                    {
                        **record.to_public(),
                        "confidence_score": round(score, 3),
                        "match_reason": reason,
                    }
                    for score, reason, record in strong[:6]
                ],
            }

        status = _verification_status(best_record.empanelment_status, best_score)
        return {
            "ocr_hospital_name": ocr_name,
            "matched_hospital_name": best_record.hospital_name,
            "confidence_score": round(best_score, 3),
            "match_reason": best_reason,
            "state": best_record.state or patient_state,
            "district": best_record.district or patient_district,
            "city": best_record.city or patient_city,
            "address": best_record.address or None,
            "hospital_type": best_record.hospital_type or None,
            "empanelment_type": best_record.empanelment_type or None,
            "empanelment_status": best_record.empanelment_status,
            "specialities": best_record.specialities or None,
            "source": best_record.source or None,
            "status": status,
            "matched_hospital": best_record.to_public(),
            "candidates": [],
        }


def _normalize_empanelment_status(raw: str | None) -> str:
    text = (raw or "").strip().lower()
    if not text:
        return "unknown"
    if "suspend" in text:
        return "suspended"
    if "delist" in text or "de-empanel" in text or "de empanel" in text:
        return "delisted"
    if "active" in text or "approved" in text or "empanel" in text:
        return "active"
    return "unknown"


def _verification_status(empanelment_status: str, confidence: float) -> str:
    status = (empanelment_status or "").lower()
    if status == "suspended":
        return "suspended"
    if status == "delisted":
        return "delisted"
    if confidence < HOSPITAL_STRONG_MATCH:
        return "manual_verification_required"
    if status == "active":
        return "empanelled"
    if status == "unknown":
        return "unknown"
    return "manual_verification_required"


def _empty_match(
    *,
    ocr_hospital_name: str,
    status: str,
    match_reason: str,
    advisories: list[str] | None = None,
    patient_state: str | None = None,
    patient_district: str | None = None,
    patient_city: str | None = None,
) -> dict[str, Any]:
    return {
        "ocr_hospital_name": ocr_hospital_name,
        "matched_hospital_name": None,
        "confidence_score": 0.0,
        "match_reason": match_reason,
        "state": patient_state,
        "district": patient_district,
        "city": patient_city,
        "address": None,
        "hospital_type": None,
        "empanelment_type": None,
        "empanelment_status": None,
        "specialities": None,
        "source": None,
        "status": status,
        "candidates": [],
        "advisories": advisories or [],
    }


def _bill_shows_direct_payment(
    *,
    ocr_text: str | None,
    line_items: list[dict[str, Any]] | None,
) -> bool:
    haystack = (ocr_text or "").lower()
    if any(keyword in haystack for keyword in _DIRECT_PAYMENT_KEYWORDS):
        return True
    for item in line_items or []:
        name = str(item.get("item_name") or "").lower()
        if any(keyword in name for keyword in ("advance", "deposit", "cash paid", "self pay")):
            return True
    return False


def build_pmjay_hospital_verification(
    *,
    pmjay_selected: bool,
    ocr_hospital_name: str | None,
    patient_state: str | None = None,
    patient_district: str | None = None,
    patient_city: str | None = None,
    pmjay_has_ayushman_card: bool | None = None,
    line_items: list[dict[str, Any]] | None = None,
    ocr_text: str | None = None,
) -> dict[str, Any] | None:
    if not pmjay_selected:
        return None

    try:
        store = get_pmjay_hospital_store()
    except Exception:
        return {
            "selected": True,
            "ocr_hospital_name": ocr_hospital_name,
            "matched_hospital_name": None,
            "confidence_score": 0.0,
            "match_reason": "PM-JAY hospital database unavailable",
            "state": patient_state,
            "district": patient_district,
            "city": patient_city,
            "address": None,
            "hospital_type": None,
            "empanelment_type": None,
            "empanelment_status": None,
            "specialities": None,
            "source": None,
            "status": "manual_verification_required",
            "advisories": [_ADVISORY_DATABASE_MISSING],
            "candidates": [],
        }

    if not store.hospitals:
        return {
            "selected": True,
            "ocr_hospital_name": ocr_hospital_name,
            "matched_hospital_name": None,
            "confidence_score": 0.0,
            "match_reason": "PM-JAY hospital database empty",
            "state": patient_state,
            "district": patient_district,
            "city": patient_city,
            "address": None,
            "hospital_type": None,
            "empanelment_type": None,
            "empanelment_status": None,
            "specialities": None,
            "source": None,
            "status": "manual_verification_required",
            "advisories": [_ADVISORY_DATABASE_MISSING],
            "candidates": [],
        }

    match = store.match_pmjay_hospital(
        ocr_hospital_name,
        patient_state=patient_state,
        patient_district=patient_district,
        patient_city=patient_city,
    )
    advisories = list(match.pop("advisories", []) or [])
    status = str(match.get("status") or "unknown")

    if status == "empanelled":
        advisories.append(_ADVISORY_EMPANELLED)
    elif status in {"suspended", "delisted"}:
        advisories.append(_ADVISORY_SUSPENDED)
    elif status == "not_found":
        advisories.append(_ADVISORY_NOT_FOUND)
    elif status == "manual_verification_required":
        if match.get("candidates"):
            advisories.append(
                "Multiple possible PM-JAY hospital matches found. Confirm the correct hospital manually."
            )
        else:
            advisories.append(_ADVISORY_NOT_FOUND)

    if pmjay_has_ayushman_card is not True:
        advisories.append(_ADVISORY_ELIGIBILITY)

    if status == "empanelled" and _bill_shows_direct_payment(
        ocr_text=ocr_text,
        line_items=line_items,
    ):
        advisories.append(_ADVISORY_DIRECT_PAYMENT)

    return {
        "selected": True,
        **match,
        "advisories": _dedupe_messages(advisories),
    }


def _dedupe_messages(messages: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for message in messages:
        cleaned = _clean_spaces(message)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


_store: PmjayHospitalStore | None = None


def get_pmjay_hospital_store() -> PmjayHospitalStore:
    global _store
    if _store is None:
        _store = PmjayHospitalStore()
    return _store
