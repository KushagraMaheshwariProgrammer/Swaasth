# Railway / Azure deployment — Swaasth FastAPI backend

Production API (as of August 2026) runs on **Azure Container Apps, South India**:

`https://swaasth-api.redbay-ce8ac868.southindia.azurecontainerapps.io`

`frontend/.env.production` sets `VITE_API_BASE` to that URL. Custom domain `api.swaasth.in` may CNAME to the same app. Railway remains an optional alternate; do not assume Railway is live unless you have provisioned it.

## Architecture overview

```
React web (swaasth.in)  ──HTTPS──►  Azure Container Apps (South India)
Capacitor Android       ──HTTPS──►  same API
```

The backend is a stateless FastAPI app. NPPA / Jan Aushadhi CSVs are in the image. **Guideline PDFs and Chroma indexes are not in git**; the Docker build fetches them from a private Azure Blob via `GUIDELINE_CORPUS_SAS_URL` (`backend/scripts/fetch_guideline_corpus.py`).

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for local testing)
- An Azure OpenAI resource **in an Indian region** with a GPT-4o mini deployment
- Azure Container Apps (or Railway) linked to this repo
- Private blob archive of guideline PDFs + prebuilt indexes, and a SAS URL

If indexes are missing locally and you have the PDFs:

```bash
cd backend
pip install -r requirements.txt
python scripts/build_primary_guidelines_index.py
python scripts/build_stg_index.py
```

Or fetch a prebuilt archive:

```bash
export GUIDELINE_CORPUS_SAS_URL='https://…'
python scripts/fetch_guideline_corpus.py --dest data --require
```

---

## Backend structure reference

| Item | Location |
|------|----------|
| FastAPI app | `backend/app/main.py` → `app` |
| Production entrypoint | `backend/main.py` → `uvicorn main:app` |
| Dependencies | `backend/requirements.txt` |
| Environment template | `backend/.env.example` |
| Docker build | `backend/Dockerfile` |
| Railway config | `backend/railway.json` |
| Health check | `GET /health` |

### API routes (unchanged)

| Route | Purpose |
|-------|---------|
| `POST /upload-bill` | OCR + Azure OpenAI bill extraction |
| `POST /compare-bill` | General bill review (NPPA, Jan Aushadhi, audit flags) |
| `POST /upload-prescription` | Prescription OCR + extraction |
| `POST /upload-clinical-document` | Lab/discharge summary upload |
| `POST /analyze-treatment` | STG treatment appropriateness audit |
| `POST /api/reports/render-pdf` | Unified PDF report generation |

---

## Environment variables

Copy [`backend/.env.example`](../backend/.env.example) for local use. On Railway, set these in **Variables**:

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_API_KEY` | **Yes** | Key for the Azure OpenAI resource |
| `AZURE_OPENAI_ENDPOINT` | **Yes** | Resource endpoint, such as `https://RESOURCE.openai.azure.com/` |
| `AZURE_OPENAI_DEPLOYMENT` | **Yes** | Chat deployment name on `swaasthbot` (currently `gpt-4.1-mini`) |
| `AZURE_OPENAI_API_VERSION` | Optional | Defaults to `2024-10-21` |
| `ENV` | Recommended | Set to `production` |
| `PORT` | Auto | Railway injects this; Dockerfile defaults to `8000` locally |
| `CORS_ORIGINS` | Optional | Comma-separated extra allowed origins |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Optional | Full service-account JSON (single line) for Firebase Admin |
| `GUIDELINE_CORPUS_SAS_URL` | **Yes (production image)** | SAS URL of the private guideline archive |
| `STG_INDEX_DIR` | Optional | Default `data/stg_index` |
| `PRIMARY_GUIDELINES_INDEX_DIR` | Optional | Default `data/primary_guidelines_index` |

Production CORS defaults (in code) include `https://swaasth.in`, `https://www.swaasth.in`, localhost dev ports, and `capacitor://localhost` for the Android app.

---

## Test locally with Docker

From the **repo root**:

```bash
# Build (first run downloads FastEmbed models — may take several minutes)
docker build -t swaasth-api -f backend/Dockerfile backend/

# Run
docker run --rm -p 8000:8000 \
  -e AZURE_OPENAI_API_KEY="your-azure-key" \
  -e AZURE_OPENAI_ENDPOINT="https://YOUR-RESOURCE.openai.azure.com/" \
  -e AZURE_OPENAI_DEPLOYMENT="gpt-4o-mini" \
  -e ENV=production \
  swaasth-api
```

Smoke tests:

```bash
curl http://localhost:8000/health
# Expected: Backend is running

curl http://localhost:8000/api/locations/states
```

Stop with `Ctrl+C`.

---

## Git: commit deployment files and indexes

Vector indexes include files over GitHub's 100 MB limit, so Chroma binaries are stored with **Git LFS**.

