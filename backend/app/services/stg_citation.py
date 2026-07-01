"""Structured STG citation payloads for flags and PDF export."""

from __future__ import annotations

import re
from typing import Any

from app.services.rag_pipeline import format_guideline_basis, sanitize_display_text

_SOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    "icmr": {
        "corpus_key": "icmr",
        "corpus_label": "ICMR",
        "display_name": "ICMR Standard Treatment Guidelines",
        "authority": "Indian Council of Medical Research (ICMR)",
        "folder_hint": "backend/data/Standard Treatment Guidelines/ICMR/",
        "credibility_note": (
            "National medical-research body guidelines used in Indian clinical "
            "protocols, hospital audits, and expert medical opinions."
        ),
        "legal_use_examples": [
            "Expert witnesses and hospital grievance panels often cite ICMR-aligned "
            "protocols when explaining whether a test or medicine was indicated.",
            "Consumer forums may treat published government or ICMR-aligned "
            "guidelines as reference standards; outcomes depend on facts and evidence.",
        ],
    },
    "clinical_establishments": {
        "corpus_key": "clinical_establishments",
        "corpus_label": "Clinical Establishments Act STG",
        "display_name": (
            "Standard Treatment Guidelines under the Clinical Establishments Act"
        ),
        "authority": (
            "Ministry of Health and Family Welfare (MoHFW), Government of India"
        ),
        "folder_hint": (
            "backend/data/Standard Treatment Guidelines/"
            "Clinical Estabilishments Act STG/"
        ),
        "credibility_note": (
            "MoHFW-issued STGs for registered clinical establishments; used as "
            "minimum standard-of-care references in regulatory and quality reviews."
        ),
        "legal_use_examples": [
            "State health authorities may refer to Clinical Establishments Act "
            "STGs when reviewing complaints about investigations or treatment paths.",
            "Patients may attach MoHFW STG excerpts when asking a hospital to "
            "justify departures from published establishment standards.",
        ],
    },
    "crc_stg": {
        "corpus_key": "crc_stg",
        "corpus_label": "CRC STG",
        "display_name": "CRC Standard Treatment Guidelines (reference book)",
        "authority": "Committee for Rational Use of Drugs (CRC) — reference textbook",
        "folder_hint": "CRC Standard Treatment Guidelines index (fallback corpus)",
        "credibility_note": (
            "Widely used Indian treatment reference text. It is not a statute, but "
            "courts and consumer forums have referred to standard treatment texts "
            "when assessing whether care departed from accepted practice."
        ),
        "legal_use_examples": [
            "Consumer dispute commissions have considered standard treatment "
            "references alongside expert testimony in medical service cases.",
            "Advocates sometimes use CRC STG excerpts to frame questions about "
            "indicated investigations or medicines; final findings require proof.",
        ],
    },
}


def _normalize_corpus_key(chunk: dict[str, Any]) -> str:
    corpus = str(chunk.get("corpus") or "").strip().lower()
    label = str(chunk.get("corpus_label") or chunk.get("chapter") or "").strip().lower()
    if corpus == "icmr" or "icmr" in label:
        return "icmr"
    if corpus == "clinical_establishments" or "clinical establishments" in label:
        return "clinical_establishments"
    if corpus == "crc" or "crc stg" in label or label == "crc stg":
        return "crc_stg"
    if "clinical establishments" in str(chunk.get("source_file") or "").lower():
        return "clinical_establishments"
    if "/icmr/" in str(chunk.get("source_file") or "").lower():
        return "icmr"
    return "crc_stg"


def resolve_source_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    key = _normalize_corpus_key(chunk)
    meta = dict(_SOURCE_REGISTRY.get(key, _SOURCE_REGISTRY["crc_stg"]))
    source_file = str(chunk.get("source_file") or "").strip()
    if source_file:
        meta = {**meta, "source_file": source_file}
    document = sanitize_display_text(
        str(chunk.get("document") or chunk.get("condition") or "")
    )
    if document:
        meta = {**meta, "document_title": document}
    return meta


def _format_page_reference(chunk: dict[str, Any]) -> str | None:
    start = chunk.get("page_start")
    end = chunk.get("page_end")
    if start is None and end is None:
        return None
    try:
        if start is not None and end is not None and int(start) != int(end):
            return f"pp. {int(start)}–{int(end)}"
        page = start if start is not None else end
        return f"p. {int(page)}"
    except (TypeError, ValueError):
        return None


def build_stg_citation_from_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """Build a patient-facing citation block from a retrieved guideline chunk."""
    text = sanitize_display_text(str(chunk.get("text") or ""))
    text = re.sub(r"\s+", " ", text).strip()
    source = resolve_source_metadata(chunk)
    section = sanitize_display_text(str(chunk.get("section_type") or ""))
    condition = sanitize_display_text(
        str(chunk.get("condition") or chunk.get("document") or "")
    )
    page_ref = _format_page_reference(chunk)
    reference = {
        "condition": condition or None,
        "section": section or None,
        "page": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "page_label": page_ref,
    }
    return {
        "full_text": text,
        "summary": format_guideline_basis(chunk),
        "source": source,
        "reference": reference,
        "chunk_id": str(chunk.get("chunk_id") or "") or None,
        "citation_verified": True,
    }


def attach_stg_citations_to_flags(
    flags: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ensure each flag carries ``stg_citation`` when a chunk can be matched."""
    from app.services.rag_pipeline import (
        _find_supporting_chunk,
        _reference_matches_chunk,
        validate_stg_citations,
    )

    validated = validate_stg_citations(flags, chunks)
    enriched: list[dict[str, Any]] = []
    for flag in validated:
        item = dict(flag)
        matched: dict[str, Any] | None = None
        reference = item.get("stg_reference")
        if isinstance(reference, dict):
            for chunk in chunks:
                if _reference_matches_chunk(reference, chunk):
                    matched = chunk
                    break
        if matched is None and item.get("citation_verified"):
            matched = _find_supporting_chunk(item, chunks)
        if matched and str(matched.get("text") or "").strip():
            item["stg_citation"] = build_stg_citation_from_chunk(matched)
        enriched.append(item)
    return enriched
