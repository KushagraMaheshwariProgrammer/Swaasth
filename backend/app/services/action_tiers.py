"""Action-tier assignment layered over existing audit confidence + flag type.

Tiers translate the existing HIGH/MEDIUM/LOW confidence and flag grounding into a
patient-facing "how strongly can I act on this" signal:

- ``A`` ("Ask now"): HIGH-confidence grounded clinical flags, or hard billing math
  (``DUPLICATE_ITEM``, ``PACKAGE_COMPONENT_CHARGED_SEPARATELY``,
  ``BILLED_NOT_PRESCRIBED``, or an overpriced line backed by an NPPA reference).
- ``B`` ("Verify then ask"): MEDIUM confidence, ``NEAR_DUPLICATE_ITEM``, or
  missing-clinical-data flags.
- ``C`` ("Document only"): LOW / ungrounded / ``INSUFFICIENT_*`` flags.

Tier D is never emitted; suppression is handled by the banned-term guardrails.
"""

from __future__ import annotations

from typing import Any

from app.services.audit_advocacy import (
    BILLING_HEURISTIC_TYPES,
    CLINICAL_GROUNDED_TYPES,
    LOW_CONFIDENCE_TYPES,
    _has_grounded_citation,
)

# Billing patterns strong enough to ask about immediately (pure math / structure).
HARD_BILLING_MATH_TYPES: frozenset[str] = frozenset(
    {
        "DUPLICATE_ITEM",
        "PACKAGE_COMPONENT_CHARGED_SEPARATELY",
        "BILLED_NOT_PRESCRIBED",
    }
)

# Overpriced-medicine flag: Tier A only when a concrete NPPA reference exists.
REFERENCE_PRICED_TYPES: frozenset[str] = frozenset({"MEDICINE_PRICE_DISCREPANCY"})

# "Verify then ask" billing / clinical-data flags.
VERIFY_FLAG_TYPES: frozenset[str] = frozenset(
    {
        "NEAR_DUPLICATE_ITEM",
        "MISSING_REQUIRED_INVESTIGATION",
    }
)

TIER_LABELS: dict[str, str] = {
    "A": "Ask now",
    "B": "Verify then ask",
    "C": "Document only",
}


def _flag_type(flag: dict[str, Any]) -> str:
    return str(flag.get("type") or "")


def _confidence(flag: dict[str, Any]) -> str:
    value = str(flag.get("confidence") or "LOW").upper()
    return value if value in {"HIGH", "MEDIUM", "LOW"} else "LOW"


def _line_item_has_reference(line_item: dict[str, Any] | None) -> bool:
    if not isinstance(line_item, dict):
        return False
    if line_item.get("pharma_rate") is not None:
        return True
    return bool(line_item.get("matched_reference_item"))


def assign_action_tier(
    flag: dict[str, Any],
    *,
    line_item: dict[str, Any] | None = None,
) -> str:
    """Return ``"A"``, ``"B"``, or ``"C"`` for a single finalized audit flag."""
    flag_type = _flag_type(flag)
    confidence = _confidence(flag)

    # Always document-only for insufficient / not-identified evidence.
    if flag_type in LOW_CONFIDENCE_TYPES:
        return "C"

    # Hard billing math: strong enough to ask immediately.
    if flag_type in HARD_BILLING_MATH_TYPES:
        return "A"

    # Overpriced medicine: Tier A only when a concrete reference rate backs it.
    if flag_type in REFERENCE_PRICED_TYPES:
        if line_item is None or _line_item_has_reference(line_item):
            return "A"
        return "B"

    # Grounded clinical flags follow their confidence + grounding.
    if flag_type in CLINICAL_GROUNDED_TYPES:
        if confidence == "HIGH" and _has_grounded_citation(flag, []):
            return "A"
        if confidence == "MEDIUM":
            return "B"
        return "C"

    # Explicit "verify then ask" family.
    if flag_type in VERIFY_FLAG_TYPES:
        return "B"

    # Fall back to raw confidence for any other billing heuristic.
    if confidence == "HIGH":
        return "A"
    if confidence == "MEDIUM":
        return "B"
    return "C"


def is_billing_flag(flag: dict[str, Any]) -> bool:
    """True when a flag concerns billing rather than clinical appropriateness."""
    flag_type = _flag_type(flag)
    if flag_type in BILLING_HEURISTIC_TYPES:
        return True
    return str(flag.get("category") or "").strip().lower() == "billing"
