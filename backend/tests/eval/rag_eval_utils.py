"""Shared utilities for RAG retrieval and audit evaluation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_GOLD_PATH = EVAL_DIR / "gold_cases.jsonl"
RESULTS_DIR = EVAL_DIR / "results"


def load_gold_cases(path: Path | None = None) -> list[dict[str, Any]]:
    gold_path = path or DEFAULT_GOLD_PATH
    cases: list[dict[str, Any]] = []
    for line in gold_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    return cases


def filter_cases(
    cases: list[dict[str, Any]],
    *,
    source: str | None = None,
    rule_based_only: bool | None = None,
    case_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    filtered = cases
    if source:
        filtered = [case for case in filtered if case.get("source") == source]
    if rule_based_only is not None:
        filtered = [
            case
            for case in filtered
            if bool((case.get("audit_gold") or {}).get("rule_based_only")) is rule_based_only
        ]
    if case_ids:
        wanted = set(case_ids)
        filtered = [case for case in filtered if case.get("id") in wanted]
    return filtered


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _chunk_document_labels(chunk: dict[str, Any]) -> list[str]:
    labels = [
        str(chunk.get("condition") or ""),
        str(chunk.get("document") or ""),
    ]
    return [_normalize_label(label) for label in labels if label.strip()]


def document_hit_at_k(
    chunks: list[dict[str, Any]],
    expected_documents: list[str],
    k: int = 5,
) -> tuple[bool, float | None]:
    if not expected_documents:
        return True, None

    expected = [_normalize_label(doc) for doc in expected_documents]
    top_chunks = chunks[:k]
    for rank, chunk in enumerate(top_chunks, start=1):
        labels = _chunk_document_labels(chunk)
        for label in labels:
            for target in expected:
                if target in label or label in target:
                    return True, 1.0 / rank
    return False, 0.0


def corpus_hit(
    guideline_sources: list[str],
    expected_corpora: list[str],
) -> bool:
    if not expected_corpora:
        return True

    source_map = {
        "icmr": "icmr",
        "clinical_establishments": "clinical establishments",
        "crc_stg": "crc stg",
    }
    normalized_sources = {_normalize_label(source) for source in guideline_sources}
    for corpus in expected_corpora:
        needle = source_map.get(corpus, corpus.replace("_", " "))
        if not any(needle in source for source in normalized_sources):
            return False
    return True


def term_recall(context_text: str, must_contain_terms: list[str]) -> float:
    if not must_contain_terms:
        return 1.0
    lowered = context_text.lower()
    hits = sum(1 for term in must_contain_terms if term.lower() in lowered)
    return hits / len(must_contain_terms)


def fallback_correct(used_fallback: bool, should_use_fallback: bool | None) -> bool:
    if should_use_fallback is None:
        return True
    return used_fallback == should_use_fallback


def case_input_to_retrieval_args(case: dict[str, Any]) -> tuple[str, list[str], list[Any], list[dict]]:
    payload = case.get("input") or {}
    diagnosis = str(payload.get("diagnosis") or "").strip()
    medicines = [str(item.get("name", "")).strip() for item in payload.get("medicines") or []]
    tests = [str(item.get("name", "")).strip() for item in payload.get("tests") or []]
    procedures = [str(item.get("name", "")).strip() for item in payload.get("procedures") or []]
    items = [name for name in medicines + tests + procedures if name]
    symptoms = payload.get("symptoms") or []
    test_results = payload.get("test_results") or []
    return diagnosis, items, symptoms, test_results


def case_input_to_audit_kwargs(case: dict[str, Any]) -> dict[str, Any]:
    payload = case.get("input") or {}
    diagnosis = str(payload.get("diagnosis") or "").strip()

    prescription_items: list[dict[str, str]] = []
    for item in payload.get("medicines") or []:
        name = str(item.get("name", "")).strip()
        if name:
            prescription_items.append({"name": name, "category": "medicine"})
    for item in payload.get("tests") or []:
        name = str(item.get("name", "")).strip()
        if name:
            prescription_items.append({"name": name, "category": "test"})
    for item in payload.get("procedures") or []:
        name = str(item.get("name", "")).strip()
        if name:
            prescription_items.append({"name": name, "category": "procedure"})

    bill_items = [
        {
            "item_name": str(item.get("item_name") or item.get("name") or "").strip(),
            "category": item.get("category") or "other",
        }
        for item in payload.get("bill_items") or []
        if str(item.get("item_name") or item.get("name") or "").strip()
    ]

    clinical_context = {
        "symptoms": payload.get("symptoms") or [],
        "test_results": payload.get("test_results") or [],
    }

    return {
        "diagnosis": diagnosis,
        "prescription_items": prescription_items,
        "bill_items": bill_items,
        "clinical_context": clinical_context,
        "diagnosis_user_provided": bool(payload.get("diagnosis_user_provided")),
    }


def flag_types_from_audit(result: dict[str, Any]) -> list[str]:
    flags = result.get("flags") or []
    return [str(flag.get("type") or "") for flag in flags if flag.get("type")]


def audit_matches_gold(actual: dict[str, Any], audit_gold: dict[str, Any]) -> dict[str, Any]:
    actual_types = set(flag_types_from_audit(actual))
    expected_types = set(audit_gold.get("expected_flag_types") or [])
    forbidden_types = set(audit_gold.get("forbidden_flag_types") or [])

    expected_hits = expected_types & actual_types
    expected_misses = expected_types - actual_types
    forbidden_hits = forbidden_types & actual_types

    precision = (
        len(expected_hits) / len(actual_types) if actual_types and expected_types else None
    )
    recall = (
        len(expected_hits) / len(expected_types) if expected_types else None
    )

    alignment = actual.get("clinical_alignment") or {}
    gold_alignment = audit_gold.get("diagnosis_supported")
    alignment_match = (
        alignment.get("diagnosis_supported") == gold_alignment
        if gold_alignment is not None
        else True
    )

    min_flags = int(audit_gold.get("min_flags") or 0)
    min_flags_ok = len(actual_types) >= min_flags

    require_ref = bool(audit_gold.get("require_stg_reference"))
    flags = actual.get("flags") or []
    citation_ok = True
    if require_ref and flags:
        citation_ok = all(
            isinstance(flag.get("stg_reference"), dict)
            and bool((flag.get("stg_reference") or {}).get("condition"))
            for flag in flags
            if flag.get("type") in expected_types
        )

    passed = (
        not expected_misses
        and not forbidden_hits
        and alignment_match
        and min_flags_ok
        and citation_ok
    )

    return {
        "passed": passed,
        "expected_hits": sorted(expected_hits),
        "expected_misses": sorted(expected_misses),
        "forbidden_hits": sorted(forbidden_hits),
        "precision": precision,
        "recall": recall,
        "alignment_match": alignment_match,
        "min_flags_ok": min_flags_ok,
        "citation_ok": citation_ok,
        "actual_flag_types": sorted(actual_types),
    }


@dataclass
class RetrievalCaseResult:
    case_id: str
    source: str
    passed: bool
    document_hit_at_5: bool
    mrr: float | None
    corpus_hit: bool
    term_recall: float
    fallback_correct: bool
    used_fallback: bool
    guideline_sources: list[str] = field(default_factory=list)
    primary_chunk_count: int = 0
    fallback_chunk_count: int = 0
    top_chunks: list[dict[str, str]] = field(default_factory=list)
    notes: str = ""


def score_retrieval_case(case: dict[str, Any], retrieval: dict[str, Any]) -> RetrievalCaseResult:
    gold = case.get("retrieval_gold") or {}
    chunks = retrieval.get("chunks") or []
    context_text = retrieval.get("context_text") or ""

    hit, mrr = document_hit_at_k(chunks, gold.get("expected_documents") or [], k=5)
    corp = corpus_hit(retrieval.get("guideline_sources") or [], gold.get("expected_corpora") or [])
    terms = term_recall(context_text, gold.get("must_contain_terms") or [])
    fb = fallback_correct(
        bool(retrieval.get("used_fallback")),
        gold.get("should_use_fallback"),
    )

    passed = hit and corp and terms >= 0.5 and fb

    top_chunks = []
    for chunk in chunks[:3]:
        top_chunks.append(
            {
                "label": f"{chunk.get('corpus_label', '')} | {chunk.get('condition', '')}",
                "preview": str(chunk.get("text") or "")[:200],
            }
        )

    return RetrievalCaseResult(
        case_id=str(case.get("id") or ""),
        source=str(case.get("source") or ""),
        passed=passed,
        document_hit_at_5=hit,
        mrr=mrr,
        corpus_hit=corp,
        term_recall=terms,
        fallback_correct=fb,
        used_fallback=bool(retrieval.get("used_fallback")),
        guideline_sources=list(retrieval.get("guideline_sources") or []),
        primary_chunk_count=int(retrieval.get("primary_chunk_count") or 0),
        fallback_chunk_count=int(retrieval.get("fallback_chunk_count") or 0),
        top_chunks=top_chunks,
        notes=str(case.get("notes") or ""),
    )


def aggregate_retrieval_results(results: list[RetrievalCaseResult]) -> dict[str, Any]:
    total = len(results)
    if not total:
        return {"total": 0}

    mrr_values = [result.mrr for result in results if result.mrr is not None]
    return {
        "total": total,
        "passed": sum(1 for result in results if result.passed),
        "document_hit_at_5": sum(1 for result in results if result.document_hit_at_5) / total,
        "corpus_hit_rate": sum(1 for result in results if result.corpus_hit) / total,
        "mean_term_recall": sum(result.term_recall for result in results) / total,
        "fallback_accuracy": sum(1 for result in results if result.fallback_correct) / total,
        "mean_mrr": sum(mrr_values) / len(mrr_values) if mrr_values else None,
    }


def write_html_report(title: str, summary: dict[str, Any], rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row_html = []
    for row in rows:
        cells = "".join(f"<td>{row.get(key, '')}</td>" for key in row.keys())
        row_html.append(f"<tr>{cells}</tr>")

    headers = "".join(f"<th>{key}</th>" for key in (rows[0].keys() if rows else []))
    summary_lines = "".join(
        f"<li><strong>{key}</strong>: {value}</li>" for key, value in summary.items()
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; color: #1e293b; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ border: 1px solid #cbd5e1; padding: 0.5rem; text-align: left; vertical-align: top; }}
th {{ background: #f1f5f9; }}
.pass {{ color: #166534; font-weight: 600; }}
.fail {{ color: #b91c1c; font-weight: 600; }}
</style></head><body>
<h1>{title}</h1>
<ul>{summary_lines}</ul>
<table><thead><tr>{headers}</tr></thead><tbody>{''.join(row_html)}</tbody></table>
</body></html>"""
    path.write_text(html, encoding="utf-8")


def write_csv_report(rows: list[dict[str, Any]], path: Path) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
