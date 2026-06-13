"""State/city directory and CGHS city tier classification."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

TIER_LABEL_TO_ID: dict[str, str] = {
    "Tier I (X City)": "tier_1",
    "Tier II (Y City)": "tier_2",
    "Tier III (Z City)": "tier_3",
}

DEFAULT_TIER_ID = "tier_3"
DEFAULT_TIER_LABEL = "Tier III (Z City)"


@dataclass(frozen=True)
class CityInfo:
    name: str
    tier_id: str
    tier_label: str
    tier_source: str


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _default_directory_path() -> Path:
    root = _project_root()
    candidates = [
        Path(__file__).resolve().parent.parent / "data" / "india_states_cities_new.csv",
        root / "india_states_cities_new.csv",
        Path(__file__).resolve().parent.parent
        / "data"
        / "india_official_gov_urban_cities_swaasth_sorted.csv",
        root / "india_official_gov_urban_cities_swaasth_sorted.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Locations CSV not found. Expected one of: "
        + ", ".join(str(p) for p in candidates)
    )


def _default_tier_path() -> Path:
    root = _project_root()
    candidates = [
        Path(__file__).resolve().parent.parent
        / "data"
        / "cghs_cities_tier_classification.csv",
        root / "cghs_cities_tier_classification.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "cghs_cities_tier_classification.csv not found. Expected one of: "
        + ", ".join(str(p) for p in candidates)
    )


def normalize_location_key(text: str) -> str:
    normalized = text.lower().strip()
    normalized = re.sub(r"\s*\([^)]*\)", " ", normalized)
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def tier_label_for_id(tier_id: str) -> str:
    for label, tid in TIER_LABEL_TO_ID.items():
        if tid == tier_id:
            return label
    return DEFAULT_TIER_LABEL


class LocationStore:
    def __init__(
        self,
        directory_path: Path | None = None,
        tier_path: Path | None = None,
    ) -> None:
        self.directory_path = directory_path or _default_directory_path()
        self.tier_path = tier_path or _default_tier_path()
        self.state_ut_names: list[str] = []
        self.cities_by_state_ut: dict[str, list[CityInfo]] = {}
        self._state_code_by_ut_name: dict[str, str] = {}
        self._tier_by_city: dict[str, str] = {}
        self._tier_by_state_city: dict[tuple[str, str], str] = {}
        self._cghs_city_entries: list[tuple[str, str, str]] = []
        self._load_tier_classification()
        self._load_directory()

    def _load_tier_classification(self) -> None:
        with self.tier_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                city = (row.get("City") or "").strip()
                state_ut = (row.get("State_UT") or "").strip()
                tier_label = (row.get("Tier") or "").strip()
                if not city:
                    continue

                tier_id = TIER_LABEL_TO_ID.get(tier_label, DEFAULT_TIER_ID)
                norm_city = normalize_location_key(city)
                norm_state = normalize_location_key(state_ut)

                self._tier_by_city[norm_city] = tier_id
                self._tier_by_state_city[(norm_state, norm_city)] = tier_id
                self._cghs_city_entries.append((norm_city, norm_state, tier_id))

    def _lookup_tier(self, state_name: str, city_name: str) -> tuple[str, str, str]:
        norm_city = normalize_location_key(city_name)
        norm_state = normalize_location_key(state_name)

        if (norm_state, norm_city) in self._tier_by_state_city:
            tier_id = self._tier_by_state_city[(norm_state, norm_city)]
            return tier_id, tier_label_for_id(tier_id), "cghs_classification"

        if norm_city in self._tier_by_city:
            tier_id = self._tier_by_city[norm_city]
            return tier_id, tier_label_for_id(tier_id), "cghs_classification"

        for cghs_city, cghs_state, tier_id in self._cghs_city_entries:
            if norm_city == cghs_city or norm_city in cghs_city or cghs_city in norm_city:
                if norm_state and cghs_state:
                    if norm_state in cghs_state or cghs_state in norm_state:
                        return tier_id, tier_label_for_id(tier_id), "cghs_classification"
                else:
                    return tier_id, tier_label_for_id(tier_id), "cghs_classification"

        return DEFAULT_TIER_ID, DEFAULT_TIER_LABEL, "default_tier_3"

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
            cities: list[CityInfo] = []
            for name in unique_names:
                tier_id, tier_label, tier_source = self._lookup_tier(state_ut_name, name)
                cities.append(
                    CityInfo(
                        name=name,
                        tier_id=tier_id,
                        tier_label=tier_label,
                        tier_source=tier_source,
                    )
                )
            self.cities_by_state_ut[state_ut_name] = cities

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
        return [
            {
                "name": city.name,
                "tier_id": city.tier_id,
                "tier_label": city.tier_label,
                "tier_source": city.tier_source,
            }
            for city in cities
        ]

    def resolve_tier(self, state_ut_name: str, city_name: str) -> dict[str, str]:
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
                    "tier_id": city.tier_id,
                    "tier_label": city.tier_label,
                    "tier_source": city.tier_source,
                }

        tier_id, tier_label, tier_source = self._lookup_tier(state_ut_name, city_name)
        return {
            "state_code": state_code,
            "state_ut_name": state_ut_name,
            "state_name": state_ut_name,
            "city_name": city_name,
            "tier_id": tier_id,
            "tier_label": tier_label,
            "tier_source": tier_source,
        }


_store: LocationStore | None = None


def get_location_store() -> LocationStore:
    global _store
    if _store is None:
        _store = LocationStore()
    return _store
