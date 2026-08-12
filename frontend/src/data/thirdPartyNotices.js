export const THIRD_PARTY_NOTICES_LAST_UPDATED = "12 August 2026";

export const THIRD_PARTY_NOTICE_SECTIONS = [
  {
    title: "How this list is produced",
    paragraphs: [
      "Swaasth redistributes or dynamically links the packages below. This page is the in-app counterpart of docs/THIRD_PARTY_NOTICES.md. Regenerate that file with pip-licenses (backend) and license-checker (frontend) before a store release, then update this page.",
      "The Swaasth application itself is licensed under AGPL-3.0 because it incorporates PyMuPDF / MuPDF. See LICENSE, NOTICE, and the Open source page.",
    ],
    bullets: [],
  },
  {
    title: "Backend (Python) — direct dependencies",
    paragraphs: [
      "Installed from backend/requirements.txt. Transitive licenses should be re-scanned with pip-licenses before distribution.",
    ],
    bullets: [
      "fastapi — MIT",
      "uvicorn — BSD-3-Clause",
      "python-multipart — Apache-2.0",
      "PyMuPDF / MuPDF — AGPL-3.0 (dual-licensed commercially by Artifex; Swaasth uses the AGPL edition)",
      "pymupdf-fonts — used with PyMuPDF (see package notices)",
      "pytesseract — Apache-2.0 (wraps Tesseract OCR, Apache-2.0)",
      "Pillow — HPND-derived / PIL license",
      "openai — Apache-2.0 (Azure OpenAI client)",
      "python-dotenv — BSD-3-Clause",
      "fastembed — Apache-2.0 (BAAI bge ONNX models, server-side only)",
      "chromadb — Apache-2.0",
      "rank-bm25 — Apache-2.0",
      "openpyxl — MIT",
      "pdfplumber — MIT (transitive pdfminer.six typically MIT)",
      "pandas — BSD-3-Clause",
      "firebase-admin — Apache-2.0",
    ],
  },
  {
    title: "Frontend (JavaScript) — direct dependencies",
    paragraphs: [
      "Installed from frontend/package.json. Transitive licenses should be re-scanned with license-checker before an Android/Play build.",
    ],
    bullets: [
      "react / react-dom — MIT",
      "react-router-dom — MIT",
      "framer-motion — MIT",
      "firebase — Apache-2.0",
      "@capacitor/core, android, app, filesystem, share, cli — MIT",
      "@capacitor-firebase/authentication — Apache-2.0 / MIT (see package)",
    ],
  },
  {
    title: "Models and data (not shipped in the Android app)",
    paragraphs: [
      "Embedding and reranking models (BAAI/bge-base-en-v1.5 and BAAI/bge-reranker-base) are downloaded server-side via FastEmbed and are not bundled in the APK.",
      "ICMR, CEA/MoHFW, and CRC Standard Treatment Guideline PDFs and the derived Chroma indexes are hosted privately and fetched at deploy time. They are not redistributed in the public source repository.",
    ],
    bullets: [],
  },
];
