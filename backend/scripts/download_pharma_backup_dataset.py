#!/usr/bin/env python3
"""Download AZ medicine dataset from Kaggle for brand-to-generic name resolution.

This dataset maps branded medicine names to their generic ingredients via
short_composition1/short_composition2 columns. Prices from this dataset are
NOT used — pricing comes from the NPPA ceiling price list.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Install dependencies as needed:
# pip install kagglehub[pandas-datasets]
import kagglehub
import pandas as pd

DATASET_SLUG = "shudhanshusingh/az-medicine-dataset-of-india"
FILE_PATH = "A_Z_medicines_dataset_of_India.csv"

BACKEND_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BACKEND_ROOT / "data" / "az_medicines_india.csv"


def main() -> int:
    print(f"Downloading backup dataset {DATASET_SLUG} ...")
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
    print(f"Saved backup dataset to {OUTPUT_PATH}")

    df = pd.read_csv(OUTPUT_PATH)
    print(f"Loaded {len(df):,} products from backup file.")
    print("First 5 records:")
    print(df.head())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
