#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ACR_NAME="${ACR_NAME:-swaasth}"
IMAGE_REPO="${ACR_NAME}.azurecr.io/swaasth-api"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CONTAINER_APP="${CONTAINER_APP:-swaasth-api}"
RESOURCE_GROUP="${RESOURCE_GROUP:-swaasth}"

echo "Building ${IMAGE_REPO}:${IMAGE_TAG} in ACR (no local Docker required)..."
BUILD_ID="$(az acr build \
  --registry "${ACR_NAME}" \
  --image "swaasth-api:${IMAGE_TAG}" \
  --file "${ROOT}/backend/Dockerfile" \
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
