FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Prefetch FastEmbed models so first /analyze-treatment request is fast
RUN python -c "from fastembed import TextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; TextEmbedding('BAAI/bge-base-en-v1.5'); TextCrossEncoder('BAAI/bge-reranker-base')"

# Private guideline PDFs + prebuilt indexes (not in the public repo).
# Pass the SAS as base64 via GUIDELINE_CORPUS_SAS_URL_B64 — ACR shell-expands
# raw URLs and breaks on '&' query separators.
COPY scripts/fetch_guideline_corpus.py /tmp/fetch_guideline_corpus.py
ARG GUIDELINE_CORPUS_SAS_URL_B64=
RUN if [ -n "$GUIDELINE_CORPUS_SAS_URL_B64" ]; then \
      export GUIDELINE_CORPUS_SAS_URL="$(printf '%s' "$GUIDELINE_CORPUS_SAS_URL_B64" | base64 -d)"; \
    fi \
 && python /tmp/fetch_guideline_corpus.py --dest /app/data --allow-missing \
 && unset GUIDELINE_CORPUS_SAS_URL

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
