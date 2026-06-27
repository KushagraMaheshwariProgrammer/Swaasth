# Secrets & environment setup

## Quick start (new teammate)

```bash
npm run setup:env
# Edit backend/.env and set GROQ_API_KEY
cd backend && ./run_dev.sh   # terminal 1
npm run dev                  # terminal 2 (from repo root)
```

## What lives on GitHub (shared)

| File | Purpose |
|------|---------|
| `frontend/google-services.json` | Firebase Android client config (required for auth & Firestore) |
| `google-services.json` | Copy at repo root for tooling |
| `frontend/.env.example` | Template for optional local overrides |
| `backend/.env.example` | Template for backend secrets |
| `firestore.rules` | Firestore security rules |

Firebase **client** API keys in `google-services.json` are designed to be bundled with the app. Protect your project with [Firestore rules](https://firebase.google.com/docs/firestore/security/get-started) and [API key restrictions](https://cloud.google.com/docs/authentication/api-keys#api_key_restrictions) in Google Cloud Console.

## What stays local only (never commit)

| File | Purpose |
|------|---------|
| `backend/.env` | `GROQ_API_KEY` for AI bill/prescription parsing |
| `frontend/.env` | Optional overrides only (usually empty) |
| `backend/firebase-service-account.json` | Firebase Admin SDK (only if added later) |

Share `GROQ_API_KEY` with teammates through a password manager or secure channel — not GitHub Issues, Slack channels, or commits.

## Rotating exposed keys

A `GROQ_API_KEY` was previously committed to git history and has been scrubbed. **Rotate the key** at [console.groq.com/keys](https://console.groq.com/keys), then update `backend/.env` locally and share the new key with teammates securely.

## After a history rewrite

If `git pull` fails after a force-push, reset to the remote:

```bash
git fetch origin
git reset --hard origin/main
```

Then run `npm run setup:env` if you are missing local `.env` files.

## STG index (prescription appropriateness)

The treatment audit uses a hybrid RAG pipeline over Indian Standard Treatment Guidelines:

1. **Primary index** — ICMR + Clinical Establishments Act STG (`primary_guidelines_index`)
2. **Fallback index** — CRC Standard Treatment Guidelines (`stg_index`)

### Source files

| Path | Purpose |
|------|---------|
| `backend/data/Standard Treatment Guidelines/STG.pdf` | CRC STG source PDF |
| `backend/data/icmr_index/chunks_manifest.json` | Legacy ICMR parsed chunks |
| `backend/data/Standard Treatment Guidelines/Clinical Estabilishments Act STG/` | CEA source PDFs (optional if manifest exists) |
| `backend/data/icmr_document_curator.json` | ICMR title aliases and exclusion patterns |

### Build indexes (required once per machine / after model changes)

```bash
cd backend
pip install -r requirements.txt
python scripts/build_primary_guidelines_index.py
python scripts/build_stg_index.py
```

This writes gitignored directories:

- `backend/data/primary_guidelines_index/` — combined ICMR + CEA Chroma index
- `backend/data/stg_index/` — CRC STG Chroma index

Embeddings use `fastembed` locally (no extra API key). Default embedding model is `BAAI/bge-base-en-v1.5`.

### Optional environment variables

Set in `backend/.env` (see `backend/.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `STG_INDEX_DIR` | `backend/data/stg_index` | CRC STG index location |
| `PRIMARY_GUIDELINES_INDEX_DIR` | `backend/data/primary_guidelines_index` | Primary guidelines index |
| `STG_EMBED_MODEL` | `BAAI/bge-base-en-v1.5` | Embedding model (requires rebuild if changed) |
| `STG_RERANK_MODEL` | `BAAI/bge-reranker-base` | Cross-encoder reranker |
| `STG_RETRIEVAL_POOL_K` | `30` | Candidates before reranking |
| `STG_RERANK_TOP_K` | `12` | Chunks passed to audit LLM |
| `STG_MAX_CONTEXT_CHARS` | `16000` | Max STG context size |

### Evaluation (optional)

```bash
cd backend
python scripts/eval_rag_retrieval.py
python scripts/eval_rag_audit.py --runs 3
pytest tests/test_rag_pipeline.py tests/test_rag_eval_regression.py -q
```

---

## Legacy STG-only build (CRC fallback index only)

Place the CRC Standard Treatment Guidelines PDF at:

`backend/data/Standard Treatment Guidelines/STG.pdf`

Then build the CRC vector index:

```bash
cd backend && python scripts/build_stg_index.py
```

This writes `backend/data/stg_index/` (gitignored). No extra API key is required for embeddings.
