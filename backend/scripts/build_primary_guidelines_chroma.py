#!/usr/bin/env python3
"""Build only the Chroma vector index from an existing primary guidelines manifest.

Use this after build_primary_guidelines_index.py has written chunks_manifest.json,
or when re-embedding is needed without re-parsing PDFs.

    cd backend && python scripts/build_primary_guidelines_chroma.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.primary_guidelines_index import get_primary_guidelines_store  # noqa: E402


def main() -> None:
    output_dir = BACKEND_ROOT / "data" / "primary_guidelines_index"
    manifest = output_dir / "chunks_manifest.json"
    if not manifest.exists():
        raise SystemExit(
            "chunks_manifest.json not found. Run build_primary_guidelines_index.py first."
        )

    store = get_primary_guidelines_store(output_dir)
    print(f"Embedding manifest at {manifest} ...", file=sys.stderr, flush=True)
    count = store.build_index_from_manifest(batch_size=128, progress=True)
    print(
        f"Primary guidelines Chroma index ready: {count} chunks at {output_dir / 'chroma'}",
        file=sys.stderr,
        flush=True,
    )


if __name__ == "__main__":
    main()
