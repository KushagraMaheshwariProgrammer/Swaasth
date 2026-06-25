"""CGHS covered cities reference data — eligibility residence advisory support."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CghsCoveredCity:
    city_display_name: str
    aliases: tuple[str, ...]
    is_cghs_covered: bool


def _parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return default


def _parse_aliases(raw: str | None) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return ()
    parts = [part.strip() for part in raw.split("|")]
    return tuple(alias for alias in parts if alias)


def _default_csv_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent
    candidates = [
        backend_root / "data" / "schemes" / "cghs" / "cghs_covered_cities.csv",
        backend_root / "data" / "cghs_covered_cities.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "CGHS covered cities CSV not found. Expected one of: "
        + ", ".join(str(p) for p in candidates)
    )


class CghsCoveredCitiesStore:
    def __init__(self, csv_path: Path | None = None) -> None:
        path = csv_path or _default_csv_path()
        self.csv_path = path
        self.cities: list[CghsCoveredCity] = []
        self._load(path)

    def _load(self, path: Path) -> None:
        if not path.exists():
            return

        seen_names: set[str] = set()
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                if not raw:
                    continue
                display_name = (raw.get("city_display_name") or "").strip()
                if not display_name:
                    continue

                normalized_key = display_name.casefold()
                if normalized_key in seen_names:
                    continue
                seen_names.add(normalized_key)

                aliases = _parse_aliases(raw.get("aliases"))
                is_covered = _parse_bool(raw.get("is_cghs_covered"), default=True)
                self.cities.append(
                    CghsCoveredCity(
                        city_display_name=display_name,
                        aliases=aliases,
                        is_cghs_covered=is_covered,
                    )
                )

    def list_public(self) -> list[dict[str, object]]:
        return [
            {
                "city_display_name": city.city_display_name,
                "aliases": list(city.aliases),
                "is_cghs_covered": city.is_cghs_covered,
            }
            for city in self.cities
        ]


_store: CghsCoveredCitiesStore | None = None


def get_cghs_covered_cities_store() -> CghsCoveredCitiesStore:
    global _store
    if _store is None:
        _store = CghsCoveredCitiesStore()
    return _store
