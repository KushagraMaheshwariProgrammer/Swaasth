"""Hybrid guideline retrieval: ICMR + Clinical Establishments first, CRC STG fallback."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import HTTPException
from groq import Groq

from app.services.document_extraction import extract_json_from_text
from app.services.primary_guidelines_index import get_primary_guidelines_store
from app.services.stg_index import get_stg_index_store

GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_CONTEXT_CHARS = 8000
MIN_PRIMARY_CONTEXT_CHARS = 1500
MAX_PRIMARY_DISTANCE = 0.85

PRIORITY_SECTIONS = {
    "diagnosis",
    "diagnostic tests",
    "investigations",
    "salient features",
    "clinical features",
    "signs and symptoms",
    "case definition",
    "criteria",
    "indications",
}


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


def map_diagnosis_to_primary_documents(diagnosis: str, limit: int = 4) -> list[str]:
    store = get_primary_guidelines_store()
    document_names = store.condition_names()
    if not document_names:
        return []

    sample = document_names[:300]
    prompt = f"""
Map the patient diagnosis to up to {limit} matching guideline document titles from
India's ICMR and Clinical Establishments Act standard treatment guidelines.

Return ONLY valid JSON:
{{
  "matched_conditions": ["Document Title 1", "Document Title 2"]
}}

Rules:
- Use exact document titles from the provided list whenever possible.
- Prefer ICMR and Clinical Establishments Act STG documents that best match the diagnosis.
- Return at most {limit} names.
- If no reasonable match exists, return an empty list.

Patient diagnosis: {diagnosis}

Available guideline documents (subset):
{json.dumps(sample, ensure_ascii=False)}
"""
    parsed = _groq_json(prompt)
    matched = parsed.get("matched_conditions") or []
    if not isinstance(matched, list):
        return []

    valid = {name.lower(): name for name in document_names}
    resolved: list[str] = []
    for item in matched:
        label = str(item).strip()
        if not label:
            continue
        canonical = valid.get(label.lower())
        if canonical and canonical not in resolved:
            resolved.append(canonical)
    return resolved[:limit]


def map_diagnosis_to_stg_conditions(diagnosis: str, limit: int = 3) -> list[str]:
    store = get_stg_index_store()
    condition_names = store.condition_names()
    if not condition_names:
        return []

    sample = condition_names[:400]
    prompt = f"""
Map the patient diagnosis to up to {limit} matching condition names from India's
CRC Standard Treatment Guidelines table of contents.

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


def _prioritize_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []
    for chunk in chunks:
        section = str(chunk.get("section_type") or "general").lower()
        if section in PRIORITY_SECTIONS:
            priority.append(chunk)
        else:
            other.append(chunk)
    return priority + other


