"""Structured Groq JSON chat helper."""

from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException
from groq import Groq

from app.services.json_utils import extract_json_from_text

GROQ_MODEL = "llama-3.3-70b-versatile"


def groq_json_chat(
    system: str,
    user: str,
    *,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not set in the environment.",
        )

    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Groq API request failed: {str(exc)}",
        ) from exc

    text = (response.choices[0].message.content or "").strip()
    if not text:
        return {}
    return extract_json_from_text(text)
