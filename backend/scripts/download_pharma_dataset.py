#!/usr/bin/env python3
"""Download primary Indian pharmaceutical products dataset from Kaggle.

Also run download_pharma_backup_dataset.py for the AZ fallback database.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Install dependencies as needed:
# pip install kagglehub[pandas-datasets]
import kagglehub
from kagglehub import KaggleDatasetAdapter

DATASET_SLUG = "rishgeeky/indian-pharmaceutical-products"
FILE_PATH = "indian_pharmaceutical_products_clean.csv"

BACKEND_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BACKEND_ROOT / "data" / "indian_pharmaceutical_products.csv"


def main() -> int:
    print(f"Downloading {DATASET_SLUG} ...")
    cache_dir = Path(kagglehub.dataset_download(DATASET_SLUG))
    source = cache_dir / FILE_PATH
    if not source.exists():
        matches = list(cache_dir.rglob(FILE_PATH))
        if not matches:
            print(f"ERROR: {FILE_PATH} not found under {cache_dir}", file=sys.stderr)
            return 1
        source = matches[0]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, OUTPUT_PATH)
    print(f"Saved dataset to {OUTPUT_PATH}")

    df = kagglehub.load_dataset(
        KaggleDatasetAdapter.PANDAS,
        DATASET_SLUG,
        FILE_PATH,
    )
    print(f"Loaded {len(df):,} products from Kaggle.")
    print("First 5 records:")
    print(df.head())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
