"""State and city directory for bill location selection."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _default_directory_path() -> Path:
    root = _project_root()
    candidates = [
        Path(__file__).resolve().parent.parent / "data" / "india_states_cities_new.csv",
        root / "india_states_cities_new.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Locations CSV not found. Expected one of: "
        + ", ".join(str(p) for p in candidates)
    )


def normalize_location_key(text: str) -> str:
    normalized = text.lower().strip()
    normalized = re.sub(r"\s*\([^)]*\)", " ", normalized)
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


@dataclass(frozen=True)
class CityInfo:
    name: str


class LocationStore:
    def __init__(self, directory_path: Path | None = None) -> None:
        self.directory_path = directory_path or _default_directory_path()
        self.state_ut_names: list[str] = []
        self.cities_by_state_ut: dict[str, list[CityInfo]] = {}
        self._state_code_by_ut_name: dict[str, str] = {}
        self._load_directory()

    def _load_directory(self) -> None:
        raw_cities: dict[str, list[str]] = {}

        with self.directory_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                state_code = (row.get("state_code") or "").strip()
                state_ut_name = (row.get("state_ut_name") or "").strip()
                city_name = (row.get("city_name") or "").strip()

                if not state_ut_name or not city_name:
                    continue

                if state_code:
                    self._state_code_by_ut_name[state_ut_name] = state_code
                raw_cities.setdefault(state_ut_name, []).append(city_name)

        self.state_ut_names = sorted(raw_cities)

        for state_ut_name in self.state_ut_names:
            unique_names = sorted(set(raw_cities.get(state_ut_name, [])))
            self.cities_by_state_ut[state_ut_name] = [
                CityInfo(name=name) for name in unique_names
            ]

    def get_state_ut_names(self) -> list[str]:
        return list(self.state_ut_names)

    def get_states(self) -> list[dict[str, str]]:
        return [
            {
                "code": self._state_code_by_ut_name.get(name, ""),
                "name": name,
            }
            for name in self.state_ut_names
        ]

    def get_state_ut_name_by_code(self, state_code: str) -> str | None:
        state_code = state_code.strip()
        if not state_code:
            return None
        for name, code in self._state_code_by_ut_name.items():
            if code == state_code:
                return name
        return None

    def get_city_names(self, state_ut_name: str) -> list[str]:
        return [city.name for city in self.cities_by_state_ut.get(state_ut_name.strip(), [])]

    def get_cities(self, state_ut_name: str) -> list[dict[str, str]]:
        cities = self.cities_by_state_ut.get(state_ut_name.strip(), [])
        return [{"name": city.name} for city in cities]

    def resolve_city(self, state_ut_name: str, city_name: str) -> dict[str, str]:
        state_ut_name = state_ut_name.strip()
        if state_ut_name not in self.cities_by_state_ut:
            raise ValueError(f"Invalid state_ut_name '{state_ut_name}'.")

        city_name = city_name.strip()
        if not city_name:
            raise ValueError("city_name is required.")

        state_code = self._state_code_by_ut_name.get(state_ut_name, "")

        for city in self.cities_by_state_ut.get(state_ut_name, []):
            if city.name == city_name:
                return {
                    "state_code": state_code,
                    "state_ut_name": state_ut_name,
                    "state_name": state_ut_name,
                    "city_name": city.name,
                }

        return {
            "state_code": state_code,
            "state_ut_name": state_ut_name,
            "state_name": state_ut_name,
            "city_name": city_name,
        }


_store: LocationStore | None = None


def get_location_store() -> LocationStore:
    global _store
    if _store is None:
        _store = LocationStore()
    return _store
