"""Hybrid STG retrieval: TOC condition lookup + semantic search."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import HTTPException
from groq import Groq

from app.services.document_extraction import extract_json_from_text
from app.services.stg_index import get_stg_index_store

GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_CONTEXT_CHARS = 6000


def _groq_json(prompt: str) -> dict[str, Any]:
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
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Groq API request failed: {str(exc)}",
        ) from exc
    text = (response.choices[0].message.content or "").strip()
    if not text:
        return {"matched_conditions": []}
    return extract_json_from_text(text)


def map_diagnosis_to_stg_conditions(diagnosis: str, limit: int = 3) -> list[str]:
    store = get_stg_index_store()
    condition_names = store.condition_names()
    if not condition_names:
        return []

    sample = condition_names[:400]
    prompt = f"""
Map the patient diagnosis to up to {limit} matching condition names from India's
Standard Treatment Guidelines table of contents.

Return ONLY valid JSON:
{{
  "matched_conditions": ["Condition Name 1", "Condition Name 2"]
}}

Rules:
- Use exact condition names from the provided list whenever possible.
- Prefer the closest clinical match; return at most {limit} names.
- If no reasonable match exists, return an empty list.

Patient diagnosis: {diagnosis}

Available STG conditions (subset):
{json.dumps(sample, ensure_ascii=False)}
"""
    parsed = _groq_json(prompt)
    matched = parsed.get("matched_conditions") or []
    if not isinstance(matched, list):
        return []

    valid = {name.lower(): name for name in condition_names}
    resolved: list[str] = []
    for item in matched:
        label = str(item).strip()
        if not label:
            continue
        canonical = valid.get(label.lower())
        if canonical and canonical not in resolved:
            resolved.append(canonical)
    return resolved[:limit]


def _dedupe_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id") or "")
        if chunk_id and chunk_id in seen:
            continue
        if chunk_id:
            seen.add(chunk_id)
        merged.append(chunk)
    return merged


def _build_context_text(chunks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    total = 0
    for chunk in chunks:
        header = (
            f"[{chunk.get('condition', '')} | {chunk.get('section_type', 'general')} "
            f"| pages {chunk.get('page_start', '?')}-{chunk.get('page_end', '?')}]"
        )
        body = str(chunk.get("text") or "").strip()
        block = f"{header}\n{body}"
        if total + len(block) > MAX_CONTEXT_CHARS:
            break
        parts.append(block)
        total += len(block)
    return "\n\n---\n\n".join(parts)


def retrieve_stg_context(
    diagnosis: str,
    items: list[str],
    *,
    top_k: int = 8,
) -> dict[str, Any]:
    store = get_stg_index_store()
    if not store.is_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "STG index is not built. Run: python backend/scripts/build_stg_index.py"
            ),
        )

    matched_conditions = map_diagnosis_to_stg_conditions(diagnosis)
    toc_chunks = store.get_chunks_for_conditions(matched_conditions)

    item_summary = ", ".join(item for item in items if item.strip())[:500]
    semantic_query = (
        f"{diagnosis}. Recommended investigations, diagnostic tests, treatment, "
        f"medicines, procedures. Items to evaluate: {item_summary}"
    )
    semantic_chunks = store.semantic_search(
        semantic_query,
        top_k=top_k,
        condition_filter=matched_conditions or None,
    )
    if not semantic_chunks:
        semantic_chunks = store.semantic_search(semantic_query, top_k=top_k)

    chunks = _dedupe_chunks(toc_chunks + semantic_chunks)
    return {
        "matched_conditions": matched_conditions,
        "chunks": chunks,
        "context_text": _build_context_text(chunks),
    }
