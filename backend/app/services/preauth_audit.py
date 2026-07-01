"""Factual comparison between pre-authorization approvals and bill items."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.services.legal_guardrails import sanitize_text


def _normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _to_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left in right or right in left:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _approved_items(preauth_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for document in preauth_documents or []:
        for item in document.get("approved_items") or []:
            name = str(item.get("name") or "").strip()
            if name:
                items.append(
                    {
                        "name": name,
                        "norm": _normalize(name),
                        "approved_amount": item.get("approved_amount"),
                        "source": document.get("filename") or "pre-authorization",
                    }
                )
    return items


def _approved_cap(preauth_documents: list[dict[str, Any]]) -> float:
    caps = [_to_float(document.get("approved_amount")) for document in preauth_documents or []]
    return max(caps, default=0.0)


def analyze_preauth_mismatches(
    *,
    line_items: list[dict[str, Any]],
    preauth_documents: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    documents = [doc for doc in (preauth_documents or []) if isinstance(doc, dict)]
    if not documents:
        return {"flags": [], "patient_questions": []}

    approved = _approved_items(documents)
    approved_cap = _approved_cap(documents)
    bill_total = sum(_to_float(item.get("total_price")) for item in line_items)
    flags: list[dict[str, Any]] = []

    if approved_cap > 0 and bill_total > approved_cap:
        flags.append(
            {
                "type": "PREAUTH_AMOUNT_ABOVE_APPROVED",
                "severity": "MEDIUM",
                "confidence": "MEDIUM",
                "category": "billing",
                "item": "Final bill total",
                "display_label": "Bill above pre-authorization amount",
                "reason": sanitize_text(
                    f"The bill total is INR {bill_total:,.2f}, while the uploaded "
                    f"pre-authorization approval mentions INR {approved_cap:,.2f}."
                ),
                "recommendation": (
                    "Ask the hospital or insurer to explain whether the extra amount "
                    "is covered, excluded, or needs additional approval."
                ),
            }
        )

    if approved:
        for line in line_items:
            name = str(line.get("item_name") or line.get("name") or "").strip()
            norm = _normalize(name)
            if not norm:
                continue
            best = max((_similarity(norm, item["norm"]) for item in approved), default=0.0)
            if best >= 0.72:
                continue
            flags.append(
                {
                    "type": "PREAUTH_ITEM_OUTSIDE_AUTHORIZATION",
                    "severity": "LOW",
                    "confidence": "MEDIUM",
                    "category": "billing",
                    "item": name,
                    "display_label": "Item not clearly listed in pre-authorization",
                    "reason": sanitize_text(
                        f"{name} was billed but was not clearly matched to the uploaded "
                        "pre-authorization approval."
                    ),
                    "recommendation": (
                        "Ask whether this item is included in the approval, excluded by "
                        "policy, or requires separate authorization."
                    ),
                }
            )
            if len(flags) >= 6:
                break

    questions = [
        {
            "question": sanitize_text(flag["recommendation"]),
            "item": flag.get("item"),
            "flag_type": flag.get("type"),
            "confidence": flag.get("confidence"),
        }
        for flag in flags
    ]
    return {"flags": flags, "patient_questions": questions}
