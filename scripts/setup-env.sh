#!/usr/bin/env bash
# Create local .env files from examples (skips existing files).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

copy_if_missing() {
  local example="$1"
  local target="$2"
  if [[ -f "$target" ]]; then
    echo "  skip  $target (already exists)"
  elif [[ -f "$example" ]]; then
    cp "$example" "$target"
    echo "  create $target"
  else
    echo "  warn  missing $example" >&2
  fi
}

echo "Setting up local environment files..."
copy_if_missing "$ROOT/backend/.env.example" "$ROOT/backend/.env"
copy_if_missing "$ROOT/frontend/.env.example" "$ROOT/frontend/.env"

echo ""
echo "Next steps:"
echo "  1. Add your Azure OpenAI credentials to backend/.env"
echo "  2. Firebase config is already in frontend/google-services.json"
echo "  3. Start backend:  cd backend && ./run_dev.sh"
echo "  4. Start frontend: npm run dev"