### One-time setup (each machine)

```bash
brew install git-lfs   # macOS; or see https://git-lfs.github.com
git lfs install
```

### Clone with LFS

```bash
git clone https://github.com/KushagraMaheshwariProgrammer/Swaasth.git
cd Swaasth
git lfs pull
```

Railway and GitHub Actions fetch LFS objects automatically when `.gitattributes` is present.

Ensure vector indexes are tracked (`.gitignore` no longer excludes them):

```bash
git add backend/data/stg_index/ backend/data/primary_guidelines_index/
git add backend/Dockerfile backend/.dockerignore backend/main.py backend/railway.json
git add backend/requirements.txt backend/.env.example .gitattributes
git add backend/app/main.py backend/app/services/document_extraction.py backend/app/services/firebase_auth.py
git add .gitignore docs/RAILWAY_DEPLOYMENT.md

git status   # review before committing
git commit -m "Add Railway Docker deployment for FastAPI backend"
git push origin main
```

The Chroma directories add ~184 MB to LFS storage (manifest JSON stays in Git; `chroma/` binaries use LFS).

---

## Deploy on Railway

### 1. Create project

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
2. Select the Swaasth repository.

### 2. Configure service

1. Open the service → **Settings**.
2. Set **Root Directory** to `backend`.
3. Confirm **Builder** is Dockerfile (Railway reads `backend/railway.json` and `backend/Dockerfile`).

### 3. Set variables

In **Variables**, add:

```
AZURE_OPENAI_API_KEY=<your-key>
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
ENV=production
```

Optionally add `CORS_ORIGINS` or `FIREBASE_SERVICE_ACCOUNT_JSON`.

### 4. Deploy

Railway builds the Docker image and starts:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

First deploy may take 10–20 minutes (large data + FastEmbed model prefetch).

### 5. Get the public API URL

1. Open **Settings** → **Networking** → **Generate Domain**.
2. Railway assigns a URL like:

   ```
   https://swaasth-backend-production.up.railway.app
   ```

3. Verify:

   ```bash
   curl https://<your-service>.up.railway.app/health
   ```

Use this URL as your API base until a custom domain is configured.

---

## Map custom domain: api.swaasth.in

1. Railway → service **Settings** → **Networking** → **Custom Domain**.
2. Enter `api.swaasth.in`.
3. Railway shows a CNAME target (e.g. `xxxx.up.railway.app`).
4. At your DNS provider (where `swaasth.in` is managed), add:

   | Type | Name | Value |
   |------|------|-------|
   | CNAME | `api` | `<railway-target>` |

5. Wait for DNS propagation (minutes to hours).
6. Railway provisions HTTPS automatically.
7. Confirm:

   ```bash
   curl https://api.swaasth.in/health
   ```

---

## Connect frontend and Android app

### React web (production build)

Set the API base when building:

```bash
# frontend/.env.production (or CI secret)
VITE_API_BASE=https://api.swaasth.in
```

Then build and deploy the frontend to your hosting (Firebase Hosting, Vercel, etc.):

```bash
cd frontend
npm run build
```

During local dev, leave `VITE_API_BASE` unset — Vite proxies to `http://127.0.0.1:8000`.

### Capacitor Android

Rebuild with the production API URL baked in:

```bash
# frontend/.env
VITE_API_BASE=https://api.swaasth.in

cd frontend
npm run build
npx cap sync android
```

Install the new APK/AAB on devices. The app probes `/health` to confirm connectivity.

---

## Data directories: Git vs runtime

| Path | In Git? | Notes |
|------|---------|-------|
| `backend/data/` reference CSVs (NPPA, locations, Jan Aushadhi, AZ brands) | Yes | Loaded at startup |
| `backend/data/stg_index/` | Yes | Pre-built Chroma index |
| `backend/data/primary_guidelines_index/` | Yes | Pre-built Chroma index |
| FastEmbed ONNX models | No | Prefetched during Docker build |
| `backend/.env`, `firebase-service-account.json` | No | Use Railway variables |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Build timeout | FastEmbed model download slow | Retry deploy; models cache in Docker layer |
| `Tesseract is not installed` | Missing apt package | Rebuild from current Dockerfile |
| `/analyze-treatment` 503 | Indexes missing from image | Ensure indexes are committed and copied in Docker build |
| CORS error from browser | Origin not allowed | Add origin to `CORS_ORIGINS` on Railway |
| 502 on startup | CSV/index load slow | Health check timeout is 120s in `railway.json`; check deploy logs |

View logs: Railway dashboard → service → **Deployments** → **View Logs**.

---

## Local dev (unchanged)

```bash
cd backend && ./run_dev.sh   # terminal 1 — port 8000
npm run dev                  # terminal 2 — Vite on 5173
```

Local dev still uses `uvicorn app.main:app` via `run_dev.sh`; production uses `uvicorn main:app` via Docker.
