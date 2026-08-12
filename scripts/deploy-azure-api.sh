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

# Firebase Admin credentials for verifying client ID tokens on upload/extract.
# Prefer env JSON, else the local key file kept outside the git repo.
FIREBASE_KEY_FILE="${FIREBASE_KEY_FILE:-${HOME}/Desktop/swaasth/firebase-adminsdk-swaasth-5bf90.json}"
FIREBASE_SECRET_READY=0
if [[ -n "${FIREBASE_SERVICE_ACCOUNT_JSON:-}" || -f "${FIREBASE_KEY_FILE}" ]]; then
  echo "Updating Firebase Admin secret on ${CONTAINER_APP}..."
  python3 - "${CONTAINER_APP}" "${RESOURCE_GROUP}" "${FIREBASE_KEY_FILE}" <<'PY'
import json, os, pathlib, subprocess, sys

app, rg, key_file = sys.argv[1], sys.argv[2], sys.argv[3]
raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
if not raw:
    raw = json.dumps(json.load(pathlib.Path(key_file).open()), separators=(",", ":"))
subprocess.run(
    [
        "az", "containerapp", "secret", "set",
        "--name", app,
        "--resource-group", rg,
        "--secrets", f"firebase-service-account-json={raw}",
    ],
    check=True,
    stdout=subprocess.DEVNULL,
)
PY
  FIREBASE_SECRET_READY=1
else
  echo "ERROR: FIREBASE_SERVICE_ACCOUNT_JSON unset and ${FIREBASE_KEY_FILE} missing." >&2
  echo "       Refusing to deploy — authenticated extract/analyze will break." >&2
  echo "       Set FIREBASE_SERVICE_ACCOUNT_JSON or place the key file, or set" >&2
  echo "       ALLOW_MISSING_FIREBASE=1 to override (not recommended)." >&2
  if [[ "${ALLOW_MISSING_FIREBASE:-}" != "1" ]]; then
    exit 1
  fi
fi

# Keep Azure OpenAI API key in sync with the Cognitive Services account when possible.
if command -v az >/dev/null 2>&1; then
  AOAI_NAME="${AZURE_OPENAI_ACCOUNT:-swaasthbot}"
  AOAI_RG="${AZURE_OPENAI_RESOURCE_GROUP:-${RESOURCE_GROUP}}"
  if KEY="$(az cognitiveservices account keys list -g "${AOAI_RG}" -n "${AOAI_NAME}" --query key1 -o tsv 2>/dev/null)" && [[ -n "${KEY}" ]]; then
    echo "Refreshing azure-openai-api-key secret from ${AOAI_NAME}..."
    python3 - "${CONTAINER_APP}" "${RESOURCE_GROUP}" "${KEY}" <<'PY'
import subprocess, sys
app, rg, key = sys.argv[1], sys.argv[2], sys.argv[3]
subprocess.run(
    [
        "az", "containerapp", "secret", "set",
        "--name", app,
        "--resource-group", rg,
        "--secrets", f"azure-openai-api-key={key}",
    ],
    check=True,
    stdout=subprocess.DEVNULL,
)
print("azure-openai-api-key refreshed")
PY
  fi
fi

echo "Updating Container App ${CONTAINER_APP} with ${IMAGE}..."
ENV_VARS=(
  "AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT:-gpt-4.1-mini}"
  "AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT:-https://swaasthbot.openai.azure.com/}"
  "AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key"
)
if [[ "${FIREBASE_SECRET_READY}" -eq 1 ]]; then
  ENV_VARS+=("FIREBASE_SERVICE_ACCOUNT_JSON=secretref:firebase-service-account-json")
fi
UPDATE_ARGS=(
  --name "${CONTAINER_APP}"
  --resource-group "${RESOURCE_GROUP}"
  --image "${IMAGE}"
  --min-replicas 1
  --cpu 4.0
  --memory 8.0Gi
  --set-env-vars "${ENV_VARS[@]}"
)
az containerapp update "${UPDATE_ARGS[@]}"

# Keep probe timeouts generous so embedding warmup cannot trip liveness and
# restart the replica mid-request (which the Android app surfaces as unreachable).
python3 - "${CONTAINER_APP}" "${RESOURCE_GROUP}" <<'PY'
import json, subprocess, sys, copy, tempfile, os
app, rg = sys.argv[1], sys.argv[2]
raw = subprocess.check_output([
    "az", "containerapp", "show", "-n", app, "-g", rg, "-o", "json"
], text=True)
src = json.loads(raw)
template = copy.deepcopy(src["properties"]["template"])
scale = template.get("scale") or {}
template["scale"] = {
    "minReplicas": scale.get("minReplicas", 1),
    "maxReplicas": scale.get("maxReplicas", 10),
    "rules": scale.get("rules"),
}
template["containers"][0]["probes"] = [
    {
        "type": "Liveness",
        "httpGet": {"path": "/health", "port": 8000, "scheme": "HTTP"},
        "initialDelaySeconds": 30,
        "periodSeconds": 20,
        "timeoutSeconds": 20,
        "failureThreshold": 6,
        "successThreshold": 1,
    },
    {
        "type": "Readiness",
        "httpGet": {"path": "/ready", "port": 8000, "scheme": "HTTP"},
        "initialDelaySeconds": 10,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 48,
        "successThreshold": 1,
    },
    {
        "type": "Startup",
        "httpGet": {"path": "/health", "port": 8000, "scheme": "HTTP"},
        "initialDelaySeconds": 5,
        "periodSeconds": 5,
        "timeoutSeconds": 10,
        "failureThreshold": 48,
        "successThreshold": 1,
    },
]
app_id = src["id"]
payload = {"properties": {"template": template}}
path = tempfile.mktemp(suffix=".json")
with open(path, "w") as handle:
    json.dump(payload, handle)
try:
    subprocess.run(
        ["az", "rest", "--method", "patch", "--url", f"{app_id}?api-version=2024-03-01", "--body", f"@{path}"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    print("Probe timeouts applied (liveness/readiness tolerant of warmup).")
finally:
    os.unlink(path)
PY

echo "Done. API URL:"
az containerapp show \
  --name "${CONTAINER_APP}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query properties.configuration.ingress.fqdn \
  -o tsv
