#!/usr/bin/env python3
"""Parse the Aarogya Bhadratha hospital PDF + rate annexures into JSON caches.

Run once (or whenever the source files change) so the backend can serve the
data without parsing the PDF/CSV on every request:

    python backend/scripts/build_aarogya_bhadratha_cache.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.aarogya_bhadratha import build_and_cache  # noqa: E402


def main() -> None:
    print("Building Aarogya Bhadratha cache...", file=sys.stderr)
    built = build_and_cache()
    hospitals = built["hospitals"]
    rate_payload = built["rates"]
    rates = rate_payload.get("rates", [])
    districts = sorted({h["district"] for h in hospitals if h.get("district")})
    numeric_rates = sum(1 for r in rates if r.get("rate") is not None)
    ehs_rates = sum(1 for r in rates if r.get("source") == "EHS_2017")
    major_ailment_rates = sum(1 for r in rates if r.get("is_major_ailment"))
    rates_with_nabh = sum(1 for r in rates if r.get("rate_nabh") is not None)

    print(
        f"Cached {len(hospitals)} hospitals across {len(districts)} districts.",
        file=sys.stderr,
    )
    print(
        f"Cached {len(rates)} rate rows "
        f"({numeric_rates} with numeric rates).",
        file=sys.stderr,
    )
    print(
        f"  - EHS 2017 rates: {ehs_rates} (with hospital-type pricing)",
        file=sys.stderr,
    )
    print(
        f"  - Rates with NABH pricing: {rates_with_nabh}",
        file=sys.stderr,
    )
    print(
        f"  - Major ailment procedures: {major_ailment_rates}",
        file=sys.stderr,
    )
    for note in rate_payload.get("unparsed", []):
        print(f"  note: {note}", file=sys.stderr)


if __name__ == "__main__":
    main()