def _build_context_text(chunks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    total = 0
    for chunk in chunks:
        corpus_label = chunk.get("corpus_label") or chunk.get("chapter") or "Guidelines"
        header = (
            f"[{corpus_label} | {chunk.get('condition', '')} | "
            f"{chunk.get('section_type', 'general')} | "
            f"pages {chunk.get('page_start', '?')}-{chunk.get('page_end', '?')}]"
        )
        body = str(chunk.get("text") or "").strip()
        block = f"{header}\n{body}"
        if total + len(block) > MAX_CONTEXT_CHARS:
            break
        parts.append(block)
        total += len(block)
    return "\n\n---\n\n".join(parts)


def _symptom_names(symptoms: list[Any] | None) -> list[str]:
    names: list[str] = []
    for item in symptoms or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return names


def _test_result_summary(test_results: list[dict[str, Any]] | None) -> list[str]:
    summaries: list[str] = []
    for item in test_results or []:
        if not isinstance(item, dict):
            continue
        test_name = str(item.get("test_name") or "").strip()
        if not test_name:
            continue
        value = item.get("value")
        result = item.get("result")
        unit = item.get("unit")
        parts = [test_name]
        if value:
            parts.append(f"value {value}")
        if unit:
            parts.append(str(unit))
        if result:
            parts.append(str(result))
        summaries.append(" ".join(parts))
    return summaries


def _build_semantic_query(
    diagnosis: str,
    items: list[str],
    *,
    symptoms: list[Any] | None = None,
    test_results: list[dict[str, Any]] | None = None,
) -> str:
    symptom_text = ", ".join(_symptom_names(symptoms))[:400]
    test_text = ", ".join(_test_result_summary(test_results))[:400]
    item_summary = ", ".join(item for item in items if item.strip())[:400]
    return (
        f"{diagnosis}. Diagnostic criteria, salient features, signs and symptoms, "
        f"investigations, test interpretation, treatment. "
        f"Symptoms: {symptom_text}. Test results: {test_text}. "
        f"Items to evaluate: {item_summary}"
    )


def _primary_is_sufficient(chunks: list[dict[str, Any]]) -> bool:
    if not chunks:
        return False
    total_chars = sum(len(str(chunk.get("text") or "")) for chunk in chunks)
    if total_chars < MIN_PRIMARY_CONTEXT_CHARS:
        return False
    distances = [
        float(chunk["distance"])
        for chunk in chunks
        if chunk.get("distance") is not None
    ]
    if distances and min(distances) > MAX_PRIMARY_DISTANCE:
        return False
    return True


def _retrieve_primary_context(
    diagnosis: str,
    semantic_query: str,
    *,
    top_k: int = 10,
) -> dict[str, Any]:
    store = get_primary_guidelines_store()
    if not store.is_ready:
        return {
            "matched_documents": [],
            "chunks": [],
            "guideline_sources": [],
        }

    matched_documents = map_diagnosis_to_primary_documents(diagnosis)
    toc_chunks = store.get_chunks_for_conditions(
        matched_documents,
        limit_per_condition=12,
    )
    semantic_chunks = store.semantic_search(
        semantic_query,
        top_k=top_k,
        condition_filter=matched_documents or None,
    )
    if not semantic_chunks:
        semantic_chunks = store.semantic_search(semantic_query, top_k=top_k)

    chunks = _prioritize_chunks(_dedupe_chunks(toc_chunks + semantic_chunks))
    guideline_sources = sorted(
        {
            str(chunk.get("corpus_label") or "")
            for chunk in chunks
            if chunk.get("corpus_label")
        }
    )
    return {
        "matched_documents": matched_documents,
        "chunks": chunks,
        "guideline_sources": guideline_sources,
    }


def _retrieve_crc_fallback_context(
    diagnosis: str,
    semantic_query: str,
    *,
    top_k: int = 10,
) -> dict[str, Any]:
    store = get_stg_index_store()
    if not store.is_ready:
        return {"matched_conditions": [], "chunks": []}

    matched_conditions = map_diagnosis_to_stg_conditions(diagnosis)
    toc_chunks = store.get_chunks_for_conditions(matched_conditions, limit_per_condition=16)
    semantic_chunks = store.semantic_search(
        semantic_query,
        top_k=top_k,
        condition_filter=matched_conditions or None,
    )
    if not semantic_chunks:
        semantic_chunks = store.semantic_search(semantic_query, top_k=top_k)

    chunks = []
    for chunk in _prioritize_chunks(_dedupe_chunks(toc_chunks + semantic_chunks)):
        enriched = dict(chunk)
        enriched["corpus_label"] = "CRC STG"
        enriched["guideline_tier"] = "fallback"
        chunks.append(enriched)

    return {
        "matched_conditions": matched_conditions,
        "chunks": chunks,
    }


def retrieve_stg_context(
    diagnosis: str,
    items: list[str],
    *,
    symptoms: list[Any] | None = None,
    test_results: list[dict[str, Any]] | None = None,
    top_k: int = 10,
) -> dict[str, Any]:
    semantic_query = _build_semantic_query(
        diagnosis,
        items,
        symptoms=symptoms,
        test_results=test_results,
    )

    primary = _retrieve_primary_context(diagnosis, semantic_query, top_k=top_k)
    primary_chunks = primary["chunks"]
    use_fallback = not _primary_is_sufficient(primary_chunks)

    fallback_chunks: list[dict[str, Any]] = []
    fallback_matched: list[str] = []
    if use_fallback:
        fallback = _retrieve_crc_fallback_context(diagnosis, semantic_query, top_k=top_k)
        fallback_chunks = fallback["chunks"]
        fallback_matched = fallback["matched_conditions"]
        if not primary_chunks and not fallback_chunks:
            raise HTTPException(
                status_code=503,
                detail=(
                    "No guideline indexes are ready. Run "
                    "python backend/scripts/build_primary_guidelines_index.py and "
                    "python backend/scripts/build_stg_index.py"
                ),
            )
    elif not primary_chunks:
        raise HTTPException(
            status_code=503,
            detail=(
                "Primary guidelines index is not built. Run: "
                "python backend/scripts/build_primary_guidelines_index.py"
            ),
        )

    merged_chunks = _dedupe_chunks(primary_chunks + fallback_chunks)
    guideline_sources = list(primary.get("guideline_sources") or [])
    if fallback_chunks and "CRC STG" not in guideline_sources:
        guideline_sources.append("CRC STG")

    matched_conditions = list(primary.get("matched_documents") or [])
    for label in fallback_matched:
        if label not in matched_conditions:
            matched_conditions.append(label)

    return {
        "matched_conditions": matched_conditions,
        "matched_primary_documents": primary.get("matched_documents") or [],
        "matched_crc_conditions": fallback_matched,
        "chunks": merged_chunks,
        "context_text": _build_context_text(merged_chunks),
        "guideline_sources": guideline_sources,
        "primary_chunk_count": len(primary_chunks),
        "fallback_chunk_count": len(fallback_chunks),
        "used_fallback": bool(fallback_chunks),
    }
