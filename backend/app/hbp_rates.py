"""Load Ayushman Bharat PM-JAY HBP 2022 rates and match bill line items."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.cghs_rates import normalize_item_name

HBP_TIER_COLUMNS: dict[str, str] = {
    "tier_1": "Tier1 (X)",
    "tier_i": "Tier1 (X)",
    "1": "Tier1 (X)",
    "tier_2": "Tier2 (Y)",
    "tier_ii": "Tier2 (Y)",
    "2": "Tier2 (Y)",
    "tier_3": "Tier3 (Z)",
    "tier_iii": "Tier3 (Z)",
    "3": "Tier3 (Z)",
}


def resolve_hbp_tier_id(tier_id: str | None) -> str:
    if not tier_id:
        return "tier_3"
    key = tier_id.strip().lower().replace(" ", "_")
    if key in HBP_TIER_COLUMNS:
        if key in ("tier_i", "1"):
            return "tier_1"
        if key in ("tier_ii", "2"):
            return "tier_2"
        if key in ("tier_iii", "3"):
            return "tier_3"
        return key
    if "tier 1" in key or "tier i" in key:
        return "tier_1"
    if "tier 2" in key or "tier ii" in key:
        return "tier_2"
    if "tier 3" in key or "tier iii" in key:
        return "tier_3"
    return "tier_3"


def _to_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _default_csv_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent
    project_root = backend_root.parent
    candidates = [
        backend_root / "data" / "HBP_2022.csv",
        project_root / "HBP_2022.csv",
        project_root / "HBP-2022.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "HBP 2022 rates CSV not found. Expected one of: "
        + ", ".join(str(p) for p in candidates)
    )


@dataclass(frozen=True)
class HbpRateRow:
    specialty: str
    package_code: str
    package_name: str
    procedure_code: str
    procedure_name: str
    tier_1_rate: float
    tier_2_rate: float
    tier_3_rate: float
    normalized_package: str
    normalized_procedure: str
    procedure_tokens: frozenset[str]
    package_tokens: frozenset[str]


class HbpRatesStore:
    def __init__(self, csv_path: Path | None = None) -> None:
        path = csv_path or _default_csv_path()
        self.csv_path = path
        self.rows: list[HbpRateRow] = []
        self._by_procedure_code: dict[str, list[HbpRateRow]] = {}
        self._by_token: dict[str, list[HbpRateRow]] = {}
        self._load(path)

    def _load(self, path: Path) -> None:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                package_name = (raw.get("AB PMJAY Package Name") or "").strip()
                procedure_name = (raw.get("Procedure Name 2022") or "").strip()
                procedure_code = (
                    raw.get("Procedure code HBP 2022") or ""
                ).strip().upper()
                if not package_name and not procedure_name:
                    continue

                norm_package = normalize_item_name(package_name)
                norm_procedure = normalize_item_name(procedure_name)
                row = HbpRateRow(
                    specialty=(raw.get("Specialty") or "").strip(),
                    package_code=(raw.get("Package Code HBP 2022") or "").strip(),
                    package_name=package_name,
                    procedure_code=procedure_code,
                    procedure_name=procedure_name,
                    tier_1_rate=_to_float(raw.get("Tier1 (X)")),
                    tier_2_rate=_to_float(raw.get("Tier2 (Y)")),
                    tier_3_rate=_to_float(raw.get("Tier3 (Z)")),
                    normalized_package=norm_package,
                    normalized_procedure=norm_procedure,
                    procedure_tokens=frozenset(norm_procedure.split()),
                    package_tokens=frozenset(norm_package.split()),
                )
                self.rows.append(row)
                if procedure_code:
                    self._by_procedure_code.setdefault(procedure_code, []).append(row)
                for token in row.procedure_tokens | row.package_tokens:
                    if len(token) >= 3:
                        self._by_token.setdefault(token, []).append(row)

        if not self.rows:
            raise ValueError(f"No HBP rate rows loaded from {path}")

    def rate_for_row(self, row: HbpRateRow, tier_id: str) -> float:
        canonical = resolve_hbp_tier_id(tier_id)
        if canonical == "tier_1":
            return row.tier_1_rate
        if canonical == "tier_2":
            return row.tier_2_rate
        return row.tier_3_rate

    def _candidate_rows(self, normalized_name: str) -> list[HbpRateRow]:
        tokens = [token for token in normalized_name.split() if len(token) >= 3]
        if not tokens:
            return self.rows[:400]

        seen: set[int] = set()
        candidates: list[HbpRateRow] = []
        for token in tokens:
            for row in self._by_token.get(token, ()):
                if id(row) in seen:
                    continue
                seen.add(id(row))
                candidates.append(row)
                if len(candidates) >= 800:
                    return candidates
        return candidates if candidates else self.rows[:400]

    def find_match(
        self,
        item_name: str,
        *,
        tier_id: str = "tier_3",
    ) -> dict[str, Any] | None:
        normalized_name = normalize_item_name(item_name)
        if not normalized_name:
            return None

        code_match = re.search(
            r"\b([A-Z]{2}\d{3,4}[A-Z]?)\b", item_name.upper()
        )
        if code_match:
            code = code_match.group(1)
            for row in self._by_procedure_code.get(code, ()):
                return self._match_payload(row, tier_id, approximate=False)

        candidate_rows = self._candidate_rows(normalized_name)
        for row in candidate_rows:
            for ref in (row.normalized_procedure, row.normalized_package):
                if ref and (ref in normalized_name or normalized_name in ref):
                    return self._match_payload(row, tier_id, approximate=False)

        input_tokens = set(normalized_name.split())
        best: tuple[float, HbpRateRow] | None = None
        for row in candidate_rows:
            ref_tokens = row.procedure_tokens | row.package_tokens
            if not ref_tokens or not input_tokens:
                continue
            overlap_score = len(input_tokens & ref_tokens) / len(
                input_tokens | ref_tokens
            )
            sequence_score = max(
                SequenceMatcher(None, normalized_name, row.normalized_procedure).ratio(),
                SequenceMatcher(None, normalized_name, row.normalized_package).ratio(),
            )
            score = (0.6 * overlap_score) + (0.4 * sequence_score)
            if best is None or score > best[0]:
                best = (score, row)

        if best and best[0] >= 0.48:
            return self._match_payload(best[1], tier_id, approximate=True)

        return None

    def _match_payload(
        self,
        row: HbpRateRow,
        tier_id: str,
        *,
        approximate: bool,
    ) -> dict[str, Any]:
        applied_rate = self.rate_for_row(row, tier_id)
        return {
            "reference_item": row.procedure_name or row.package_name,
            "package_name": row.package_name,
            "rate": applied_rate,
            "hbp_procedure_code": row.procedure_code,
            "hbp_package_code": row.package_code,
            "specialty": row.specialty,
            "tier_1_rate": row.tier_1_rate,
            "tier_2_rate": row.tier_2_rate,
            "tier_3_rate": row.tier_3_rate,
            "approximate_match": approximate,
        }


_store: HbpRatesStore | None = None


def get_hbp_store() -> HbpRatesStore:
    global _store
    if _store is None:
        _store = HbpRatesStore()
    return _store
