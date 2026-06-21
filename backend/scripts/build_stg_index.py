#!/usr/bin/env python3
"""Build the STG vector index from STG.pdf.

Run once (or whenever STG.pdf changes):

    cd backend && python scripts/build_stg_index.py

Requires STG.pdf at:
    backend/data/Standard Treatment Guidelines/STG.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.stg_index import get_stg_index_store  # noqa: E402
from app.services.stg_parser import (  # noqa: E402
    build_chunks_from_pdf,
    write_parsed_artifacts,
)


def main() -> None:
    output_dir = BACKEND_ROOT / "data" / "stg_index"
    print("Parsing STG.pdf...", file=sys.stderr)
    toc, chunks = build_chunks_from_pdf()
    print(f"Parsed {len(toc)} TOC entries and {len(chunks)} chunks.", file=sys.stderr)

    write_parsed_artifacts(toc, chunks, output_dir)
    print(f"Wrote toc.json and chunks_manifest.json to {output_dir}", file=sys.stderr)

    store = get_stg_index_store(output_dir)
    print("Building Chroma index with fastembed...", file=sys.stderr)
    store.build_index(chunks)
    print(f"STG index ready at {output_dir / 'chroma'}", file=sys.stderr)


if __name__ == "__main__":
    main()
