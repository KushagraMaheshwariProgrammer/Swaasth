# Backend data files

Tracked in git:

- `NPPA_Price_List_03-06-2025.csv` — NPPA ceiling prices (factual schedule)
- `Jan_Aushadhi_Product_List.csv` — PMBJP catalogue
- `medicines/` — restricted-medicine list and rationality tables
- `india_states_cities_new.csv` — location picker
- `icmr_document_curator.json` — title aliases used when building the private index

**Not in git** (fetched at deploy time from a private Azure Blob):

- `Standard Treatment Guidelines/` — ICMR, CEA/MoHFW, and CRC PDFs
- `primary_guidelines_index/` and `stg_index/` — prebuilt Chroma indexes

See `backend/scripts/fetch_guideline_corpus.py` and `docs/DATA_SOURCES.md`.
Local copies may exist on a developer machine; they must not be committed.
