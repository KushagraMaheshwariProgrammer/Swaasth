#!/usr/bin/env python3
"""Fetch privately hosted guideline PDFs and prebuilt Chroma indexes.

The public repository does not redistribute ICMR / CEA / CRC guideline PDFs or
the verbatim text in the derived vector indexes. Production images download a
single archive from a private Azure Blob (South India) using a SAS URL.

Expected archive (zip or tar.gz) layout — files extracted into --dest:

    Standard Treatment Guidelines/
    primary_guidelines_index/
    stg_index/

Usage:
    python scripts/fetch_guideline_corpus.py
    python scripts/fetch_guideline_corpus.py --dest data --require

Environment:
    GUIDELINE_CORPUS_SAS_URL  HTTPS URL (typically an Azure Blob SAS) of the archive.
"""

from __future__ import annotations

import argparse
import os
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = BACKEND_ROOT / "data"
REQUIRED_MARKERS = (
    "primary_guidelines_index",
    "stg_index",
)
ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar", ".zip")


def _dest_looks_complete(dest: Path) -> bool:
    return all((dest / marker).exists() for marker in REQUIRED_MARKERS)


def _download(url: str, target: Path) -> None:
    request = Request(url, headers={"User-Agent": "swaasth-guideline-fetch/1.0"})
    with urlopen(request, timeout=120) as response, target.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def _extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
        return
    if name.endswith(".tar.gz") or name.endswith(".tgz") or name.endswith(".tar"):
        with tarfile.open(archive) as tf:
            tf.extractall(dest)
        return
    raise SystemExit(f"Unsupported archive type: {archive.name}")


def _flatten_if_wrapped(dest: Path) -> None:
    """If the archive wrapped everything in a single top-level folder, unwrap it."""
    if _dest_looks_complete(dest):
        return
    children = [p for p in dest.iterdir() if p.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir() and _dest_looks_complete(children[0]):
        wrapped = children[0]
        for item in wrapped.iterdir():
            target = dest / item.name
            if target.exists():
                continue
            item.rename(target)


def fetch_guideline_corpus(
    *,
    dest: Path,
    url: str | None,
    require: bool,
    skip_if_present: bool,
) -> int:
    if skip_if_present and _dest_looks_complete(dest):
        print(f"Guideline corpus already present under {dest}; skipping fetch.")
        return 0

    if not url:
        message = (
            "GUIDELINE_CORPUS_SAS_URL is not set. "
            "Guideline PDFs and vector indexes will be missing; RAG comparison "
            "will run without retrieved excerpts."
        )
        if require:
            print(message, file=sys.stderr)
            return 1
        print(f"Warning: {message}")
        return 0

    dest.mkdir(parents=True, exist_ok=True)
    suffix = next((s for s in ARCHIVE_SUFFIXES if url.split("?", 1)[0].lower().endswith(s)), ".tar.gz")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"guideline-corpus{suffix}"
        print(f"Downloading guideline corpus into {dest} …")
        _download(url, archive)
        _extract(archive, dest)
        _flatten_if_wrapped(dest)

    if require and not _dest_looks_complete(dest):
        print(
            f"Fetched archive did not contain {', '.join(REQUIRED_MARKERS)} under {dest}.",
            file=sys.stderr,
        )
        return 1
    print("Guideline corpus fetch complete.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument(
        "--url",
        default=os.environ.get("GUIDELINE_CORPUS_SAS_URL", "").strip() or None,
        help="Archive URL (defaults to GUIDELINE_CORPUS_SAS_URL)",
    )
    parser.add_argument(
        "--require",
        action="store_true",
        help="Exit non-zero if the URL is missing or the archive is incomplete",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Do not fail when GUIDELINE_CORPUS_SAS_URL is unset (default)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Download even if indexes already exist",
    )
    args = parser.parse_args()
    dest = args.dest if args.dest.is_absolute() else (Path.cwd() / args.dest)
    return fetch_guideline_corpus(
        dest=dest,
        url=args.url,
        require=args.require and not args.allow_missing,
        skip_if_present=not args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
