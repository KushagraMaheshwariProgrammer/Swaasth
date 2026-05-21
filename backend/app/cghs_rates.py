"""Load CGHS 2025 rates from CSV and match bill line items."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

TERM_ALIASES: dict[str, str] = {
    "complete blood count": "cbc",
    "complete haemogram": "cbc",
    "complete hemogram": "cbc",
    "liver function test": "lft",
    "kidney function test": "kft",
    "renal function test": "kft",
    "erythrocyte sedimentation rate": "esr",
    "electrocardiogram": "ecg",
    "electroencephalogram": "eeg",
    "ultrasonography": "ultrasound",
    "usg": "ultrasound",
    "magnetic resonance imaging": "mri",
    "computed tomography": "ct scan",
    "operation theatre": "ot",
    "operation theater": "ot",
    "international normalized ratio": "inr",
    "activated partial thromboplastin time": "aptt",
    "prothrombin time": "pt",
    "glycated hemoglobin": "hba1c",
    "thyroid function test": "thyroid profile",
    "urine routine examination": "urine routine",
    "urine routine microscopy": "urine routine",
    "culture and sensitivity": "culture sensitivity",
    "xray": "x ray",
}

TIER_KEYS: dict[str, str] = {
    "tier_1": "Tier I (X City)",
    "tier_i": "Tier I (X City)",
    "1": "Tier I (X City)",
    "tier_2": "Tier II (Y City)",
    "tier_ii": "Tier II (Y City)",
    "2": "Tier II (Y City)",
    "tier_3": "Tier III (Z City)",
    "tier_iii": "Tier III (Z City)",
    "3": "Tier III (Z City)",
}

RATE_TYPE_KEYS: dict[str, str] = {
    "non_nabh": "non_nabh",
    "non-nabh": "non_nabh",
    "nabh": "nabh",
    "super_speciality": "super_speciality",
    "super-speciality": "super_speciality",
    "super_specialty": "super_speciality",
}


@dataclass(frozen=True)
class CghsRateRow:
    tier: str
    sr_no: int
    cghs_code: str
    procedure: str
    non_nabh_rate: float
    nabh_rate: float
    super_speciality_rate: float
    speciality_classification: str
    normalized_procedure: str
    procedure_tokens: frozenset[str]


def normalize_item_name(item_name: str) -> str:
    normalized = item_name.lower().strip()
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = normalized.replace("&", " and ").replace("/", " ")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)

    for source, target in TERM_ALIASES.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)

    return re.sub(r"\s+", " ", normalized).strip()


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


def resolve_tier(tier: str | None) -> str:
    if not tier:
        return TIER_KEYS["tier_1"]
    key = tier.strip().lower().replace(" ", "_")
    if key in TIER_KEYS:
        return TIER_KEYS[key]
    for canonical in TIER_KEYS.values():
        if tier.strip().lower() == canonical.lower():
            return canonical
    raise ValueError(
        f"Invalid tier '{tier}'. Use tier_1, tier_2, or tier_3 "
        "(Tier I/II/III cities)."
    )


def resolve_rate_type(rate_type: str | None) -> str:
    if not rate_type:
        return "nabh"
    key = rate_type.strip().lower().replace(" ", "_")
    if key in RATE_TYPE_KEYS:
        return RATE_TYPE_KEYS[key]
    raise ValueError(
        f"Invalid rate_type '{rate_type}'. "
        "Use non_nabh, nabh, or super_speciality."
    )


def _default_csv_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent
    project_root = backend_root.parent
    candidates = [
        backend_root / "data" / "cghs_rates_2025.csv",
        project_root / "cghs_rates_2025 (1).csv",
        project_root / "cghs_rates_2025.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "CGHS rates CSV not found. Expected one of: "
        + ", ".join(str(p) for p in candidates)
    )


class CghsRatesStore:
    def __init__(self, csv_path: Path | None = None) -> None:
        path = csv_path or _default_csv_path()
        self.csv_path = path
        self.rows: list[CghsRateRow] = []
        self._by_tier: dict[str, list[CghsRateRow]] = {}
        self._load(path)

    def _load(self, path: Path) -> None:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                tier = (raw.get("Tier") or "").strip()
                procedure = (raw.get("Procedure_Investigation") or "").strip()
                if not tier or not procedure:
                    continue

                normalized = normalize_item_name(procedure)
                row = CghsRateRow(
                    tier=tier,
                    sr_no=_to_int(raw.get("Sr_No")),
                    cghs_code=(raw.get("CGHS_Code") or "").strip().upper(),
                    procedure=procedure,
                    non_nabh_rate=_to_float(raw.get("Non_NABH_Rate")),
                    nabh_rate=_to_float(raw.get("NABH_Rate")),
                    super_speciality_rate=_to_float(raw.get("Super_Speciality_Rate")),
                    speciality_classification=(
                        raw.get("Speciality_Classification") or ""
                    ).strip(),
                    normalized_procedure=normalized,
                    procedure_tokens=frozenset(normalized.split()),
                )
                self.rows.append(row)
                self._by_tier.setdefault(tier, []).append(row)

        if not self.rows:
            raise ValueError(f"No CGHS rate rows loaded from {path}")

    @property
    def tiers(self) -> list[str]:
        return sorted(self._by_tier.keys())

    def rate_for_row(self, row: CghsRateRow, rate_type: str) -> float:
        if rate_type == "non_nabh":
            return row.non_nabh_rate
        if rate_type == "super_speciality":
            return row.super_speciality_rate
        return row.nabh_rate

    def find_match(
        self,
        item_name: str,
        *,
        tier: str,
        rate_type: str = "nabh",
    ) -> dict[str, Any] | None:
        canonical_tier = resolve_tier(tier)
        canonical_rate_type = resolve_rate_type(rate_type)
        tier_rows = self._by_tier.get(canonical_tier, [])
        if not tier_rows:
            return None

        normalized_name = normalize_item_name(item_name)
        if not normalized_name:
            return None

        code_match = re.search(r"\b([A-Z]{2}\d{3,4})\b", item_name.upper())
        if code_match:
            code = code_match.group(1)
            for row in tier_rows:
                if row.cghs_code == code:
                    return self._match_payload(
                        row, canonical_tier, canonical_rate_type, approximate=False
                    )

        exact_index = {
            row.normalized_procedure: row for row in tier_rows
        }
        if normalized_name in exact_index:
            return self._match_payload(
                exact_index[normalized_name],
                canonical_tier,
                canonical_rate_type,
                approximate=False,
            )

        for row in tier_rows:
            ref = row.normalized_procedure
            if ref in normalized_name or normalized_name in ref:
                return self._match_payload(
                    row, canonical_tier, canonical_rate_type, approximate=False
                )

        input_tokens = set(normalized_name.split())
        best: tuple[float, CghsRateRow] | None = None
        for row in tier_rows:
            ref_tokens = row.procedure_tokens
            if not ref_tokens or not input_tokens:
                continue

            overlap_score = len(input_tokens & ref_tokens) / len(
                input_tokens | ref_tokens
            )
            sequence_score = SequenceMatcher(
                None, normalized_name, row.normalized_procedure
            ).ratio()
            score = (0.6 * overlap_score) + (0.4 * sequence_score)
            if best is None or score > best[0]:
                best = (score, row)

        if best and best[0] >= 0.52:
            return self._match_payload(
                best[1], canonical_tier, canonical_rate_type, approximate=True
            )

        return None

    def _match_payload(
        self,
        row: CghsRateRow,
        tier: str,
        rate_type: str,
        *,
        approximate: bool,
    ) -> dict[str, Any]:
        applied_rate = self.rate_for_row(row, rate_type)
        return {
            "reference_item": row.procedure,
            "rate": applied_rate,
            "cghs_code": row.cghs_code,
            "sr_no": row.sr_no,
            "tier": tier,
            "rate_type": rate_type,
            "non_nabh_rate": row.non_nabh_rate,
            "nabh_rate": row.nabh_rate,
            "super_speciality_rate": row.super_speciality_rate,
            "speciality_classification": row.speciality_classification,
            "approximate_match": approximate,
        }


_store: CghsRatesStore | None = None


def get_cghs_store() -> CghsRatesStore:
    global _store
    if _store is None:
        _store = CghsRatesStore()
    return _store
