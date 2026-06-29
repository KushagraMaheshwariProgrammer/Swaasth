"""Investigation rationality checks against guideline retrieval chunks."""

from __future__ import annotations

import re
from typing import Any

from app.services.rag_pipeline import _find_supporting_chunk, format_guideline_basis

INVESTIGATION_SECTIONS = frozenset(
    {
        "diagnosis",
        "diagnostic tests",
        "investigations",
        "indications",
    }
)

ADVANCED_IMAGING_MARKERS = (
    "mri",
    "ct scan",
    "ct chest",
    "ct brain",
    "pet",
    "pet-ct",
    "angiography",
)

NOT_ROUTINELY_PATTERNS = (
    re.compile(r"not\s+(?:routinely|usually|recommended|indicated|required)", re.I),
    re.compile(r"should\s+not\s+(?:be\s+)?(?:done|routine|performed)", re.I),
    re.compile(r"unnecessary", re.I),
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def _item_tokens(item_name: str) -> list[str]:
    tokens = [token for token in _normalize(item_name).split() if len(token) >= 3]
    return tokens


def _investigation_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered = [
        chunk
        for chunk in chunks
        if str(chunk.get("section_type") or "").lower() in INVESTIGATION_SECTIONS
    ]
    return filtered or list(chunks)


def _item_in_chunk_text(item_name: str, chunk: dict[str, Any]) -> bool:
    text = _normalize(str(chunk.get("text") or ""))
    if not text:
        return False
    item_norm = _normalize(item_name)
    if item_norm and item_norm in text:
        return True
    return any(token in text for token in _item_tokens(item_name))


def _chunk_suggests_not_routine(item_name: str, chunk: dict[str, Any]) -> bool:
    text = str(chunk.get("text") or "")
    if not _item_in_chunk_text(item_name, chunk):
        return False
    for pattern in NOT_ROUTINELY_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _is_advanced_imaging(item_name: str) -> bool:
    normalized = _normalize(item_name)
    return any(marker in normalized for marker in ADVANCED_IMAGING_MARKERS)


def analyze_investigations(
    *,
    diagnosis: str,
    investigation_items: list[str],
    retrieval_chunks: list[dict[str, Any]],
    flagged_item_norms: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not diagnosis or not investigation_items:
        return []

    flagged_item_norms = flagged_item_norms or set()
    inv_chunks = _investigation_chunks(retrieval_chunks)
    flags: list[dict[str, Any]] = []

    for item_name in investigation_items:
        item_norm = _normalize(item_name)
        if not item_norm or item_norm in flagged_item_norms:
            continue

        supporting = None
        not_routine_chunk = None
        for chunk in inv_chunks:
            if _chunk_suggests_not_routine(item_name, chunk):
                not_routine_chunk = chunk
                break
            if _item_in_chunk_text(item_name, chunk):
                supporting = chunk

        if not_routine_chunk:
            flags.append(
                {
                    "type": "INVESTIGATION_NOT_ROUTINELY_RECOMMENDED",
                    "severity": "MEDIUM",
                    "item": item_name,
                    "category": "investigation",
                    "reason": (
                        f"For {diagnosis}, {item_name} is not routinely recommended "
                        "under the retrieved government guideline excerpts."
                    ),
                    "recommendation": (
                        f"Ask your doctor why {item_name} was ordered and whether a "
                        "simpler test would have been sufficient."
                    ),
                    "guideline_basis": format_guideline_basis(not_routine_chunk),
                    "stg_reference": {
                        "condition": not_routine_chunk.get("condition")
                        or not_routine_chunk.get("document"),
                        "section": not_routine_chunk.get("section_type"),
                        "page": not_routine_chunk.get("page_start"),
                    },
                    "citation_verified": True,
                }
            )
            flagged_item_norms.add(item_norm)
            continue

        if supporting:
            continue

        if _is_advanced_imaging(item_name):
            flags.append(
                {
                    "type": "GUIDELINE_SUPPORT_NOT_IDENTIFIED",
                    "severity": "MEDIUM",
                    "item": item_name,
                    "category": "investigation",
                    "reason": (
                        f"Guideline support for {item_name} in this clinical scenario "
                        f"({diagnosis}) was not identified in the retrieved excerpts."
                    ),
                    "recommendation": (
                        f"Ask the hospital or doctor to explain the clinical reason "
                        f"for ordering {item_name}."
                    ),
                    "guideline_basis": None,
                    "stg_reference": None,
                }
            )
            flagged_item_norms.add(item_norm)
            continue

        pseudo_flag = {"item": item_name, "category": "investigation"}
        weak_support = _find_supporting_chunk(pseudo_flag, inv_chunks)
        if retrieval_chunks and not weak_support:
            flags.append(
                {
                    "type": "GUIDELINE_SUPPORT_NOT_IDENTIFIED",
                    "severity": "MEDIUM",
                    "item": item_name,
                    "category": "investigation",
                    "reason": (
                        f"Guideline support for {item_name} in this clinical scenario "
                        f"({diagnosis}) was not identified."
                    ),
                    "recommendation": (
                        f"Can you explain why {item_name} was ordered for {diagnosis}?"
                    ),
                    "guideline_basis": None,
                    "stg_reference": None,
                }
            )
            flagged_item_norms.add(item_norm)

    return flags
