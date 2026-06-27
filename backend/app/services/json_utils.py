"""JSON parsing helpers for LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException


def extract_json_from_text(raw_text: str) -> dict[str, Any]:
    cleaned_text = raw_text.strip()
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned_text, re.DOTALL)
        if not match:
            raise HTTPException(
                status_code=500,
                detail="Groq returned an invalid response format.",
            )
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=500,
                detail="Groq returned malformed JSON.",
            ) from exc
