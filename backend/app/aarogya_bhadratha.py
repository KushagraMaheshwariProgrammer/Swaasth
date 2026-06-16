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

# --------------------------------------------------------------------------- #
# EHS Payment Rules - Ceiling Limits (G.O.Ms.No.101, 1-12-2015)               #
# --------------------------------------------------------------------------- #
CEILING_GENERAL = 500_000       # Rs. 5 lakh for general ailments
CEILING_MAJOR = 750_000         # Rs. 7.5 lakh for major ailments
ANNUAL_CAP_AUTO = 800_000       # Rs. 8 lakh automatic family limit per FY
ANNUAL_CAP_DGP = 1_500_000      # Rs. 15 lakh with DGP approval

# Major ailment categories (heart surgery, kidney transplant, cancer, neuro-surgery)
MAJOR_AILMENT_CATEGORIES = frozenset({
    "CARDIOTHORASIC SURGERY",   # heart surgery
    "NEURO SURGERY",            # neuro-surgery
    "MEDICAL ONCOLOGY",         # cancer
    "SURGICAL ONCOLOGY",        # cancer
    "RADIATION ONCOLOGY",       # cancer
})

# Keywords for kidney transplant procedures (checked separately within GENITO URINARY)
KIDNEY_TRANSPLANT_KEYWORDS = frozenset({
    "kidney transplant",
    "renal transplant",
    "transplant kidney",
    "transplant renal",
})

# Hospital type constants
HOSPITAL_TYPE_NON_NABH = "non_nabh"
HOSPITAL_TYPE_NABH = "nabh"
HOSPITAL_TYPE_NABH_SUPER = "nabh_super"

# Payment basis constants
PAYMENT_BASIS_PACKAGE = "package"
PAYMENT_BASIS_PACKAGE_PLUS_CONSUMABLES = "package_plus_consumables"
PAYMENT_BASIS_ACTUAL = "actual"

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
    # Keep distinctive tokens when only generic suffixes remain (e.g. "Care Hospital").
    if not tokens:
        tokens = [t for t in normalized.split() if len(t) >= 2]
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

    def get_hospital_type(self) -> str:
        """Classify hospital by accreditation for payment rule selection.

        Returns:
            'non_nabh': Non-NABH hospitals - package rates only
            'nabh': Regular NABH hospitals - package rates only
            'nabh_super': NABH Super Specialty - package + consumables at actual
        """
        acc = (self.accreditation or "").upper()
        if "SUPER" in acc:
            return HOSPITAL_TYPE_NABH_SUPER
        if "NABH" in acc and "NON" not in acc:
            return HOSPITAL_TYPE_NABH
        return HOSPITAL_TYPE_NON_NABH

    def get_payment_basis(self) -> str:
        """Determine payment basis for this hospital type.

        Returns:
            'package': All-inclusive package rates
            'package_plus_consumables': Package + consumables at actual (NABH Super)
        """
        if self.get_hospital_type() == HOSPITAL_TYPE_NABH_SUPER:
            return PAYMENT_BASIS_PACKAGE_PLUS_CONSUMABLES
        return PAYMENT_BASIS_PACKAGE

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
            "hospital_type": self.get_hospital_type(),
            "payment_basis": self.get_payment_basis(),
        }


@dataclass(frozen=True)
class RateRecord:
    code: str
    name: str
    rate: float | None               # Legacy single rate (for backward compat)
    rate_non_nabh: float | None      # Price_Private_Non_NABH from EHS
    rate_nabh: float | None          # Price_Private_NABH from EHS
    rate_text: str
    unit: str
    department: str
    category: str
    category_hierarchy: str          # e.g., "NEURO SURGERY", "GENERAL SURGERY"
    source: str
    normalized_name: str
    tokens: frozenset[str]
    is_major_ailment: bool           # True if category_hierarchy in MAJOR_AILMENT_CATEGORIES

    def get_rate_for_hospital_type(self, hospital_type: str) -> float | None:
        """Get the appropriate rate based on hospital accreditation type."""
        if hospital_type in (HOSPITAL_TYPE_NABH, HOSPITAL_TYPE_NABH_SUPER):
            return self.rate_nabh if self.rate_nabh is not None else self.rate
        return self.rate_non_nabh if self.rate_non_nabh is not None else self.rate


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


def _ehs_excel_path() -> Path | None:
    """Find the EHS Excel file with category hierarchy and hospital-type rates."""
    candidates = sorted(_DATA_DIR.glob("**/EHS*with*Category*.xlsx"))
    if not candidates:
        candidates = sorted(_DATA_DIR.glob("**/EHS*.xlsx"))
    return candidates[0] if candidates else None


