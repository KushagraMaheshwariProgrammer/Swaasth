"""Hybrid guideline retrieval: ICMR + Clinical Establishments first, CRC STG fallback."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

from app.services.azure_openai_client import azure_openai_json_chat
from app.services.gender_guidelines import filter_chunks_by_gender, filter_conditions_by_gender
from app.services.patient_gender import gender_display_label
from app.services.primary_guidelines_index import get_primary_guidelines_store
from app.services.rag_pipeline import (
    DEFAULT_MAX_CONTEXT_CHARS,
    DEFAULT_RERANK_TOP_K,
    DEFAULT_RETRIEVAL_POOL_K,
    build_context_text,
    prefilter_titles_by_embedding,
    reciprocal_rank_fusion,
    rerank_chunks,
)
from app.services.stg_index import get_stg_index_store

MIN_PRIMARY_CONTEXT_CHARS = 1500
MAX_PRIMARY_DISTANCE = 0.85
TITLE_PREFILTER_K = 50

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


def _ai_json(system: str, user: str) -> dict[str, Any]:
    parsed = azure_openai_json_chat(system, user, max_tokens=800)
    if not parsed:
        return {"matched_conditions": []}
    return parsed


def _gender_prompt_clause(patient_gender: str | None) -> str:
    label = gender_display_label(patient_gender)
    if not label:
        return ""
    return (
        f" Patient sex: {label}. Exclude guideline topics that apply only to the "
        "opposite sex (for example pregnancy/obstetric/gynaecological topics for "
        "male patients, or prostate/testicular topics for female patients)."
    )


def map_diagnosis_to_primary_documents(
    diagnosis: str,
    limit: int = 4,
    *,
    patient_gender: str | None = None,
) -> list[str]:
    store = get_primary_guidelines_store()
    document_names = store.condition_names()
    if not document_names:
        return []

    sample = prefilter_titles_by_embedding(
        diagnosis,
        document_names,
        top_k=TITLE_PREFILTER_K,
        embed_fn=store.embed_texts,
    )
    system = (
        "Map the patient diagnosis to matching guideline document titles from "
        "India's ICMR and Clinical Establishments Act standard treatment guidelines. "
        "Return ONLY valid JSON with key matched_conditions as a list of strings. "
        "Use exact document titles from the provided list whenever possible. "
        "Prefer ICMR and Clinical Establishments Act STG documents that best match "
        f"the diagnosis. Return at most {limit} names. "
        "If no reasonable match exists, return an empty list."
        f"{_gender_prompt_clause(patient_gender)}"
    )
    user = (
        f"Patient diagnosis: {diagnosis}\n\n"
        f"Available guideline documents (subset):\n"
        f"{json.dumps(sample, ensure_ascii=False)}"
    )
    parsed = _ai_json(system, user)
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
    return filter_conditions_by_gender(resolved[:limit], patient_gender)


def map_diagnosis_to_stg_conditions(
    diagnosis: str,
    limit: int = 3,
    *,
    patient_gender: str | None = None,
) -> list[str]:
    store = get_stg_index_store()
    condition_names = store.condition_names()
    if not condition_names:
        return []

    sample = prefilter_titles_by_embedding(
        diagnosis,
        condition_names,
        top_k=TITLE_PREFILTER_K,
        embed_fn=store.embed_texts,
    )
    system = (
        "Map the patient diagnosis to matching condition names from India's "
        "CRC Standard Treatment Guidelines table of contents. "
        "Return ONLY valid JSON with key matched_conditions as a list of strings. "
        "Use exact condition names from the provided list whenever possible. "
        f"Prefer the closest clinical match; return at most {limit} names. "
        "If no reasonable match exists, return an empty list."
        f"{_gender_prompt_clause(patient_gender)}"
    )
    user = (
        f"Patient diagnosis: {diagnosis}\n\n"
        f"Available STG conditions (subset):\n"
        f"{json.dumps(sample, ensure_ascii=False)}"
    )
    parsed = _ai_json(system, user)
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
    return filter_conditions_by_gender(resolved[:limit], patient_gender)


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
    clinical_history: dict[str, Any] | None = None,
    patient_age: int | None = None,
    patient_gender: str | None = None,
) -> str:
    from app.services.clinical_history_relevance import history_context_labels

    symptom_text = ", ".join(_symptom_names(symptoms))[:400]
    test_text = ", ".join(_test_result_summary(test_results))[:400]
    item_summary = ", ".join(item for item in items if item.strip())[:400]
    history_labels = ", ".join(history_context_labels(clinical_history))[:400]
    history_clause = (
        f" Relevant patient history: {history_labels}."
        if history_labels
        else ""
    )
    age_clause = (
        f" Patient age (approximate): {patient_age} years."
        if patient_age is not None
        else ""
    )
    gender_label = gender_display_label(patient_gender)
    gender_clause = (
        f" Patient sex: {gender_label}."
        if gender_label
        else ""
    )
    return (
        f"{diagnosis}. Diagnostic criteria, salient features, signs and symptoms, "
        f"investigations, test interpretation, treatment. "
        f"Symptoms: {symptom_text}. Test results: {test_text}. "
        f"Items to evaluate: {item_summary}.{history_clause}{age_clause}{gender_clause}"
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


def _hybrid_retrieve_chunks(
    store: Any,
    semantic_query: str,
    matched_labels: list[str],
    *,
    pool_k: int = DEFAULT_RETRIEVAL_POOL_K,
    rerank_top_k: int = DEFAULT_RERANK_TOP_K,
    enrich_fn: Any = None,
    patient_gender: str | None = None,
) -> list[dict[str, Any]]:
    toc_chunks = store.get_chunks_for_conditions(matched_labels, limit_per_condition=12)
    for chunk in toc_chunks:
        chunk["source"] = "toc"

    semantic_chunks = store.semantic_search(
        semantic_query,
        top_k=pool_k,
        condition_filter=matched_labels or None,
    )
    if not semantic_chunks:
        semantic_chunks = store.semantic_search(semantic_query, top_k=pool_k)

    keyword_chunks = store.keyword_search(semantic_query, top_k=pool_k)

    fused = reciprocal_rank_fusion([toc_chunks, semantic_chunks, keyword_chunks])
    reranked = rerank_chunks(semantic_query, fused, top_k=rerank_top_k)
    prioritized = _prioritize_chunks(reranked)
    gender_filtered = filter_chunks_by_gender(prioritized, patient_gender)

    if enrich_fn:
        return [enrich_fn(chunk) for chunk in gender_filtered]
    return gender_filtered


def _retrieve_primary_context(
    diagnosis: str,
    semantic_query: str,
    *,
    top_k: int = DEFAULT_RETRIEVAL_POOL_K,
    patient_gender: str | None = None,
) -> dict[str, Any]:
    store = get_primary_guidelines_store()
    if not store.is_ready:
        return {
            "matched_documents": [],
            "chunks": [],
            "guideline_sources": [],
        }

    matched_documents = map_diagnosis_to_primary_documents(
        diagnosis,
        patient_gender=patient_gender,
    )
    chunks = _hybrid_retrieve_chunks(
        store,
        semantic_query,
        matched_documents,
        pool_k=top_k,
        patient_gender=patient_gender,
    )
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
    top_k: int = DEFAULT_RETRIEVAL_POOL_K,
    patient_gender: str | None = None,
) -> dict[str, Any]:
    store = get_stg_index_store()
    if not store.is_ready:
        return {"matched_conditions": [], "chunks": []}

    matched_conditions = map_diagnosis_to_stg_conditions(
        diagnosis,
        patient_gender=patient_gender,
    )

    def enrich(chunk: dict[str, Any]) -> dict[str, Any]:
        item = dict(chunk)
        item["corpus_label"] = "CRC STG"
        item["guideline_tier"] = "fallback"
        return item

    chunks = _hybrid_retrieve_chunks(
        store,
        semantic_query,
        matched_conditions,
        pool_k=top_k,
        enrich_fn=enrich,
        patient_gender=patient_gender,
    )

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
    clinical_history: dict[str, Any] | None = None,
    patient_age: int | None = None,
    patient_gender: str | None = None,
    top_k: int = DEFAULT_RETRIEVAL_POOL_K,
) -> dict[str, Any]:
    semantic_query = _build_semantic_query(
        diagnosis,
        items,
        symptoms=symptoms,
        test_results=test_results,
        clinical_history=clinical_history,
        patient_age=patient_age,
        patient_gender=patient_gender,
    )

    primary = _retrieve_primary_context(
        diagnosis,
        semantic_query,
        top_k=top_k,
        patient_gender=patient_gender,
    )
    primary_chunks = primary["chunks"]
    use_fallback = not _primary_is_sufficient(primary_chunks)

    fallback_chunks: list[dict[str, Any]] = []
    fallback_matched: list[str] = []
    if use_fallback:
        fallback = _retrieve_crc_fallback_context(
            diagnosis,
            semantic_query,
            top_k=top_k,
            patient_gender=patient_gender,
        )
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
        "context_text": build_context_text(merged_chunks, max_chars=DEFAULT_MAX_CONTEXT_CHARS),
        "guideline_sources": guideline_sources,
        "primary_chunk_count": len(primary_chunks),
        "fallback_chunk_count": len(fallback_chunks),
        "used_fallback": bool(fallback_chunks),
        "patient_gender": gender_display_label(patient_gender),
    }
