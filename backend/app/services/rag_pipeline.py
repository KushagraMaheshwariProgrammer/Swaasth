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
        if not reference or not isinstance(reference, dict):
            validated.append(item)
            continue

        grounded = any(_reference_matches_chunk(reference, chunk) for chunk in chunks)
        if grounded:
            validated.append(item)
            continue

        reason = str(item.get("reason") or "").strip()
        suffix = " (STG citation could not be verified against retrieved excerpts.)"
        if suffix.strip() not in reason:
            item["reason"] = f"{reason}{suffix}".strip()
        item["stg_reference"] = None
        validated.append(item)
    return validated
