"""Structured Azure OpenAI JSON chat helper."""

from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException
from openai import AzureOpenAI

from app.services.json_utils import extract_json_from_text

DEFAULT_API_VERSION = "2024-10-21"


def azure_openai_json_chat(
    system: str,
    user: str,
    *,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    missing = [
        name
        for name, value in (
            ("AZURE_OPENAI_API_KEY", api_key),
            ("AZURE_OPENAI_ENDPOINT", endpoint),
            ("AZURE_OPENAI_DEPLOYMENT", deployment),
        )
        if not value
    ]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing Azure OpenAI configuration: {', '.join(missing)}.",
        )

    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION),
    )
    try:
        response = client.chat.completions.create(
            model=deployment,
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
            detail=f"Azure OpenAI API request failed: {str(exc)}",
        ) from exc

    text = (response.choices[0].message.content or "").strip()
    if not text:
        return {}
    return extract_json_from_text(text)