def parse_ehs_excel(excel_path: Path | None = None) -> dict[str, Any]:
    """Parse the EHS Excel file with hospital-type-specific package rates.

    The EHS file contains 1,885 procedures with 4 price columns:
    - Price_Semi_Private_Non_NABH
    - Price_Private_Non_NABH (used for Non-NABH hospitals)
    - Price_Semi_Private_NABH
    - Price_Private_NABH (used for NABH and NABH Super Specialty)

    Returns a dict with ``rates`` (list of rate dicts) and ``unparsed`` notes.
    """
    try:
        import openpyxl
    except ImportError:
        return {"rates": [], "unparsed": ["openpyxl not installed - EHS parsing skipped"]}

    path = excel_path or _ehs_excel_path()
    if path is None or not path.exists():
        return {"rates": [], "unparsed": ["EHS Excel file not found"]}

    rates: list[dict[str, Any]] = []
    unparsed: list[str] = []

    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet = workbook.active
        if sheet is None:
            return {"rates": [], "unparsed": ["EHS Excel has no active sheet"]}

        # Read header row
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return {"rates": [], "unparsed": ["EHS Excel is empty"]}

        headers = [str(h or "").strip() for h in rows[0]]
        header_map = {h.lower(): i for i, h in enumerate(headers)}

        # Required columns
        required = ["procedure_name", "price_private_non_nabh", "price_private_nabh"]
        missing = [r for r in required if r not in header_map]
        if missing:
            unparsed.append(f"EHS missing columns: {missing}")
            return {"rates": rates, "unparsed": unparsed}

        # Column indices
        cat_idx = header_map.get("category_hierarchy")
        code_idx = header_map.get("procedure_icd_code")
        name_idx = header_map.get("procedure_name")
        non_nabh_idx = header_map.get("price_private_non_nabh")
        nabh_idx = header_map.get("price_private_nabh")
        spec_idx = header_map.get("applicable_speciality_code")

        for row in rows[1:]:
            if not row or len(row) <= max(name_idx, non_nabh_idx, nabh_idx):
                continue

            proc_name = str(row[name_idx] or "").strip()
            if not proc_name:
                continue

            category_hierarchy = str(row[cat_idx] or "").strip().upper() if cat_idx is not None else ""
            icd_code = str(row[code_idx] or "").strip() if code_idx is not None else ""
            spec_code = str(row[spec_idx] or "").strip() if spec_idx is not None else ""

            # Parse rates
            rate_non_nabh, _ = parse_rate_amount(row[non_nabh_idx])
            rate_nabh, _ = parse_rate_amount(row[nabh_idx])

            # Use NABH rate as the legacy single rate for backward compat
            legacy_rate = rate_nabh if rate_nabh is not None else rate_non_nabh

            # Determine if major ailment
            is_major = category_hierarchy in MAJOR_AILMENT_CATEGORIES
            if not is_major:
                name_lower = proc_name.lower()
                is_major = any(kw in name_lower for kw in KIDNEY_TRANSPLANT_KEYWORDS)

            rates.append(
                _rate_dict(
                    code=icd_code,
                    name=proc_name,
                    amount=legacy_rate,
                    rate_non_nabh=rate_non_nabh,
                    rate_nabh=rate_nabh,
                    rate_text=str(rate_nabh) if rate_nabh else "",
                    unit="",
                    department=spec_code,
                    category="procedure_package",
                    category_hierarchy=category_hierarchy,
                    source="EHS_2017",
                    is_major_ailment=is_major,
                )
            )

        workbook.close()
    except Exception as exc:
        unparsed.append(f"EHS Excel parse error: {exc}")

    return {"rates": rates, "unparsed": unparsed}


