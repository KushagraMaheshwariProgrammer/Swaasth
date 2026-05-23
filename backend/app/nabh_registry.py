"""NABH accredited hospital registry lookup."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ACCREDITED_STATUSES = frozenset({"accredited", "certified", "empaneled"})

STRIP_TOKENS = (
    "private",
    "limited",
    "ltd",
    "pvt",
    "hospital",
    "hospitals",
    "medical",
    "centre",
    "center",
    "clinic",
    "institute",
    "and",
    "the",
    "of",
    "a",
    "unit",
)


@dataclass(frozen=True)
class NabhHospitalRecord:
    name: str
    normalized_name: str
    tokens: frozenset[str]
    accreditation_status: str
    accreditation_number: str
    address: str


def normalize_hospital_name(name: str) -> str:
    normalized = name.lower().strip()
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    tokens = [token for token in normalized.split() if token not in STRIP_TOKENS]
    return " ".join(tokens).strip()


def _default_csv_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent
    project_root = backend_root.parent
    candidates = [
        backend_root / "data" / "nabh_accredited_hospitals_22may2026.csv",
        project_root / "NABH" / "nabh_accredited_hospitals_22may2026.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "NABH hospitals CSV not found. Expected one of: "
        + ", ".join(str(p) for p in candidates)
    )


class NabhRegistry:
    def __init__(self, csv_path: Path | None = None) -> None:
        path = csv_path or _default_csv_path()
        self.csv_path = path
        self.records: list[NabhHospitalRecord] = []
        self._exact_index: dict[str, NabhHospitalRecord] = {}
        self._token_index: dict[str, list[NabhHospitalRecord]] = {}
        self._load(path)

    def _load(self, path: Path) -> None:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                name = (row.get("HCO Name") or "").strip()
                if not name:
                    continue

                status = (row.get("Accreditations / Certifications") or "").strip()
                normalized = normalize_hospital_name(name)
                if not normalized:
                    continue

                record = NabhHospitalRecord(
                    name=name,
                    normalized_name=normalized,
                    tokens=frozenset(normalized.split()),
                    accreditation_status=status,
                    accreditation_number=(
                        row.get("Accreditation Number (Acc. No.)") or ""
                    ).strip(),
                    address=(row.get("Address") or "").strip(),
                )
                self.records.append(record)
                self._exact_index.setdefault(normalized, record)
                for token in record.tokens:
                    if len(token) >= 3:
                        self._token_index.setdefault(token, []).append(record)

        if not self.records:
            raise ValueError(f"No NABH hospital rows loaded from {path}")

    def lookup(self, hospital_name: str) -> dict[str, Any]:
        hospital_name = hospital_name.strip()
        if not hospital_name:
            return {
                "hospital_name": "",
                "is_accredited": False,
                "accreditation_status": None,
                "matched_registry_name": None,
                "accreditation_number": None,
                "approximate_match": False,
                "match_score": 0.0,
            }

        normalized = normalize_hospital_name(hospital_name)
        if not normalized:
            return self._not_found(hospital_name)

        exact = self._exact_index.get(normalized)
        if exact is not None:
            return self._found(hospital_name, exact, score=1.0, approximate=False)

        input_tokens = {t for t in normalized.split() if len(t) >= 3}
        if len(input_tokens) < 2:
            return self._not_found(hospital_name)

        candidates: dict[int, NabhHospitalRecord] = {}
        for token in input_tokens:
            for record in self._token_index.get(token, []):
                candidates[id(record)] = record

        if len(normalized) >= 4:
            for record in candidates.values():
                registry_name = record.normalized_name
                if len(registry_name) < 4:
                    continue
                if registry_name in normalized or normalized in registry_name:
                    return self._found(
                        hospital_name, record, score=0.95, approximate=False
                    )

        best: tuple[float, NabhHospitalRecord] | None = None
        for record in candidates.values():
            if not record.tokens or not input_tokens:
                continue

            overlap_score = len(input_tokens & record.tokens) / len(
                input_tokens | record.tokens
            )
            sequence_score = SequenceMatcher(
                None, normalized, record.normalized_name
            ).ratio()
            score = (0.65 * overlap_score) + (0.35 * sequence_score)
            if best is None or score > best[0]:
                best = (score, record)

        if best:
            score, record = best
            input_tokens = set(normalized.split())
            overlap_score = len(input_tokens & record.tokens) / max(
                len(input_tokens | record.tokens), 1
            )
            if score >= 0.78 and overlap_score >= 0.4:
                return self._found(
                    hospital_name,
                    record,
                    score=score,
                    approximate=score < 0.92,
                )

        return self._not_found(hospital_name)

    def _is_accredited(self, record: NabhHospitalRecord) -> bool:
        return record.accreditation_status.strip().lower() in ACCREDITED_STATUSES

    def _found(
        self,
        query_name: str,
        record: NabhHospitalRecord,
        *,
        score: float,
        approximate: bool,
    ) -> dict[str, Any]:
        return {
            "hospital_name": query_name,
            "is_accredited": self._is_accredited(record),
            "accreditation_status": record.accreditation_status,
            "matched_registry_name": record.name,
            "accreditation_number": record.accreditation_number,
            "approximate_match": approximate,
            "match_score": round(score, 3),
        }

    def _not_found(self, hospital_name: str) -> dict[str, Any]:
        return {
            "hospital_name": hospital_name,
            "is_accredited": False,
            "accreditation_status": None,
            "matched_registry_name": None,
            "accreditation_number": None,
            "approximate_match": False,
            "match_score": 0.0,
        }


_registry: NabhRegistry | None = None


def get_nabh_registry() -> NabhRegistry:
    global _registry
    if _registry is None:
        _registry = NabhRegistry()
    return _registry
