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
    built = build_and_cache()
    hospitals = built["hospitals"]
    rate_payload = built["rates"]
    districts = sorted({h["district"] for h in hospitals if h.get("district")})
    numeric_rates = sum(1 for r in rate_payload["rates"] if r.get("rate") is not None)
    print(
        f"Cached {len(hospitals)} hospitals across {len(districts)} districts.",
        file=sys.stderr,
    )
    print(
        f"Cached {len(rate_payload['rates'])} rate rows "
        f"({numeric_rates} with numeric rates).",
        file=sys.stderr,
    )
    for note in rate_payload.get("unparsed", []):
        print(f"  note: {note}", file=sys.stderr)


if __name__ == "__main__":
    main()
