#!/usr/bin/env python3
"""Export states/cities/tiers JSON for the mobile and web frontend bundle."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_BUNDLE = (
    BACKEND_ROOT.parent / "frontend" / "src" / "data" / "locations.bundle.json"
)

sys.path.insert(0, str(BACKEND_ROOT))

from app.locations import get_location_store  # noqa: E402


def main() -> None:
    store = get_location_store()
    cities_by_state: dict[str, list[str]] = {}
    tier_by_state_city: dict[str, dict[str, dict[str, str]]] = {}

    for state_ut_name in store.state_ut_names:
        city_names = store.get_city_names(state_ut_name)
        cities_by_state[state_ut_name] = city_names
        tier_by_state_city[state_ut_name] = {}
        for city in store.cities_by_state_ut.get(state_ut_name, []):
            tier_by_state_city[state_ut_name][city.name] = {
                "tier_id": city.tier_id,
                "tier_label": city.tier_label,
                "tier_source": city.tier_source,
            }

    bundle = {
        "states": store.get_state_ut_names(),
        "citiesByState": cities_by_state,
        "tierByStateCity": tier_by_state_city,
    }

    FRONTEND_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_BUNDLE.write_text(
        json.dumps(bundle, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    city_count = sum(len(names) for names in cities_by_state.values())
    print(
        f"Wrote {len(bundle['states'])} states and {city_count} cities to {FRONTEND_BUNDLE}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
