"""Boot-time checks for production-critical configuration."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


def _firebase_configured() -> bool:
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return False
        return bool(payload.get("private_key") and payload.get("client_email"))
    rel_path = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json"
    )
    return (_BACKEND_ROOT / rel_path).is_file()


def _azure_openai_configured() -> bool:
    return all(
        os.getenv(name, "").strip()
        for name in (
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
        )
    )


def log_critical_config_status() -> None:
    """Log missing production config so deploys fail loudly in container logs."""
    if not _firebase_configured():
        logger.error(
            "CRITICAL: Firebase Admin credentials are not configured. "
            "Set FIREBASE_SERVICE_ACCOUNT_JSON (or PATH). Authenticated "
            "upload/extract/analyze calls will fail."
        )
    else:
        logger.info("Firebase Admin credentials: configured")

    if not _azure_openai_configured():
        logger.error(
            "CRITICAL: Azure OpenAI is not fully configured "
            "(AZURE_OPENAI_API_KEY / ENDPOINT / DEPLOYMENT). "
            "Document extraction and classification will fail."
        )
    else:
        logger.info(
            "Azure OpenAI configured: endpoint=%s deployment=%s",
            os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/"),
            os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
        )
