# Data sources and provenance

Swaasth compares billed medicines and uploaded clinical documents against published Indian reference datasets. This file records where each corpus came from, whether it is redistributed, and how to refresh it.

**Not legal advice.** Confirm reuse terms with counsel before any new public distribution.

## Hosting rule

Guideline PDFs and derived vector indexes are **not** in the public Git repository. They are stored in a private Azure Blob container (South India) and fetched at Docker build / deploy time by [`backend/scripts/fetch_guideline_corpus.py`](../backend/scripts/fetch_guideline_corpus.py) using `GUIDELINE_CORPUS_SAS_URL`.

AGPL §13 requires corresponding source of the *program*, not third-party data corpora. The fetch script remains in the public source tree.

## Corpora

| Corpus | Publisher | Typical source | Format | In public git? | Reuse posture |
|--------|-----------|----------------|--------|----------------|---------------|
| ICMR Standard Treatment Guidelines | Indian Council of Medical Research | ICMR / STG portals | PDF (private blob) | No | Internal RAG only. Seek written permission if terms are silent. Not GODL unless the specific file says so. |
| MoHFW Clinical Establishments Act STGs | Ministry of Health & Family Welfare / CEA | MoHFW / CEA STG portal | PDF (private blob) | No | Internal RAG only. Government works are copyrighted under Copyright Act s.17(d); s.52(1)(q) is narrow. |
| CRC Standard Treatment Guidelines | Committee for Rational Use of Drugs (reference book) | CRC STG PDF | PDF (private blob) | No | Fallback index only. Treat as copyrighted reference text. |
| NPPA ceiling price list | National Pharmaceutical Pricing Authority | [nppaindia.nic.in](https://www.nppaindia.nic.in/) price lists | CSV in repo (`backend/data/NPPA_Price_List_03-06-2025.csv`) | Yes (factual schedule) | Display as “as per NPPA list dated …”. Refresh when NPPA publishes a new list. |
| Jan Aushadhi / PMBJP catalogue | Pharmaceuticals & Medical Devices Bureau of India | janaushadhi.gov.in product list | CSV in repo (`backend/data/Jan_Aushadhi_Product_List.csv`) | Yes | Informational; frame as an option to discuss with the prescriber, not substitution advice. |
| AZ brand→generic map | Kaggle `shudhanshusingh/az-medicine-dataset-of-india` | Kaggle (do not redistribute the zip) | CSV gitignored; download script `backend/scripts/download_pharma_backup_dataset.py` | No | Kaggle terms typically bar redistribution. Keep private. |
| Restricted medicines list | Internal compilation | `backend/data/medicines/restricted_medicines.csv` | CSV | Yes | Internal screening list; OCR-based, not medical advice. |
| India states/cities | Internal / public geography | `backend/data/india_states_cities_new.csv` | CSV | Yes | Location picker only. |

## Refresh procedure

1. **NPPA** — download the latest ceiling-price spreadsheet from the NPPA site, convert to the existing CSV columns (`Sl_No`, `Medicine`, `Dosage_Form_and_Strength`, `Unit`, `Ceiling_Price_Rs`, `SO_Date`, …), name the file `NPPA_Price_List_DD-MM-YYYY.csv`, update `NPPA_DATASET_PATH` if needed. The API surfaces `rates_source.nppa_list_date` from the filename.
2. **Jan Aushadhi** — replace `Jan_Aushadhi_Product_List.csv` from the PMBJP product list export.
3. **Guidelines** — place updated PDFs in the private blob layout (`Standard Treatment Guidelines/ICMR/`, `…/Clinical Estabilishments Act STG/`, CRC `STG.pdf`), rebuild indexes with `python scripts/build_primary_guidelines_index.py` and `python scripts/build_stg_index.py`, upload a new `corpus.tar.gz` to the blob, rotate the SAS URL if it is time-limited.
4. **AZ brands** — run `python backend/scripts/download_pharma_backup_dataset.py` locally; do not commit the CSV or zip.

## Archive layout for the private blob

```
Standard Treatment Guidelines/
  ICMR/
  Clinical Estabilishments Act STG/
  STG.pdf
primary_guidelines_index/
stg_index/
```