def _rate_dict(
    *,
    code: str,
    name: str,
    amount: float | None = None,
    rate_non_nabh: float | None = None,
    rate_nabh: float | None = None,
    rate_text: str,
    unit: str,
    department: str,
    category: str,
    category_hierarchy: str = "",
    source: str,
    is_major_ailment: bool = False,
) -> dict[str, Any]:
    return {
        "code": (code or "").strip().upper(),
        "name": name.strip(),
        "rate": amount,
        "rate_non_nabh": rate_non_nabh,
        "rate_nabh": rate_nabh,
        "rate_text": rate_text,
        "unit": unit,
        "department": department.strip(),
        "category": category,
        "category_hierarchy": category_hierarchy.strip().upper(),
        "source": source,
        "normalized_name": normalize_procedure_name(name),
        "is_major_ailment": is_major_ailment,
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
            category_hierarchy = r.get("category_hierarchy", "").upper()
            # Determine major ailment status
            is_major = r.get("is_major_ailment", False)
            if not is_major and category_hierarchy:
                is_major = category_hierarchy in MAJOR_AILMENT_CATEGORIES
            # Also check for kidney transplant keywords
            if not is_major:
                name_lower = r.get("name", "").lower()
                is_major = any(kw in name_lower for kw in KIDNEY_TRANSPLANT_KEYWORDS)

            record = RateRecord(
                code=r.get("code", ""),
                name=r.get("name", ""),
                rate=r.get("rate"),
                rate_non_nabh=r.get("rate_non_nabh"),
                rate_nabh=r.get("rate_nabh"),
                rate_text=r.get("rate_text", ""),
                unit=r.get("unit", ""),
                department=r.get("department", ""),
                category=r.get("category", ""),
                category_hierarchy=category_hierarchy,
                source=r.get("source", ""),
                normalized_name=normalized,
                tokens=frozenset(t for t in normalized.split() if len(t) >= 3),
                is_major_ailment=is_major,
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

        query_terms = [
            term
            for term in query_norm.split()
            if len(term) >= 2 and term not in _HOSPITAL_STRIP_TOKENS
        ]
        if query_norm and not query_terms:
            query_terms = [term for term in query_norm.split() if term]

        scored: list[tuple[float, HospitalRecord]] = []
        for hospital in self.hospitals:
            if district_norm and hospital.district.lower() != district_norm:
                continue
            if speciality_norm and speciality_norm not in hospital.specialities_text.lower():
                continue
            score = 1.0
            if query_terms:
                haystack = " ".join(
                    [
                        hospital.name_raw,
                        hospital.name,
                        hospital.normalized_name,
                        hospital.district,
                        hospital.address,
                        hospital.specialities_text,
                    ]
                ).lower()
                matched = sum(1 for term in query_terms if term in haystack)
                if matched == 0:
                    continue
                score = matched / len(query_terms)
                if query_norm in haystack:
                    score += 0.5
            scored.append((score, hospital))

        scored.sort(key=lambda item: item[0], reverse=True)
        results = [record for _, record in scored]

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
        if not input_tokens:
            return 0.0
        record_token_set = set(record.name_tokens)
        matched_tokens = input_tokens & record_token_set
        if not matched_tokens:
            haystack = f"{record.normalized_name} {record.name_raw.lower()}"
            matched_tokens = {t for t in input_tokens if t in haystack}
        if not matched_tokens:
            return 0.0

        input_coverage = len(matched_tokens) / len(input_tokens)
        union = input_tokens | record_token_set
        overlap = len(matched_tokens) / len(union) if union else input_coverage
        sequence = SequenceMatcher(None, normalized, record.normalized_name).ratio()

        # Bill names often contain only a brand ("Apollo Hospital", "KIMS").
        if len(input_tokens) <= 2:
            return round(0.75 * input_coverage + 0.25 * max(sequence, overlap), 4)
        return round((0.45 * input_coverage) + (0.25 * overlap) + (0.3 * sequence), 4)

    def _gather_hospital_candidates(
        self, input_tokens: set[str], *, district_norm: str = ""
    ) -> dict[str, HospitalRecord]:
        candidates: dict[str, HospitalRecord] = {}
        for token in input_tokens:
            for record in self._hospital_token.get(token, ()):
                candidates[record.id] = record

        if candidates:
            return candidates

        for record in self.hospitals:
            if district_norm and record.district.lower() != district_norm:
                continue
            haystack = " ".join(
                [
                    record.name_raw,
                    record.name,
                    record.normalized_name,
                    record.address,
                    record.district,
                ]
            ).lower()
            if any(token in haystack for token in input_tokens):
                candidates[record.id] = record
        return candidates

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

        input_tokens = {
            t
            for t in normalized.split()
            if len(t) >= 3 and t not in _HOSPITAL_STRIP_TOKENS
        }
        if not input_tokens:
            input_tokens = {t for t in normalized.split() if len(t) >= 2}
        candidates = self._gather_hospital_candidates(
            input_tokens, district_norm=district_norm
        )

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

        if district_norm:
            district_scored = [
                (score, record)
                for score, record in scored
                if record.district.lower() == district_norm
            ]
            if district_scored:
                scored = district_scored

        if not scored:
            return base

        # 2) name + district exact-ish (substring containment) with district agree
        # Skip for brand-only bill names (e.g. "Apollo") that match many branches.
        has_specific_name = len(input_tokens) >= 2 or len(normalized) >= 12
        if has_specific_name:
            for score, record in scored:
                if (
                    district_norm
                    and record.district.lower() == district_norm
                    and (
                        record.normalized_name in normalized
                        or normalized in record.normalized_name
                    )
                ):
                    return self._empanelled(
                        base, record, max(score, 0.9), "name_district"
                    )

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
            "rate_non_nabh": record.rate_non_nabh,
            "rate_nabh": record.rate_nabh,
            "rate_text": record.rate_text,
            "unit": record.unit,
            "department": record.department,
            "category": record.category,
            "category_hierarchy": record.category_hierarchy,
            "source": record.source,
            "match_confidence": round(float(confidence), 4),
            "match_method": method,
            "is_major_ailment": record.is_major_ailment,
        }

    # -- bill comparison ---------------------------------------------------- #
    def compare_bill_items(
        self,
        line_items: list[dict[str, Any]],
        hospital: HospitalRecord | None = None,
        consumable_indices: list[int] | None = None,
    ) -> dict[str, Any]:
        """Compare bill line items against scheme rates.

        Args:
            line_items: List of bill items with item_name, quantity, total_price, etc.
            hospital: The empanelled hospital (for hospital-type-based rate selection).
            consumable_indices: Indices of items marked as consumables by user
                (for NABH Super Specialty: passed at actual cost instead of package rate).

        Returns:
            Comparison results with items, summary, ceiling info, and payment basis.
        """
        from app.medicine_comparison import (
            compare_line_item_with_nppa,
            pharma_to_aarogya_item,
            should_use_nppa_result,
        )

        consumable_set = set(consumable_indices or [])
        hospital_type = hospital.get_hospital_type() if hospital else HOSPITAL_TYPE_NON_NABH
        payment_basis = hospital.get_payment_basis() if hospital else PAYMENT_BASIS_PACKAGE

        compared: list[dict[str, Any]] = []
        total_charged = 0.0
        total_approved = 0.0
        total_excess = 0.0
        total_below = 0.0
        total_consumables_actual = 0.0
        matched_count = 0
        unmatched_count = 0
        manual_count = 0
        consumables_at_actual: list[dict[str, Any]] = []
        major_ailment_categories: set[str] = set()
        has_major_ailment = False

        for idx, raw in enumerate(line_items):
            item_name = str(raw.get("item_name", "")).strip()
            quantity = max(_to_float(raw.get("quantity")), 0.0) or 1.0
            unit_price = max(_to_float(raw.get("unit_price")), 0.0)
            charged = _to_float(raw.get("total_price"))
            if charged <= 0 and unit_price > 0:
                charged = round(quantity * unit_price, 2)
            total_charged += max(charged, 0.0)

            is_consumable = idx in consumable_set
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
                "is_consumable": is_consumable,
                "category_hierarchy": "",
                "is_major_ailment": False,
            }

            # For NABH Super Specialty: consumables are passed at actual cost
            if is_consumable and hospital_type == HOSPITAL_TYPE_NABH_SUPER:
                entry["status"] = "Consumable At Actual"
                entry["approved_amount"] = round(charged, 2)
                entry["note"] = "Consumable (implant/stent/mesh) at actual cost for NABH Super Specialty."
                total_consumables_actual += charged
                total_approved += charged
                matched_count += 1
                consumables_at_actual.append({
                    "item_name": item_name,
                    "amount": round(charged, 2),
                })
                compared.append(entry)
                continue

            if not item_name:
                unmatched_count += 1
                compared.append(entry)
                continue

            pharma_item = compare_line_item_with_nppa(raw)
            if should_use_nppa_result(raw, pharma_item):
                entry = pharma_to_aarogya_item(raw, pharma_item)
                entry["is_consumable"] = is_consumable
                entry["category_hierarchy"] = ""
                entry["is_major_ailment"] = False
                approved = entry.get("approved_amount")
                if approved is not None:
                    total_approved += approved
                    matched_count += 1
                    excess = _to_float(entry.get("excess_amount"))
                    if entry["status"] == "Above Approved Rate":
                        total_excess += excess
                    elif entry["status"] == "Below Approved Rate":
                        total_below += abs(_to_float(entry.get("difference")))
                else:
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
            entry["matched_unit"] = match["unit"]
            entry["category_hierarchy"] = match.get("category_hierarchy", "")
            entry["is_major_ailment"] = match.get("is_major_ailment", False)

            # Track major ailment categories
            if match.get("is_major_ailment"):
                has_major_ailment = True
                cat_hier = match.get("category_hierarchy", "")
                if cat_hier:
                    major_ailment_categories.add(cat_hier)

            # Select rate based on hospital type
            rate_nabh = match.get("rate_nabh")
            rate_non_nabh = match.get("rate_non_nabh")
            if hospital_type in (HOSPITAL_TYPE_NABH, HOSPITAL_TYPE_NABH_SUPER):
                approved_rate = rate_nabh if rate_nabh is not None else match["rate"]
            else:
                approved_rate = rate_non_nabh if rate_non_nabh is not None else match["rate"]

            entry["approved_unit_rate"] = approved_rate

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

        # Determine per-case ceiling based on ailment type
        per_case_ceiling = CEILING_MAJOR if has_major_ailment else CEILING_GENERAL
        total_approved_capped = min(total_approved, per_case_ceiling)
        ceiling_exceeded = total_approved > per_case_ceiling
        ceiling_excess = max(0.0, total_approved - per_case_ceiling)

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
            # EHS payment rule fields
            "hospital_type": hospital_type,
            "payment_basis": payment_basis,
            "has_major_ailment": has_major_ailment,
            "major_ailment_categories": sorted(major_ailment_categories),
            "per_case_ceiling": per_case_ceiling,
            "total_approved_capped": round(total_approved_capped, 2),
            "ceiling_exceeded": ceiling_exceeded,
            "ceiling_excess": round(ceiling_excess, 2),
            "total_consumables_actual": round(total_consumables_actual, 2),
            "consumables_at_actual": consumables_at_actual,
            # Annual limits (advisory only)
            "annual_cap_auto": ANNUAL_CAP_AUTO,
            "annual_cap_dgp": ANNUAL_CAP_DGP,
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
    """Parse raw sources and write JSON caches. Returns the parsed payloads.

    Parses both:
    1. EHS Excel file (primary): Has hospital-type-specific rates and category hierarchy
    2. Annexure CSVs (supplementary): Additional services, investigations, room rents

    EHS rates are used as the primary source for procedure packages with
    rate_non_nabh and rate_nabh fields populated.
    """
    import json

    hospitals = parse_hospitals_pdf()

    # Parse EHS Excel first (primary source with hospital-type rates)
    ehs_payload = parse_ehs_excel()
    ehs_rates = ehs_payload.get("rates", [])
    ehs_unparsed = ehs_payload.get("unparsed", [])

    # Parse annexure CSVs (supplementary rates)
    annexure_payload = parse_rate_annexures()
    annexure_rates = annexure_payload.get("rates", [])
    annexure_unparsed = annexure_payload.get("unparsed", [])

    # Build a lookup of EHS rates by normalized name and code for deduplication
    ehs_by_name: dict[str, dict[str, Any]] = {}
    ehs_by_code: dict[str, dict[str, Any]] = {}
    for rate in ehs_rates:
        norm_name = rate.get("normalized_name", "")
        code = rate.get("code", "")
        if norm_name:
            ehs_by_name[norm_name] = rate
        if code:
            ehs_by_code[code] = rate

    # Merge rates: EHS first, then annexure rates not already in EHS
    merged_rates: list[dict[str, Any]] = list(ehs_rates)
    for rate in annexure_rates:
        norm_name = rate.get("normalized_name", "")
        code = rate.get("code", "")
        # Skip if already covered by EHS
        if norm_name and norm_name in ehs_by_name:
            continue
        if code and code in ehs_by_code:
            continue
        # Add annexure rate (will use legacy single rate field)
        merged_rates.append(rate)

    rate_payload = {
        "rates": merged_rates,
        "unparsed": ehs_unparsed + annexure_unparsed,
    }

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    hosp_path, rate_path = _cache_paths()
    hosp_path.write_text(
        json.dumps({"hospitals": hospitals}, ensure_ascii=False),
        encoding="utf-8",
    )
    rate_path.write_text(
        json.dumps(rate_payload, ensure_ascii=False), encoding="utf-8"
    )

    print(f"  EHS rates: {len(ehs_rates)}")
    print(f"  Annexure rates: {len(annexure_rates)}")
    print(f"  Merged total: {len(merged_rates)}")

    return {"hospitals": hospitals, "rates": rate_payload}


def _load_payloads() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    import json

    hosp_path, rate_path = _cache_paths()
    sources: dict[str, str] = {}
    if hosp_path.exists() and rate_path.exists():
        try:
            hospitals = json.loads(hosp_path.read_text(encoding="utf-8")).get(
                "hospitals", []
            )
            rate_payload = json.loads(rate_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            hospitals = []
            rate_payload = {}
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
