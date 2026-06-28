"""Shared RAG retrieval utilities: BM25, RRF, reranking, citation validation."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable

DEFAULT_EMBED_MODEL = os.getenv("STG_EMBED_MODEL", "BAAI/bge-base-en-v1.5")
DEFAULT_RERANK_MODEL = os.getenv("STG_RERANK_MODEL", "BAAI/bge-reranker-base")
DEFAULT_RETRIEVAL_POOL_K = int(os.getenv("STG_RETRIEVAL_POOL_K", "30"))
DEFAULT_RERANK_TOP_K = int(os.getenv("STG_RERANK_TOP_K", "12"))
DEFAULT_MAX_CONTEXT_CHARS = int(os.getenv("STG_MAX_CONTEXT_CHARS", "16000"))
RRF_K = 60

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

_reranker: Any = None


def tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


class Bm25Index:
    """In-memory BM25 index built from chunks_manifest.json."""

    def __init__(self, manifest_path: Path) -> None:
        self._chunk_ids: list[str] = []
        self._chunks_by_id: dict[str, dict[str, Any]] = {}
        self._bm25: Any = None
        self._corpus_tokens: list[list[str]] = []
        if manifest_path.exists():
            self._load(manifest_path)

    def _load(self, manifest_path: Path) -> None:
        from rank_bm25 import BM25Okapi

        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in payload:
            if not isinstance(item, dict):
                continue
            chunk_id = str(item.get("chunk_id") or "")
            text = str(item.get("text") or "").strip()
            if not chunk_id or len(text) < 40:
                continue
            chunk = {
                "chunk_id": chunk_id,
                "condition": str(item.get("condition") or item.get("document") or ""),
                "chapter": str(item.get("chapter") or ""),
                "section_type": str(item.get("section_type") or "general"),
                "page_start": item.get("page_start"),
                "page_end": item.get("page_end"),
                "text": text,
                "corpus": str(item.get("corpus") or ""),
                "source_file": str(item.get("source_file") or ""),
                "document": str(item.get("document") or item.get("condition") or ""),
            }
            self._chunk_ids.append(chunk_id)
            self._chunks_by_id[chunk_id] = chunk
            self._corpus_tokens.append(tokenize(text))

        if self._corpus_tokens:
            self._bm25 = BM25Okapi(self._corpus_tokens)

    @property
    def is_ready(self) -> bool:
        return self._bm25 is not None and bool(self._chunk_ids)

    def search(self, query: str, top_k: int = 30) -> list[dict[str, Any]]:
        if not self.is_ready:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(
            enumerate(scores),
            key=lambda pair: pair[1],
            reverse=True,
        )[:top_k]
        results: list[dict[str, Any]] = []
        for index, score in ranked:
            chunk_id = self._chunk_ids[index]
            item = dict(self._chunks_by_id[chunk_id])
            item["source"] = "bm25"
            item["bm25_score"] = float(score)
            results.append(item)
        return results


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict[str, Any]]],
    *,
    k: int = RRF_K,
) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    chunks: dict[str, dict[str, Any]] = {}
    sources: dict[str, set[str]] = {}

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            chunk_id = str(chunk.get("chunk_id") or "")
            if not chunk_id:
                continue
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            if chunk_id not in chunks:
                chunks[chunk_id] = dict(chunk)
            source = str(chunk.get("source") or "unknown")
            sources.setdefault(chunk_id, set()).add(source)

    merged: list[dict[str, Any]] = []
    for chunk_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        item = dict(chunks[chunk_id])
        item["rrf_score"] = score
        item["retrieval_sources"] = sorted(sources.get(chunk_id, set()))
        merged.append(item)
    return merged


def _get_reranker() -> Any:
    global _reranker
    if _reranker is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        _reranker = TextCrossEncoder(model_name=DEFAULT_RERANK_MODEL)
    return _reranker


def rerank_chunks(
    query: str,
    chunks: list[dict[str, Any]],
    *,
    top_k: int = DEFAULT_RERANK_TOP_K,
) -> list[dict[str, Any]]:
    if not chunks:
        return []
    if len(chunks) <= top_k:
        return [dict(chunk) for chunk in chunks]

    try:
        reranker = _get_reranker()
    except Exception:
        return [dict(chunk) for chunk in chunks[:top_k]]

    documents = [str(chunk.get("text") or "") for chunk in chunks]
    try:
        scores = list(reranker.rerank(query, documents))
    except Exception:
        return [dict(chunk) for chunk in chunks[:top_k]]

    ranked = sorted(
        zip(chunks, scores, strict=False),
        key=lambda pair: pair[1],
        reverse=True,
    )[:top_k]
    results: list[dict[str, Any]] = []
    for chunk, score in ranked:
        item = dict(chunk)
        item["rerank_score"] = float(score)
        results.append(item)
    return results


def prefilter_titles_by_embedding(
    query: str,
    titles: list[str],
    *,
    top_k: int = 50,
    embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
) -> list[str]:
    if not titles:
        return []
    if len(titles) <= top_k:
        return list(titles)

    if embed_fn is None:
        from fastembed import TextEmbedding

        embedder = TextEmbedding(model_name=DEFAULT_EMBED_MODEL)
        embed_fn = lambda texts: [  # noqa: E731
            [float(v) for v in vector] for vector in embedder.embed(texts)
        ]

    vectors = embed_fn([query] + titles)
    query_vec = vectors[0]
    title_vecs = vectors[1:]

    def dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=False))

    def norm(v: list[float]) -> float:
        return sum(x * x for x in v) ** 0.5 or 1.0

    query_norm = norm(query_vec)
    scored = [
        (title, dot(query_vec, vec) / (query_norm * norm(vec)))
        for title, vec in zip(titles, title_vecs, strict=False)
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [title for title, _ in scored[:top_k]]


def build_context_text(
    chunks: list[dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> str:
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
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n\n---\n\n".join(parts)


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _chunk_reference_keys(chunk: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for field in ("condition", "document", "chapter"):
        label = _normalize_label(str(chunk.get(field) or ""))
        if label:
            keys.add(label)
    return keys


def _reference_matches_chunk(reference: dict[str, Any], chunk: dict[str, Any]) -> bool:
    ref_condition = _normalize_label(str(reference.get("condition") or ""))
    ref_section = _normalize_label(str(reference.get("section") or ""))
    ref_page = reference.get("page")

    chunk_keys = _chunk_reference_keys(chunk)
    if ref_condition and not any(
        ref_condition in key or key in ref_condition for key in chunk_keys
    ):
        return False

    chunk_section = _normalize_label(str(chunk.get("section_type") or ""))
    if ref_section and chunk_section and ref_section not in chunk_section:
        if chunk_section not in ref_section:
            return False

    if ref_page is not None:
        try:
            page = int(ref_page)
        except (TypeError, ValueError):
            page = None
        if page is not None:
            start = chunk.get("page_start")
            end = chunk.get("page_end")
            if start is not None and end is not None:
                if not (int(start) <= page <= int(end)):
                    return False
    return True


def _score_chunk_relevance(flag: dict[str, Any], chunk: dict[str, Any]) -> float:
    item = _normalize_label(str(flag.get("item") or ""))
    reason = _normalize_label(str(flag.get("reason") or ""))
    text = _normalize_label(str(chunk.get("text") or ""))
    score = 0.0
    for token in item.split():
        if len(token) > 3 and token in text:
            score += 2.0
    for token in reason.split():
        if len(token) > 4 and token in text:
            score += 0.5
    section = _normalize_label(str(chunk.get("section_type") or ""))
    if section in {"treatment", "diagnosis", "investigations", "general"}:
        score += 0.3
    return score


def _find_supporting_chunk(
    flag: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not chunks:
        return None
    scored = sorted(
        ((chunk, _score_chunk_relevance(flag, chunk)) for chunk in chunks),
        key=lambda pair: pair[1],
        reverse=True,
    )
    best_chunk, best_score = scored[0]
    if best_score >= 1.0:
        return best_chunk
    return chunks[0]


_OCR_GLYPH_PATTERN = re.compile(
    r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f"
    r"\uf000-\uf0ff\u25a0-\u25ff\u2580-\u259f]+"
)
_SECTION_NUMBER_PATTERN = re.compile(
    r"\b\d+(?:\.\d+){1,3}\b|\bCHAPTER\s*:?\s*\d+\b",
    re.IGNORECASE,
)


def sanitize_display_text(text: str) -> str:
    """Strip OCR artifacts and control characters from user-facing audit text."""
    cleaned = str(text or "")
    cleaned = _OCR_GLYPH_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _friendly_source_name(corpus_label: str) -> str:
    label = str(corpus_label or "").strip().lower()
    if not label or label in {"government guidelines", "guidelines"}:
        return "government treatment guidelines"
    if label == "icmr":
        return "ICMR guidelines"
    if label == "crc stg":
        return "CRC Standard Treatment Guidelines"
    if "clinical establishments" in label:
        return "Clinical Establishments Act guidelines"
    if "icmr" in label:
        return "ICMR guidelines"
    return str(corpus_label or "government treatment guidelines").strip()


def _friendly_condition_name(condition: str) -> str:
    name = sanitize_display_text(condition)
    name = _SECTION_NUMBER_PATTERN.sub("", name)
    name = re.sub(r"\s+", " ", name).strip(" .,-")
    return name


def format_guideline_basis(chunk: dict[str, Any], *, excerpt_max: int = 220) -> str:
    """Return a short source attribution label (no raw OCR excerpt)."""
    del excerpt_max  # kept for backward compatibility with callers
    source = _friendly_source_name(
        str(chunk.get("corpus_label") or chunk.get("chapter") or "").strip()
    )
    condition = _friendly_condition_name(
        str(chunk.get("condition") or chunk.get("document") or "")
    )
    if condition:
        return f"Based on {source} for {condition}."
    return f"Based on {source}."


def _strip_citation_verification_suffix(reason: str) -> str:
    cleaned = re.sub(
        r"\s*\(STG citation could not be verified[^)]*\)\.?",
        "",
        reason,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def validate_stg_citations(
    flags: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        item = dict(flag)
        reference = item.get("stg_reference")
        matched_chunk: dict[str, Any] | None = None

        if reference and isinstance(reference, dict):
            for chunk in chunks:
                if _reference_matches_chunk(reference, chunk):
                    matched_chunk = chunk
                    break

            if not matched_chunk:
                item["stg_reference"] = None
                item["reason"] = _strip_citation_verification_suffix(
                    str(item.get("reason") or "")
                )

        existing_basis = sanitize_display_text(str(item.get("guideline_basis") or ""))
        if existing_basis:
            item["guideline_basis"] = existing_basis
        elif matched_chunk:
            item["guideline_basis"] = format_guideline_basis(matched_chunk)
        else:
            support = _find_supporting_chunk(item, chunks)
            if support:
                item["guideline_basis"] = format_guideline_basis(support)

        item["reason"] = sanitize_display_text(str(item.get("reason") or ""))
        item["recommendation"] = sanitize_display_text(str(item.get("recommendation") or ""))

        validated.append(item)
    return validated
