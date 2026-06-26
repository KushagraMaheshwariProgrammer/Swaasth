#!/usr/bin/env python3
"""Build the primary guidelines vector index (ICMR + Clinical Establishments Act STG).

Reuses the pre-parsed ICMR manifest when available to avoid re-OCR.
Clinical Establishments PDFs are parsed with OCR fallback for image-heavy pages.

    cd backend && python scripts/build_primary_guidelines_index.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.guideline_corpus_parser import (  # noqa: E402
    GuidelineChunk,
    build_primary_guideline_corpus,
    write_primary_guideline_artifacts,
)
from app.services.primary_guidelines_index import get_primary_guidelines_store  # noqa: E402
from app.services.stg_parser import StgChunk  # noqa: E402


def _to_stg_chunks(chunks: list[GuidelineChunk]) -> tuple[list[StgChunk], list[dict]]:
    stg_chunks: list[StgChunk] = []
    metadata: list[dict] = []
    for chunk in chunks:
        stg_chunks.append(chunk.to_stg_chunk())
        metadata.append(
            {
                "corpus": chunk.corpus,
                "source_file": chunk.source_file,
                "document": chunk.document,
            }
        )
    return stg_chunks, metadata


def main() -> None:
    output_dir = BACKEND_ROOT / "data" / "primary_guidelines_index"
    manifest = output_dir / "chunks_manifest.json"
    chroma_only = "--chroma-only" in sys.argv

    if chroma_only:
        if not manifest.exists():
            raise SystemExit(
                "chunks_manifest.json not found. Run without --chroma-only first."
            )
        store = get_primary_guidelines_store(output_dir)
        print("Embedding existing manifest into Chroma...", file=sys.stderr, flush=True)
        count = store.build_index_from_manifest(batch_size=128, progress=True)
        print(
            f"Primary guidelines index ready: {count} chunks at {output_dir / 'chroma'}",
            file=sys.stderr,
            flush=True,
        )
        return

    print("Building primary guideline corpus...", file=sys.stderr, flush=True)
    documents, chunks = build_primary_guideline_corpus(
        use_ocr_fallback=True,
        reuse_icmr_manifest=True,
    )
    print(
        f"Prepared {len(documents)} documents and {len(chunks)} chunks.",
        file=sys.stderr,
        flush=True,
    )
    if not chunks:
        raise SystemExit("No guideline chunks were produced.")

    write_primary_guideline_artifacts(documents, chunks, output_dir)
    print(f"Wrote artifacts to {output_dir}", file=sys.stderr, flush=True)

    stg_chunks, metadata = _to_stg_chunks(chunks)
    store = get_primary_guidelines_store(output_dir)
    print("Building Chroma index with fastembed...", file=sys.stderr, flush=True)
    store.build_index(stg_chunks, extra_metadata=metadata, batch_size=128, progress=True)
    print(f"Primary guidelines index ready at {output_dir / 'chroma'}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
