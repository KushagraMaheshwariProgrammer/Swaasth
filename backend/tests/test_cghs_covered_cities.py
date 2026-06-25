"""Tests for CGHS covered cities store and API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.cghs_covered_cities import CghsCoveredCitiesStore, get_cghs_covered_cities_store
from app.main import app

client = TestClient(app)


def test_store_loads_23_cities() -> None:
    store = get_cghs_covered_cities_store()
    assert len(store.cities) == 23
    names = {city.city_display_name for city in store.cities}
    assert "Hyderabad" in names
    assert "Delhi and NCR" in names


def test_store_parses_aliases() -> None:
    store = get_cghs_covered_cities_store()
    bengaluru = next(
        city for city in store.cities if city.city_display_name == "Bengaluru"
    )
    assert "Bangalore" in bengaluru.aliases


def test_store_deduplicates_cities(tmp_path) -> None:
    csv_path = tmp_path / "cghs_covered_cities.csv"
    csv_path.write_text(
        "scheme_code,city_display_name,aliases,is_cghs_covered,source_note\n"
        'CGHS,Hyderabad,"Hyderabad",true,"test"\n'
        'CGHS,Hyderabad,"Hyderabad",true,"duplicate"\n'
        'CGHS,Delhi and NCR,"Delhi|NCR",true,"test"\n',
        encoding="utf-8",
    )
    store = CghsCoveredCitiesStore(csv_path=csv_path)
    assert len(store.cities) == 2


def test_store_handles_missing_aliases_column(tmp_path) -> None:
    csv_path = tmp_path / "cghs_covered_cities.csv"
    csv_path.write_text(
        "scheme_code,city_display_name,is_cghs_covered\n"
        "CGHS,Hyderabad,true\n",
        encoding="utf-8",
    )
    store = CghsCoveredCitiesStore(csv_path=csv_path)
    assert len(store.cities) == 1
    assert store.cities[0].aliases == ()


def test_store_skips_empty_rows(tmp_path) -> None:
    csv_path = tmp_path / "cghs_covered_cities.csv"
    csv_path.write_text(
        "scheme_code,city_display_name,aliases,is_cghs_covered,source_note\n"
        'CGHS,,"Hyderabad",true,"empty name"\n'
        'CGHS,Hyderabad,"Hyderabad",true,"ok"\n',
        encoding="utf-8",
    )
    store = CghsCoveredCitiesStore(csv_path=csv_path)
    assert len(store.cities) == 1


def test_covered_cities_endpoint() -> None:
    res = client.get("/api/schemes/cghs/covered-cities")
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["scheme_code"] == "CGHS"
    assert len(payload["cities"]) == 23
    hyderabad = next(
        city for city in payload["cities"] if city["city_display_name"] == "Hyderabad"
    )
    assert hyderabad["is_cghs_covered"] is True
    assert "Hyderabad" in hyderabad["aliases"]
