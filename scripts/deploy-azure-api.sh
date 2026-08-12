#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ACR_NAME="${ACR_NAME:-swaasth}"
IMAGE_REPO="${ACR_NAME}.azurecr.io/swaasth-api"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CONTAINER_APP="${CONTAINER_APP:-swaasth-api}"
RESOURCE_GROUP="${RESOURCE_GROUP:-swaasth}"

# Private guideline PDFs + Chroma indexes (not in git). Prefer env, else local file
# written outside the repo by the corpus-upload step.
if [[ -z "${GUIDELINE_CORPUS_SAS_URL:-}" && -f "${HOME}/Desktop/swaasth/GUIDELINE_CORPUS_SAS_URL.txt" ]]; then
  GUIDELINE_CORPUS_SAS_URL="$(tr -d '\n' < "${HOME}/Desktop/swaasth/GUIDELINE_CORPUS_SAS_URL.txt")"
fi
if [[ -z "${GUIDELINE_CORPUS_SAS_URL:-}" ]]; then
  echo "WARNING: GUIDELINE_CORPUS_SAS_URL is unset. Image will build without STG indexes." >&2
fi

echo "Building ${IMAGE_REPO}:${IMAGE_TAG} in ACR (no local Docker required)..."
BUILD_ARGS=()
if [[ -n "${GUIDELINE_CORPUS_SAS_URL:-}" ]]; then
  # Base64 avoids ACR agent shell-breaking on '&' in SAS query strings.
  SAS_B64="$(printf '%s' "${GUIDELINE_CORPUS_SAS_URL}" | base64 | tr -d '\n')"
  BUILD_ARGS+=(--build-arg "GUIDELINE_CORPUS_SAS_URL_B64=${SAS_B64}")
fi
BUILD_ID="$(az acr build \
  --registry "${ACR_NAME}" \
  --image "swaasth-api:${IMAGE_TAG}" \
  --file "${ROOT}/backend/Dockerfile" \
  "${BUILD_ARGS[@]}" \
  "${ROOT}/backend" \
  --query id \
  -o tsv)"

echo "Build ${BUILD_ID} finished. Resolving image digest..."
DIGEST="$(az acr repository show-manifests \
  --name "${ACR_NAME}" \
  --repository swaasth-api \
  --orderby time_desc \
  --top 1 \
  --query "[0].digest" \
  -o tsv)"
IMAGE="${IMAGE_REPO}@${DIGEST}"

echo "Updating Container App ${CONTAINER_APP} with ${IMAGE}..."
az containerapp update \
  --name "${CONTAINER_APP}" \
  --resource-group "${RESOURCE_GROUP}" \
  --image "${IMAGE}" \
  --min-replicas 1 \
  --cpu 4.0 \
  --memory 8.0Gi

echo "Done. API URL:"
az containerapp show \
  --name "${CONTAINER_APP}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query properties.configuration.ingress.fqdn \
  -o tsv
