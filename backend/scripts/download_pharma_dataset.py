#!/usr/bin/env python3
"""DEPRECATED: This script is no longer needed.

Medicine pricing now uses the NPPA ceiling price list (included in backend/data/).
Brand-to-generic resolution uses the AZ dataset — run download_pharma_backup_dataset.py
if you need to refresh that.

This script previously downloaded the rishgeeky/indian-pharmaceutical-products dataset
which provided market MRP data. That approach has been replaced by NPPA ceiling prices.
"""

import sys


def main() -> int:
    print("DEPRECATED: This script is no longer needed.")
    print()
    print("Medicine pricing now uses NPPA ceiling prices from:")
    print("  backend/data/NPPA_Price_List_03-06-2025.csv")
    print()
    print("For brand-to-generic name resolution, run:")
    print("  python backend/scripts/download_pharma_backup_dataset.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
