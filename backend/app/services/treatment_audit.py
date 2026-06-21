"""STG-grounded treatment appropriateness audit."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from fastapi import HTTPException
from groq import Groq

from app.services.document_extraction import extract_json_from_text
from app.services.stg_retrieval import retrieve_stg_context

GROQ_MODEL = "llama-3.3-70b-versatile"

FILLER_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "for",
    "in",
    "of",
    "or",
    "the",
    "to",
    "with",
}


def _normalize_name(text: str) -> str:
    lowered = text.lower()
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    tokens = [token for token in cleaned.split() if token and token not in FILLER_WORDS]
    return " ".join(tokens)


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _collect_item_names(items: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(
            item.get("item_name")
            or item.get("name")
            or item.get("description")
            or ""
        ).strip()
        if name:
            names.append(name)
    return names


def _rule_based_bill_prescription_flags(
    bill_items: list[dict[str, Any]],
    prescription_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bill_names = _collect_item_names(bill_items)
    prescription_names = _collect_item_names(prescription_items)
    if not bill_names or not prescription_names:
        return []

    rx_norms = {_normalize_name(name): name for name in prescription_names}
    flags: list[dict[str, Any]] = []
    for bill_name in bill_names:
        bill_norm = _normalize_name(bill_name)
        if not bill_norm:
            continue
        if bill_norm in rx_norms:
            continue
        best_score = max(
            (_similarity(bill_norm, rx_norm) for rx_norm in rx_norms),
            default=0.0,
        )
        if best_score >= 0.85:
            continue
        flags.append(
            {
                "type": "BILLED_NOT_PRESCRIBED",
                "severity": "HIGH",
                "item": bill_name,
                "reason": (
                    f'"{bill_name}" appears on the bill but was not found on the '
                    "uploaded prescription."
                ),
                "recommendation": (
                    "Ask the hospital to explain why this charge was added without "
                    "a corresponding prescription order."
                ),
                "stg_reference": None,
            }
        )
    return flags


def _compute_risk_level(flags: list[dict[str, Any]]) -> str:
    if not flags:
        return "LOW"
    if any(flag.get("severity") == "HIGH" for flag in flags) or len(flags) >= 3:
        return "HIGH"
    return "MEDIUM"


def _groq_audit(
    *,
    diagnosis: str,
    prescription_items: list[str],
    bill_items: list[str],
    context_text: str,
    matched_conditions: list[str],
) -> list[dict[str, Any]]:
    api_key = __import__("os").getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not set in the environment.",
        )

    prompt = f"""
You are reviewing medical orders against India's Standard Treatment Guidelines (STG).

Return ONLY valid JSON:
{{
  "flags": [
    {{
      "type": "UNNECESSARY_TEST|UNNECESSARY_PROCEDURE|NOT_INDICATED_MEDICINE|EXCESSIVE_WORKUP|PRESCRIBED_NOT_IN_STG|INSUFFICIENT_STG_EVIDENCE",
      "severity": "MEDIUM|HIGH",
      "item": "string",
      "reason": "string",
      "recommendation": "string",
      "stg_reference": {{
        "condition": "string",
        "section": "string",
        "page": number or null
      }}
    }}
  ]
}}

Rules:
- Only flag items that are NOT supported by the STG excerpts below.
- Every flag MUST include stg_reference citing the excerpt used.
- If STG excerpts do not mention an item and do not clearly exclude it, do NOT flag it.
- Use INSUFFICIENT_STG_EVIDENCE only when you cannot determine appropriateness.
- Compare prescribed items and billed items (if provided) against STG for diagnosis: {diagnosis}
- matched STG conditions: {json.dumps(matched_conditions)}

Prescribed / ordered items:
{json.dumps(prescription_items, ensure_ascii=False)}

Billed items (optional):
{json.dumps(bill_items, ensure_ascii=False)}

STG excerpts:
{context_text}
"""
    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Groq API request failed: {str(exc)}",
        ) from exc

    text = (response.choices[0].message.content or "").strip()
    if not text:
        return []
    parsed = extract_json_from_text(text)
    flags = parsed.get("flags") or []
    return flags if isinstance(flags, list) else []


def analyze_treatment(
    *,
    diagnosis: str,
    prescription_items: list[dict[str, Any]] | None = None,
    bill_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    diagnosis = str(diagnosis or "").strip()
    if not diagnosis:
        raise HTTPException(status_code=400, detail="Diagnosis is required.")

    prescription_items = prescription_items or []
    bill_items = bill_items or []

    rx_names = _collect_item_names(prescription_items)
    bill_names = _collect_item_names(bill_items)
    all_items = list(dict.fromkeys(rx_names + bill_names))

    retrieval = retrieve_stg_context(diagnosis, all_items)
    matched_conditions = retrieval.get("matched_conditions") or []
    context_text = retrieval.get("context_text") or ""

    flags: list[dict[str, Any]] = []
    flags.extend(_rule_based_bill_prescription_flags(bill_items, prescription_items))

    if context_text:
        llm_flags = _groq_audit(
            diagnosis=diagnosis,
            prescription_items=rx_names,
            bill_items=bill_names,
            context_text=context_text,
            matched_conditions=matched_conditions,
        )
        for flag in llm_flags:
            if not isinstance(flag, dict):
                continue
            if flag.get("type") == "INSUFFICIENT_STG_EVIDENCE":
                continue
            flags.append(flag)
    elif not matched_conditions:
        flags.append(
            {
                "type": "INSUFFICIENT_STG_EVIDENCE",
                "severity": "MEDIUM",
                "item": diagnosis,
                "reason": (
                    f"Could not map diagnosis '{diagnosis}' to a condition in the "
                    "Standard Treatment Guidelines index."
                ),
                "recommendation": (
                    "Confirm the diagnosis spelling or choose a closer condition name."
                ),
                "stg_reference": None,
            }
        )

    return {
        "flags_count": len(flags),
        "risk_level": _compute_risk_level(flags),
        "matched_stg_conditions": matched_conditions,
        "flags": flags,
    }
