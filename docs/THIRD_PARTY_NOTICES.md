# Third-party notices

Last updated: 12 August 2026.

Swaasth is AGPL-3.0 (see `LICENSE` and `NOTICE`). This file lists **direct** dependencies. Before a Play / Galaxy Store build, regenerate:

```bash
# Backend (from a venv with requirements installed)
pip install pip-licenses
pip-licenses --from=mixed --format=markdown --output-file docs/THIRD_PARTY_NOTICES.generated.md

# Frontend
npx license-checker --production --summary
```

Then update this file and `frontend/src/data/thirdPartyNotices.js` (in-app `/licenses` page).

## Backend (backend/requirements.txt)

| Package | Typical license | Notes |
|---------|-----------------|-------|
| fastapi | MIT | |
| uvicorn | BSD-3-Clause | |
| python-multipart | Apache-2.0 | |
| PyMuPDF | AGPL-3.0 | Drives project AGPL; Artifex commercial license not used |
| pymupdf-fonts | See package | Used with PyMuPDF Story PDF rendering |
| pytesseract | Apache-2.0 | Wraps Tesseract OCR (Apache-2.0) |
| Pillow | HPND / PIL | |
| openai | Apache-2.0 | Azure OpenAI client |
| python-dotenv | BSD-3-Clause | |
| fastembed | Apache-2.0 | Server-side BAAI bge models |
| chromadb | Apache-2.0 | |
| rank-bm25 | Apache-2.0 | |
| openpyxl | MIT | |
| pdfplumber | MIT | Transitive pdfminer.six typically MIT |
| pandas | BSD-3-Clause | |
| firebase-admin | Apache-2.0 | |

## Frontend (frontend/package.json)

| Package | Typical license |
|---------|-----------------|
| react, react-dom | MIT |
| react-router-dom | MIT |
| framer-motion | MIT |
| firebase | Apache-2.0 |
| @capacitor/* | MIT |
| @capacitor-firebase/authentication | See package (Apache-2.0 / MIT) |

Embedding models are **not** shipped in the Android app. Guideline PDFs are **not** in the public repository.
