import json
import os
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)

_backend_root = Path(__file__).resolve().parent.parent.parent
_initialized = False


def _ensure_firebase_initialized() -> None:
    global _initialized
    if _initialized:
        return

    json_str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if json_str:
        cred = credentials.Certificate(json.loads(json_str))
    else:
        rel_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json")
        cred_path = _backend_root / rel_path
        if not cred_path.is_file():
            raise RuntimeError(f"Firebase service account not found at {cred_path}")
        cred = credentials.Certificate(str(cred_path))

    firebase_admin.initialize_app(cred)
    _initialized = True


def verify_firebase_token(id_token: str) -> dict[str, Any]:
    _ensure_firebase_initialized()
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
        ) from exc


def user_profile_from_claims(claims: dict[str, Any]) -> dict[str, Any]:
    return {
        "uid": claims.get("uid") or claims.get("sub"),
        "email": claims.get("email"),
        "name": claims.get("name"),
        "picture": claims.get("picture"),
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required.")
    if not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return verify_firebase_token(credentials.credentials)
