"""Aarogya Bhadratha Scheme data layer.

Loads the Telangana Aarogya Bhadratha empanelled-hospital directory (parsed from
the official district-wise PDF) and the approved-rate annexures (CSV), and
provides hospital verification, hospital search, rate matching, bill comparison
and report building.

The raw source files are large and slow to parse, so processed data is cached as
JSON under ``data/aarogya_bhadratha_cache/``. The cache is rebuilt lazily if it
is missing or older than the source files. ``scripts/build_aarogya_bhadratha_cache.py``
can also be run to (re)generate the cache ahead of time.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _BACKEND_ROOT / "data"
_CACHE_DIR = _DATA_DIR / "aarogya_bhadratha_cache"

# Confidence thresholds (documented in the implementation summary).
HOSPITAL_STRONG_MATCH = 0.82
HOSPITAL_CANDIDATE_MATCH = 0.55
HOSPITAL_MULTIPLE_GAP = 0.12
RATE_MATCH_THRESHOLD = 0.62
RATE_STRONG_MATCH = 0.84

_HOSPITAL_STRIP_TOKENS = frozenset(
    {
        "hospital",
        "hospitals",
        "hosp",
        "hosps",
        "medical",
        "med",
        "centre",
        "center",
        "clinic",
        "clinics",
        "institute",
        "inst",
        "nursing",
        "home",
        "homes",
        "pvt",
        "private",
        "ltd",
        "limited",
        "and",
        "the",
        "of",
        "a",
        "unit",
        "multi",
        "speciality",
        "specialities",
        "specialty",
        "super",
        "care",
        "res",
    }
)

# Common abbreviation expansions applied before normalization/matching so OCR
# shorthand lines up with the directory spelling.
_HOSPITAL_ABBREVIATIONS = [
    (r"\bhosps\b", "hospitals"),
    (r"\bhosp\b", "hospital"),
    (r"\binst\b", "institute"),
    (r"\bmed\s+college\b", "medical college"),
    (r"\bnursing\s+home\b", "nursing"),
    (r"\bcentre\b", "center"),
    (r"\bdr\b", "doctor"),
    (r"\bst\b", "saint"),
    (r"\bsuper\s+speciality\b", "super speciality"),
]

_PROCEDURE_ABBREVIATIONS = [
    (r"\binj\b", "injection"),
    (r"\btab\b", "tablet"),
    (r"\bigm\b", "immunoglobulin m"),
    (r"\busg\b", "ultrasound"),
    (r"\bct\b", "ct scan"),
    (r"\bmri\b", "mri scan"),
    (r"\becg\b", "electrocardiogram"),
    (r"\bcbc\b", "complete blood count"),
    (r"\bopd\b", "outpatient"),
    (r"\bip\b", "inpatient"),
    (r"\bicu\b", "intensive care unit"),
]


def _clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_hospital_name(name: str) -> str:
    """Normalize a hospital name for matching (lowercase, de-punctuated,
    abbreviation-expanded, common legal/suffix tokens removed)."""
    normalized = (name or "").lower().strip()
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = _clean_spaces(normalized)
    for pattern, repl in _HOSPITAL_ABBREVIATIONS:
        normalized = re.sub(pattern, repl, normalized)
    tokens = [t for t in normalized.split() if t not in _HOSPITAL_STRIP_TOKENS]
    return _clean_spaces(" ".join(tokens))


def normalize_procedure_name(name: str) -> str:
    """Normalize a procedure/package/service name for matching."""
    normalized = (name or "").lower().strip()
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = normalized.replace("&", " and ").replace("/", " ")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = _clean_spaces(normalized)
    for pattern, repl in _PROCEDURE_ABBREVIATIONS:
        normalized = re.sub(pattern, repl, normalized)
    return _clean_spaces(normalized)


def parse_rate_amount(value: Any) -> tuple[float | None, str]:
    """Parse a rate cell into (amount, unit).

    Handles currency symbols, Indian-number commas, decimals and "per Day"/
    "per Hour" units. Formula-style cells (e.g. "50% increase on NIMS tariff")
    return (None, "") so they are flagged for manual verification rather than
    treated as a fixed approved rate.
    """
    if value is None:
        return None, ""
    text = str(value).strip()
    if not text:
        return None, ""

    lowered = text.lower()
    unit = ""
    if "per day" in lowered:
        unit = "per day"
    elif "per hour" in lowered:
        unit = "per hour"

    # Formula / reference based rates cannot be compared numerically.
    if "%" in text or "nims" in lowered or "discount" in lowered or "increase" in lowered:
        return None, unit

    match = re.search(r"(\d[\d,]*\.?\d*)", text)
    if not match:
        return None, unit
    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None, unit
    if amount < 0:
        return None, unit
    return amount, unit


@dataclass(frozen=True)
class HospitalRecord:
    id: str
    sno: str
    district: str
    accreditation: str
    name: str
    name_raw: str
    address: str
    specialities: tuple[str, ...]
    specialities_text: str
    contact: str
    empanel_date: str
    dme_validity: str
    hospital_code: str | None
    normalized_name: str
    name_tokens: frozenset[str]

    def to_public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ref_no": self.sno,
            "name": self.name,
            "full_name": self.name_raw,
            "district": self.district.title() if self.district else "",
            "address": self.address,
            "specialities": list(self.specialities),
            "specialities_text": self.specialities_text,
            "accreditation": self.accreditation,
            "hospital_code": self.hospital_code,
            "empanelled_date": self.empanel_date,
            "dme_validity_upto": self.dme_validity,
        }


@dataclass(frozen=True)
class RateRecord:
    code: str
    name: str
    rate: float | None
    rate_text: str
    unit: str
    department: str
    category: str
    source: str
    normalized_name: str
    tokens: frozenset[str]


def _split_specialities(text: str) -> list[str]:
    text = _clean_spaces(text)
    if not text:
        return []
    # Drop roman-numeral / numeric list markers like "(i)", "(ii)", "(1)".
    text = re.sub(r"\((?:[ivxlcdm]+|\d+)\)", ",", text, flags=re.IGNORECASE)
    parts = re.split(r"[,;]\s*|\s+and\s+", text)
    seen: list[str] = []
    for part in parts:
        cleaned = _clean_spaces(part).strip(" .")
        if cleaned and cleaned.lower() not in {p.lower() for p in seen}:
            seen.append(cleaned)
    return seen


def _split_name_address(name_raw: str, district: str) -> tuple[str, str]:
    name_raw = _clean_spaces(name_raw)
    if not name_raw:
        return "", ""
    # Hospital name is generally the text before the first comma; the remainder
    # is the address. Guard against very short fragments.
    head, _, tail = name_raw.partition(",")
    name = _clean_spaces(head).strip(" .")
    address = _clean_spaces(tail).strip(" .")
    if not name:
        name = name_raw
    if not address:
        address = district.title() if district else ""
    return name, address


# --------------------------------------------------------------------------- #
# Raw source parsing                                                           #
# --------------------------------------------------------------------------- #
def _hospital_pdf_path() -> Path:
    candidates = sorted(_DATA_DIR.glob("*HOSPITAL*LIST*DISTRICT*WISE*.pdf"))
    if not candidates:
        candidates = sorted(_DATA_DIR.glob("*ospital*ist*istrict*ise*.pdf"))
    if not candidates:
        raise FileNotFoundError(
            "Aarogya Bhadratha hospital list PDF not found in data directory."
        )
    return candidates[0]


def _rates_source() -> Path:
    folder = next(
        (p for p in _DATA_DIR.glob("*arogya*hadratha*ates*") if p.is_dir()),
        None,
    )
    if folder is None:
        raise FileNotFoundError(
            "Aarogya Bhadratha rates folder not found in data directory."
        )
    return folder


def parse_hospitals_pdf(pdf_path: Path | None = None) -> list[dict[str, Any]]:
    """Parse the district-wise empanelled hospital PDF into hospital dicts."""
    import fitz  # imported lazily so non-PDF flows do not require PyMuPDF

    path = pdf_path or _hospital_pdf_path()
    doc = fitz.open(path)
    hospitals: list[dict[str, Any]] = []
    current_district: str | None = None
    seq = 0

    for page in doc:
        for table in page.find_tables().tables:
            for row in table.extract():
                cells = [_clean_spaces((c or "").replace("\n", " ")) for c in row]
                if not any(cells):
                    continue
                first = cells[0]
                if first.upper().startswith("S.NO"):
                    continue
                rest = [c for c in cells[1:] if c]
                # A lone non-numeric first cell is a district section header.
                if first and not rest and not first.isdigit():
                    current_district = first.strip()
                    continue
                if not first.isdigit():
                    continue

                seq += 1
                name_raw = cells[2] if len(cells) > 2 else ""
                district = current_district or ""
                name, address = _split_name_address(name_raw, district)
                specialities_text = cells[5] if len(cells) > 5 else ""
                hospitals.append(
                    {
                        "id": f"abh-{seq:04d}",
                        "sno": first,
                        "district": district,
                        "accreditation": cells[1] if len(cells) > 1 else "",
                        "name": name,
                        "name_raw": name_raw,
                        "address": address,
                        "specialities": _split_specialities(specialities_text),
                        "specialities_text": specialities_text,
                        "contact": cells[6] if len(cells) > 6 else "",
                        "empanel_date": cells[3] if len(cells) > 3 else "",
                        "dme_validity": cells[4] if len(cells) > 4 else "",
                        "hospital_code": None,
                    }
                )
    doc.close()
    if not hospitals:
        raise ValueError("No hospitals parsed from the Aarogya Bhadratha PDF.")
    return hospitals


def _read_csv_rows(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def _iter_annexure_csvs(source: Path) -> Iterable[tuple[str, list[dict[str, str]]]]:
    """Yield (annexure_name, rows) from either the zip or extracted CSVs."""
    zip_path = source / "files.zip"
    if zip_path.exists():
        with zipfile.ZipFile(zip_path) as archive:
            for name in sorted(archive.namelist()):
                if name.lower().endswith(".csv"):
                    yield Path(name).stem, _read_csv_rows(archive.read(name))
        return
    for csv_path in sorted(source.rglob("*.csv")):
        yield csv_path.stem, _read_csv_rows(csv_path.read_bytes())


def _get(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in row and row[key] is not None:
            return str(row[key]).strip()
        # tolerant header lookup (case/space-insensitive)
        for actual in row:
            if actual and actual.strip().lower() == key.strip().lower():
                value = row[actual]
                if value is not None:
                    return str(value).strip()
    return ""


def parse_rate_annexures(source: Path | None = None) -> dict[str, Any]:
    """Parse Aarogya Bhadratha rate annexures into a unified rate list.

    Returns a dict with ``rates`` (list of rate dicts) and ``unparsed`` (notes
    about annexures/rows that are not numeric rate tables).
    """
    src = source or _rates_source()
    rates: list[dict[str, Any]] = []
    unparsed: list[str] = []

    for name, rows in _iter_annexure_csvs(src):
        lname = name.lower()
        if not rows:
            unparsed.append(f"{name}: empty file")
            continue
        headers = {h.strip().lower() for h in rows[0].keys() if h}

        # annexure_1: ICD procedure packages
        if {"icd procedure code", "icd procedure name", "rate"} <= headers:
            for row in rows:
                code = _get(row, "ICD Procedure Code")
                pname = _get(row, "ICD Procedure Name")
                if not pname:
                    continue
                amount, unit = parse_rate_amount(_get(row, "Rate"))
                rates.append(
                    _rate_dict(
                        code=code,
                        name=pname,
                        amount=amount,
                        rate_text=_get(row, "Rate"),
                        unit=unit,
                        department=_get(row, "Category Code"),
                        category="procedure_package",
                        source=name,
                    )
                )
        # annexure_5: coded services (Department, Class, Code, Description, Rate)
        elif {"code", "description", "rate"} <= headers:
            for row in rows:
                pname = _get(row, "Description")
                if not pname:
                    continue
                amount, unit = parse_rate_amount(_get(row, "Rate"))
                rates.append(
                    _rate_dict(
                        code=_get(row, "Code"),
                        name=pname,
                        amount=amount,
                        rate_text=_get(row, "Rate"),
                        unit=unit,
                        department=_get(row, "Department", "Class"),
                        category="service",
                        source=name,
                    )
                )
        # annexure_6: named services (Department, Service Name, Cost)
        elif {"service name", "cost"} <= headers:
            for row in rows:
                pname = _get(row, "Service Name")
                if not pname:
                    continue
                amount, unit = parse_rate_amount(_get(row, "Cost"))
                rates.append(
                    _rate_dict(
                        code="",
                        name=pname,
                        amount=amount,
                        rate_text=_get(row, "Cost"),
                        unit=unit,
                        department=_get(row, "Department"),
                        category="investigation",
                        source=name,
                    )
                )
        # annexure_4: room rents / per-day services
        elif {"procedure/service", "rate"} <= headers or {
            "procedure / service",
            "rate",
        } <= headers:
            for row in rows:
                pname = _get(row, "Procedure/Service", "Procedure / Service")
                if not pname:
                    continue
                amount, unit = parse_rate_amount(_get(row, "Rate"))
                rates.append(
                    _rate_dict(
                        code="",
                        name=pname,
                        amount=amount,
                        rate_text=_get(row, "Rate"),
                        unit=unit,
                        department="Room/General",
                        category="room",
                        source=name,
                    )
                )
        else:
            unparsed.append(
                f"{name}: not a numeric rate table (headers: {sorted(headers)}) — "
                "used for scheme reference only"
            )

    if not rates:
        raise ValueError("No Aarogya Bhadratha rate rows parsed.")
    return {"rates": rates, "unparsed": unparsed}


def _rate_dict(
    *,
    code: str,
    name: str,
    amount: float | None,
    rate_text: str,
    unit: str,
    department: str,
    category: str,
    source: str,
) -> dict[str, Any]:
    return {
        "code": (code or "").strip().upper(),
        "name": name.strip(),
        "rate": amount,
        "rate_text": rate_text,
        "unit": unit,
        "department": department.strip(),
        "category": category,
        "source": source,
        "normalized_name": normalize_procedure_name(name),
    }


# --------------------------------------------------------------------------- #
# Data store with matching / search / comparison                              #
# --------------------------------------------------------------------------- #
@dataclass
class AarogyaDataStore:
    hospitals: list[HospitalRecord] = field(default_factory=list)
    rates: list[RateRecord] = field(default_factory=list)
    unparsed_notes: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)

    _hospital_exact: dict[str, list[HospitalRecord]] = field(default_factory=dict)
    _hospital_token: dict[str, list[HospitalRecord]] = field(default_factory=dict)
    _rate_by_code: dict[str, list[RateRecord]] = field(default_factory=dict)
    _rate_exact: dict[str, list[RateRecord]] = field(default_factory=dict)
    _rate_token: dict[str, list[RateRecord]] = field(default_factory=dict)
    _districts: list[str] = field(default_factory=list)
    _specialities: list[str] = field(default_factory=list)

    # -- construction ------------------------------------------------------- #
    @classmethod
    def from_dicts(
        cls,
        hospital_dicts: list[dict[str, Any]],
        rate_payload: dict[str, Any],
        sources: dict[str, str] | None = None,
    ) -> "AarogyaDataStore":
        store = cls(sources=sources or {})
        for h in hospital_dicts:
            normalized = normalize_hospital_name(h.get("name_raw") or h.get("name", ""))
            record = HospitalRecord(
                id=h["id"],
                sno=str(h.get("sno", "")),
                district=h.get("district", ""),
                accreditation=h.get("accreditation", ""),
                name=h.get("name", ""),
                name_raw=h.get("name_raw", ""),
                address=h.get("address", ""),
                specialities=tuple(h.get("specialities", [])),
                specialities_text=h.get("specialities_text", ""),
                contact=h.get("contact", ""),
                empanel_date=h.get("empanel_date", ""),
                dme_validity=h.get("dme_validity", ""),
                hospital_code=h.get("hospital_code"),
                normalized_name=normalized,
                name_tokens=frozenset(t for t in normalized.split() if len(t) >= 3),
            )
            store.hospitals.append(record)
            store._hospital_exact.setdefault(normalized, []).append(record)
            for token in record.name_tokens:
                store._hospital_token.setdefault(token, []).append(record)

        for r in rate_payload.get("rates", []):
            normalized = r.get("normalized_name") or normalize_procedure_name(
                r.get("name", "")
            )
            record = RateRecord(
                code=r.get("code", ""),
                name=r.get("name", ""),
                rate=r.get("rate"),
                rate_text=r.get("rate_text", ""),
                unit=r.get("unit", ""),
                department=r.get("department", ""),
                category=r.get("category", ""),
                source=r.get("source", ""),
                normalized_name=normalized,
                tokens=frozenset(t for t in normalized.split() if len(t) >= 3),
            )
            store.rates.append(record)
            if record.code:
                store._rate_by_code.setdefault(record.code, []).append(record)
            if normalized:
                store._rate_exact.setdefault(normalized, []).append(record)
            for token in record.tokens:
                store._rate_token.setdefault(token, []).append(record)

        store.unparsed_notes = list(rate_payload.get("unparsed", []))
        store._districts = sorted(
            {h.district.title() for h in store.hospitals if h.district}
        )
        store._specialities = store._build_speciality_list()
        return store

    def _build_speciality_list(self) -> list[str]:
        counts: dict[str, int] = {}
        for hospital in self.hospitals:
            for spec in hospital.specialities:
                key = _clean_spaces(spec).title()
                if 2 < len(key) <= 60 and "ailment" not in key.lower():
                    counts[key] = counts.get(key, 0) + 1
        return sorted(k for k, v in counts.items() if v >= 2)

    # -- directory ---------------------------------------------------------- #
    def list_districts(self) -> list[str]:
        return list(self._districts)

    def list_specialities(self) -> list[str]:
        return list(self._specialities)

    def search_hospitals(
        self,
        *,
        query: str = "",
        district: str = "",
        speciality: str = "",
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        query_norm = _clean_spaces((query or "").lower())
        district_norm = _clean_spaces((district or "").lower())
        speciality_norm = _clean_spaces((speciality or "").lower())

        results: list[HospitalRecord] = []
        for hospital in self.hospitals:
            if district_norm and hospital.district.lower() != district_norm:
                continue
            if speciality_norm and speciality_norm not in hospital.specialities_text.lower():
                continue
            if query_norm:
                haystack = " ".join(
                    [
                        hospital.name_raw,
                        hospital.district,
                        hospital.address,
                        hospital.specialities_text,
                    ]
                ).lower()
                if not all(term in haystack for term in query_norm.split()):
                    continue
            results.append(hospital)

        total = len(results)
        page = max(int(page or 1), 1)
        limit = max(min(int(limit or 20), 100), 1)
        start = (page - 1) * limit
        page_items = results[start : start + limit]
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": start + limit < total,
            "results": [h.to_public() for h in page_items],
        }

    def get_hospital(self, hospital_id: str) -> HospitalRecord | None:
        for hospital in self.hospitals:
            if hospital.id == hospital_id:
                return hospital
        return None

    # -- hospital verification --------------------------------------------- #
    def _score_hospital(
        self, normalized: str, input_tokens: set[str], record: HospitalRecord
    ) -> float:
        if not record.name_tokens or not input_tokens:
            return 0.0
        overlap = len(input_tokens & record.name_tokens) / len(
            input_tokens | record.name_tokens
        )
        sequence = SequenceMatcher(None, normalized, record.normalized_name).ratio()
        return round((0.6 * overlap) + (0.4 * sequence), 4)

    def verify_hospital(
        self,
        ocr_name: str,
        *,
        district: str = "",
        address: str = "",
    ) -> dict[str, Any]:
        ocr_name = (ocr_name or "").strip()
        normalized = normalize_hospital_name(ocr_name)
        district_norm = _clean_spaces((district or "").lower())
        context = f"{address or ''} {district or ''}".lower()

        base = {
            "ocr_hospital_name": ocr_name,
            "normalized_name": normalized,
            "matched_hospital": None,
            "match_confidence": 0.0,
            "match_method": "none",
            "empanelment_status": "not_found",
            "candidates": [],
        }
        if not normalized:
            base["empanelment_status"] = "name_missing"
            return base

        # 1) exact normalized name
        exact = self._hospital_exact.get(normalized, [])
        exact = self._prefer_district(exact, district_norm)
        if exact:
            chosen = exact[0]
            return self._empanelled(base, chosen, 1.0, "exact_name")

        input_tokens = {t for t in normalized.split() if len(t) >= 3}
        candidates: dict[str, HospitalRecord] = {}
        for token in input_tokens:
            for record in self._hospital_token.get(token, []):
                candidates[record.id] = record

        scored: list[tuple[float, HospitalRecord]] = []
        for record in candidates.values():
            score = self._score_hospital(normalized, input_tokens, record)
            # Boost when district/address context agrees.
            if district_norm and record.district.lower() == district_norm:
                score = min(1.0, score + 0.1)
            elif context.strip() and record.district and record.district.lower() in context:
                score = min(1.0, score + 0.07)
            if score >= HOSPITAL_CANDIDATE_MATCH:
                scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            return base

        # 2) name + district exact-ish (substring containment) with district agree
        for score, record in scored:
            if (
                district_norm
                and record.district.lower() == district_norm
                and (
                    record.normalized_name in normalized
                    or normalized in record.normalized_name
                )
            ):
                return self._empanelled(base, record, max(score, 0.9), "name_district")

        top_score, top_record = scored[0]
        strong = [s for s in scored if s[0] >= max(0.6, top_score - HOSPITAL_MULTIPLE_GAP)]

        # 3) single strong match -> empanelled (approximate / fuzzy)
        if top_score >= HOSPITAL_STRONG_MATCH and len(strong) == 1:
            method = "fuzzy" if top_score < 0.95 else "exact_name"
            return self._empanelled(base, top_record, top_score, method)

        # 4) multiple plausible matches -> ask the user to confirm
        if len(strong) > 1 or (top_score >= HOSPITAL_CANDIDATE_MATCH and top_score < HOSPITAL_STRONG_MATCH):
            base["empanelment_status"] = "multiple"
            base["match_method"] = "multiple_candidates"
            base["match_confidence"] = top_score
            base["candidates"] = [
                {**rec.to_public(), "match_confidence": sc}
                for sc, rec in scored[:6]
            ]
            return base

        return base

    @staticmethod
    def _prefer_district(
        records: list[HospitalRecord], district_norm: str
    ) -> list[HospitalRecord]:
        if not records or not district_norm:
            return records
        same = [r for r in records if r.district.lower() == district_norm]
        return same or records

    @staticmethod
    def _empanelled(
        base: dict[str, Any],
        record: HospitalRecord,
        confidence: float,
        method: str,
    ) -> dict[str, Any]:
        result = dict(base)
        result["matched_hospital"] = record.to_public()
        result["match_confidence"] = round(float(confidence), 4)
        result["match_method"] = method
        result["empanelment_status"] = "empanelled"
        result["candidates"] = [record.to_public()]
        return result

    # -- rate matching ------------------------------------------------------ #
    def _candidate_rates(self, normalized: str) -> list[RateRecord]:
        tokens = [t for t in normalized.split() if len(t) >= 3]
        if not tokens:
            return []
        seen: set[int] = set()
        candidates: list[RateRecord] = []
        for token in tokens:
            for record in self._rate_token.get(token, ()):  # noqa: B007
                if id(record) in seen:
                    continue
                seen.add(id(record))
                candidates.append(record)
                if len(candidates) >= 900:
                    return candidates
        return candidates

    def match_rate(
        self, item_name: str, *, code_hint: str = ""
    ) -> dict[str, Any] | None:
        normalized = normalize_procedure_name(item_name)
        if not normalized:
            return None

        # 1) explicit code in item name or provided hint
        codes_to_try = []
        if code_hint:
            codes_to_try.append(code_hint.strip().upper())
        icd = re.search(r"\b([A-TV-Z]\d{2}(?:\.\d{1,2})?)\b", (item_name or "").upper())
        if icd:
            codes_to_try.append(icd.group(1))
        numeric = re.search(r"\b(\d{3,5})\b", item_name or "")
        if numeric:
            codes_to_try.append(numeric.group(1))
        for code in codes_to_try:
            for record in self._rate_by_code.get(code, ()):  # noqa: B007
                return self._rate_payload(record, 1.0, "exact_code")

        # 2) exact normalized name
        for record in self._rate_exact.get(normalized, ()):  # noqa: B007
            return self._rate_payload(record, 0.97, "exact_name")

        candidates = self._candidate_rates(normalized)
        # 3) containment (strong name)
        for record in candidates:
            ref = record.normalized_name
            if ref and len(ref) >= 4 and (ref in normalized or normalized in ref):
                return self._rate_payload(record, 0.88, "strong_name")

        # 4) controlled fuzzy
        input_tokens = set(normalized.split())
        best: tuple[float, RateRecord] | None = None
        for record in candidates:
            if not record.tokens or not input_tokens:
                continue
            overlap = len(input_tokens & record.tokens) / len(
                input_tokens | record.tokens
            )
            sequence = SequenceMatcher(
                None, normalized, record.normalized_name
            ).ratio()
            score = (0.6 * overlap) + (0.4 * sequence)
            if best is None or score > best[0]:
                best = (score, record)

        if best and best[0] >= RATE_MATCH_THRESHOLD:
            method = "fuzzy" if best[0] < RATE_STRONG_MATCH else "strong_name"
            return self._rate_payload(best[1], round(best[0], 4), method)
        return None

    @staticmethod
    def _rate_payload(
        record: RateRecord, confidence: float, method: str
    ) -> dict[str, Any]:
        return {
            "matched_name": record.name,
            "code": record.code,
            "rate": record.rate,
            "rate_text": record.rate_text,
            "unit": record.unit,
            "department": record.department,
            "category": record.category,
            "source": record.source,
            "match_confidence": round(float(confidence), 4),
            "match_method": method,
        }

    # -- bill comparison ---------------------------------------------------- #
    def compare_bill_items(self, line_items: list[dict[str, Any]]) -> dict[str, Any]:
        compared: list[dict[str, Any]] = []
        total_charged = 0.0
        total_approved = 0.0
        total_excess = 0.0
        total_below = 0.0
        matched_count = 0
        unmatched_count = 0
        manual_count = 0

        for raw in line_items:
            item_name = str(raw.get("item_name", "")).strip()
            quantity = max(_to_float(raw.get("quantity")), 0.0) or 1.0
            unit_price = max(_to_float(raw.get("unit_price")), 0.0)
            charged = _to_float(raw.get("total_price"))
            if charged <= 0 and unit_price > 0:
                charged = round(quantity * unit_price, 2)
            total_charged += max(charged, 0.0)

            entry: dict[str, Any] = {
                "item_name": item_name,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": round(charged, 2),
                "category": raw.get("category", "other"),
                "matched_name": None,
                "matched_code": None,
                "approved_unit_rate": None,
                "approved_amount": None,
                "difference": None,
                "excess_amount": None,
                "percentage_difference": None,
                "match_confidence": 0.0,
                "match_method": "none",
                "rate_source": None,
                "status": "Rate Not Found",
                "note": "Rate not found in the Aarogya Bhadratha rates database.",
            }

            if not item_name:
                unmatched_count += 1
                compared.append(entry)
                continue

            match = self.match_rate(item_name)
            if match is None:
                unmatched_count += 1
                compared.append(entry)
                continue

            entry["matched_name"] = match["matched_name"]
            entry["matched_code"] = match["code"] or None
            entry["match_confidence"] = match["match_confidence"]
            entry["match_method"] = match["match_method"]
            entry["rate_source"] = match["source"]
            entry["approved_unit_rate"] = match["rate"]
            entry["matched_unit"] = match["unit"]

            approved_rate = match["rate"]
            # Uncertain match or non-numeric (formula) rate -> manual verification.
            if approved_rate is None or match["match_confidence"] < RATE_MATCH_THRESHOLD:
                entry["status"] = "Manual Verification Required"
                entry["note"] = (
                    "Matched to a scheme entry but the approved rate is "
                    "formula-based or the match is uncertain — verify manually."
                    if approved_rate is None
                    else "Match confidence is low — verify manually."
                )
                manual_count += 1
                compared.append(entry)
                continue

            # Bundled package rates (procedure packages / per-day room rents) are
            # compared as a single approved amount, not multiplied by quantity,
            # to avoid double counting package components.
            if match["category"] in {"procedure_package"}:
                approved_amount = round(approved_rate, 2)
            else:
                approved_amount = round(approved_rate * quantity, 2)

            difference = round(charged - approved_amount, 2)
            pct = round((difference / approved_amount) * 100, 2) if approved_amount else None
            entry["approved_amount"] = approved_amount
            entry["difference"] = difference
            entry["percentage_difference"] = pct

            total_approved += approved_amount
            matched_count += 1
            if difference > 0:
                entry["excess_amount"] = difference
                entry["status"] = "Above Approved Rate"
                total_excess += difference
            elif difference < 0:
                entry["excess_amount"] = 0.0
                entry["status"] = "Below Approved Rate"
                total_below += abs(difference)
            else:
                entry["excess_amount"] = 0.0
                entry["status"] = "Within Approved Rate"
            entry["note"] = ""
            compared.append(entry)

        pct_diff = (
            round((total_excess - total_below) / total_approved * 100, 2)
            if total_approved
            else None
        )
        summary = {
            "total_charged": round(total_charged, 2),
            "total_approved_matched": round(total_approved, 2),
            "total_possible_excess": round(total_excess, 2),
            "total_below_approved": round(total_below, 2),
            "percentage_difference": pct_diff,
            "matched_items": matched_count,
            "unmatched_items": unmatched_count,
            "manual_verification_items": manual_count,
            "total_items": len(line_items),
        }
        return {"items": compared, "summary": summary}


def _to_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------- #
# Cache + singleton                                                            #
# --------------------------------------------------------------------------- #
def _cache_paths() -> tuple[Path, Path]:
    return _CACHE_DIR / "hospitals.json", _CACHE_DIR / "rates.json"


def build_and_cache() -> dict[str, Any]:
    """Parse raw sources and write JSON caches. Returns the parsed payloads."""
    import json

    hospitals = parse_hospitals_pdf()
    rate_payload = parse_rate_annexures()
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    hosp_path, rate_path = _cache_paths()
    hosp_path.write_text(
        json.dumps({"hospitals": hospitals}, ensure_ascii=False),
        encoding="utf-8",
    )
    rate_path.write_text(
        json.dumps(rate_payload, ensure_ascii=False), encoding="utf-8"
    )
    return {"hospitals": hospitals, "rates": rate_payload}


def _load_payloads() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    import json

    hosp_path, rate_path = _cache_paths()
    sources: dict[str, str] = {}
    if hosp_path.exists() and rate_path.exists():
        hospitals = json.loads(hosp_path.read_text(encoding="utf-8")).get(
            "hospitals", []
        )
        rate_payload = json.loads(rate_path.read_text(encoding="utf-8"))
        sources = {"hospitals": "cache", "rates": "cache"}
        if hospitals and rate_payload.get("rates"):
            return hospitals, rate_payload, sources

    built = build_and_cache()
    return built["hospitals"], built["rates"], {"hospitals": "parsed", "rates": "parsed"}


_store: AarogyaDataStore | None = None


def get_aarogya_store() -> AarogyaDataStore:
    global _store
    if _store is None:
        hospitals, rate_payload, sources = _load_payloads()
        _store = AarogyaDataStore.from_dicts(hospitals, rate_payload, sources)
    return _store
