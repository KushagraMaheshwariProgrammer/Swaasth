"""Builds the ``action_plan`` block: a confidence-gated "legal strength" layer.

Everything here is derived from the already-finalized audit flags, the compared
bill line items, and the Jan Aushadhi summary. No new datasets, no accusations:
recoverable estimates are pure billing math and every generated action/template
string is routed through :mod:`app.services.legal_guardrails`.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.action_tiers import (
    HARD_BILLING_MATH_TYPES,
    REFERENCE_PRICED_TYPES,
    assign_action_tier,
    is_billing_flag,
)
from app.services.audit_advocacy import (
    _recommendation_to_question,
    flag_display_label,
)
from app.services.legal_guardrails import sanitize_text

# Disputed-amount threshold (INR) above which the "consider an advocate" step is
# offered. Combined HIGH clinical + billing findings also unlock it.
HIGH_DISPUTE_THRESHOLD = 25000.0

_ACTION_PLAN_DISCLAIMER = (
    "This action plan is assistance based on reference rates and government "
    "treatment guidelines available in the app. It is not a final medical, "
    "legal, or regulatory finding against any hospital or doctor. Verify every "
    "detail before acting."
)

_RECOVERABLE_DISCLAIMER = (
    "This is an estimate from billing math only (reference-rate differences and "
    "subsidized-scheme prices). It is not a guaranteed refund; package terms, "
    "exclusions, and item matches may require manual verification."
)

_EMERGENCY_NOTE = (
    "In a medical emergency, do not delay or refuse necessary care over a billing "
    "concern. Raise billing questions in parallel and keep copies of everything."
)

_BILLING_ATTACHMENTS = ["Itemized bill", "Payment receipt"]
_CLINICAL_ATTACHMENTS = [
    "Prescription",
    "Discharge summary",
    "Relevant test/lab reports",
]
_MEDICINE_PRICE_ATTACHMENTS = [
    "Itemized bill",
    "Medicine strip or label showing brand and strength",
]


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip().lower())


def _match_line_item(
    flag: dict[str, Any],
    line_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    item_name = _normalize_name(flag.get("item"))
    if not item_name:
        return None
    for line in line_items:
        line_name = _normalize_name(line.get("item_name") or line.get("name"))
        if not line_name:
            continue
        if line_name == item_name or line_name in item_name or item_name in line_name:
            return line
    return None


def _is_billing_strength_flag(flag: dict[str, Any]) -> bool:
    """Billing-math concern even when the audit labels its category clinically."""
    if is_billing_flag(flag):
        return True
    return str(flag.get("type") or "") in (
        HARD_BILLING_MATH_TYPES | REFERENCE_PRICED_TYPES
    )


def _attachments_for(flag: dict[str, Any]) -> list[str]:
    flag_type = str(flag.get("type") or "")
    if flag_type.startswith("PREAUTH_"):
        return ["Itemized bill", "Pre-authorization approval", "Claim or policy documents"]
    if flag_type == "MEDICINE_PRICE_DISCREPANCY":
        return list(_MEDICINE_PRICE_ATTACHMENTS)
    if is_billing_flag(flag):
        return list(_BILLING_ATTACHMENTS)
    return list(_CLINICAL_ATTACHMENTS)


def _action_text(flag: dict[str, Any], tier: str) -> str:
    item = str(flag.get("item") or "").strip()
    question = _recommendation_to_question(
        str(flag.get("recommendation") or ""), item
    )
    if tier == "A":
        prefix = "Ask the billing or records desk now"
    elif tier == "B":
        prefix = "Verify the details first, then ask"
    else:
        prefix = "Keep this on record for now"
    return sanitize_text(f"{prefix}: {question}")


def _reference_rate(line_item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(line_item, dict):
        return None
    if line_item.get("pharma_rate") is not None:
        return {
            "value": line_item.get("pharma_rate"),
            "source": "NPPA ceiling price",
            "date": line_item.get("pharma_price_date"),
        }
    if line_item.get("jan_aushadhi_mrp") is not None:
        return {
            "value": line_item.get("jan_aushadhi_mrp"),
            "source": "Jan Aushadhi (PMBJP) subsidized MRP",
            "date": None,
        }
    return None


def _stg_excerpt(flag: dict[str, Any]) -> dict[str, Any] | None:
    citation = flag.get("stg_citation")
    if isinstance(citation, dict) and citation.get("full_text"):
        source = citation.get("source") if isinstance(citation.get("source"), dict) else {}
        reference = citation.get("reference") if isinstance(citation.get("reference"), dict) else {}
        return {
            "condition": reference.get("condition"),
            "section": reference.get("section"),
            "page": reference.get("page"),
            "text": sanitize_text(str(citation.get("full_text") or "")) or None,
            "source_label": source.get("corpus_label"),
            "authority": source.get("authority"),
        }
    reference = flag.get("stg_reference")
    if not isinstance(reference, dict) or not reference.get("condition"):
        return None
    return {
        "condition": reference.get("condition"),
        "section": reference.get("section"),
        "page": reference.get("page"),
        "text": sanitize_text(str(flag.get("guideline_basis") or "")) or None,
        "source_label": None,
        "authority": None,
    }


def _build_action_items(
    flags: list[dict[str, Any]],
    line_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    action_items: list[dict[str, Any]] = []
    tiers: list[str] = []
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        line_item = _match_line_item(flag, line_items)
        tier = assign_action_tier(flag, line_item=line_item)
        tiers.append(tier)
        display_label = flag.get("display_label") or flag_display_label(
            str(flag.get("type") or "")
        )
        action_items.append(
            {
                "type": flag.get("type"),
                "item": flag.get("item"),
                "display_label": display_label,
                "confidence": flag.get("confidence") or "LOW",
                "tier": tier,
                "action": _action_text(flag, tier),
                "attachments": _attachments_for(flag),
            }
        )
    return action_items, tiers


def _build_recoverable_estimate(
    line_items: list[dict[str, Any]],
    jan_aushadhi: dict[str, Any] | None,
) -> dict[str, Any]:
    basis: list[dict[str, Any]] = []
    overpriced_total = 0.0
    for line in line_items:
        if line.get("flag") != "overpriced":
            continue
        diff = _to_float(line.get("price_difference"))
        if diff <= 0:
            continue
        overpriced_total += diff
        reference = line.get("matched_reference_item") or "NPPA ceiling reference"
        basis.append(
            {
                "item": line.get("item_name") or line.get("name"),
                "amount": round(diff, 2),
                "source": f"Charged above NPPA ceiling ({reference})",
            }
        )

    jan_savings = 0.0
    for line in line_items:
        if not line.get("jan_aushadhi_available"):
            continue
        mrp = line.get("jan_aushadhi_mrp")
        if mrp is None:
            continue
        charged = _to_float(line.get("total_price"))
        saving = charged - _to_float(mrp)
        if saving <= 0:
            continue
        jan_savings += saving
        basis.append(
            {
                "item": line.get("item_name") or line.get("name"),
                "amount": round(saving, 2),
                "source": "Available under Jan Aushadhi (PMBJP) at subsidized MRP",
            }
        )

    overpriced_total = round(overpriced_total, 2)
    jan_savings = round(jan_savings, 2)
    return {
        "overpriced_total": overpriced_total,
        "jan_aushadhi_savings": jan_savings,
        "total": round(overpriced_total + jan_savings, 2),
        "basis": basis,
        "disclaimer": _RECOVERABLE_DISCLAIMER,
    }


def _build_discharge_guidance(
    flags: list[dict[str, Any]],
    tiers: list[str],
) -> dict[str, Any]:
    reasons: list[str] = []
    has_tier_a_billing = False
    has_tier_b = False

    for flag, tier in zip(flags, tiers):
        if tier == "A" and _is_billing_strength_flag(flag):
            has_tier_a_billing = True
        if tier == "B":
            has_tier_b = True

    if has_tier_a_billing:
        status = "hold"
        reasons.append(
            "There is at least one billing item you can clarify now before paying."
        )
    elif has_tier_b:
        status = "caution"
        reasons.append(
            "Some items are worth verifying before you settle the bill or discharge."
        )
    else:
        status = "pay_ok"
        reasons.append(
            "No high-strength billing concerns were flagged for clarification."
        )

    for flag, tier in zip(flags, tiers):
        if tier in {"A", "B"}:
            label = flag.get("display_label") or flag_display_label(
                str(flag.get("type") or "")
            )
            item = str(flag.get("item") or "").strip()
            reason = f"{label}: {item}" if item else str(label)
            reasons.append(sanitize_text(reason))

    return {
        "status": status,
        "reasons": [sanitize_text(reason) for reason in reasons],
        "emergency_note": _EMERGENCY_NOTE,
    }


def _build_escalation_ladder(
    *,
    recoverable_total: float,
    has_high_clinical: bool,
    has_high_billing: bool,
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = [
        {
            "title": "Hospital billing or records desk",
            "when": "Before you pay or at discharge, for any item you want explained.",
            "what_to_attach": ["Itemized bill", "Payment receipt", "Prescription"],
            "typical_timeline": "Same day, while you are still at the hospital.",
        },
        {
            "title": "Hospital grievance officer / medical superintendent",
            "when": "If the billing desk cannot resolve your questions.",
            "what_to_attach": [
                "Itemized bill",
                "Written summary of your questions",
                "Any earlier replies",
            ],
            "typical_timeline": "A few working days after a written request.",
        },
        {
            "title": "Insurer / scheme nodal officer (if insured or under a scheme)",
            "when": "If the charges affect an insurance or government-scheme claim.",
            "what_to_attach": [
                "Itemized bill",
                "Policy or scheme card",
                "Claim or pre-authorization documents",
            ],
            "typical_timeline": "Usually acknowledged within a few working days.",
        },
        {
            "title": "State health authority / regulator",
            "when": "If the hospital does not respond to a written grievance.",
            "what_to_attach": [
                "Itemized bill",
                "Copies of your earlier grievance",
                "Any responses received",
            ],
            "typical_timeline": "Varies by state; keep acknowledgement records.",
        },
        {
            "title": "Consumer disputes redressal commission",
            "when": "If the matter is still unresolved after the above steps.",
            "what_to_attach": [
                "Itemized bill",
                "All correspondence",
                "This dispute pack",
            ],
            "typical_timeline": "A formal process that can take longer; timelines vary.",
        },
    ]

    if recoverable_total >= HIGH_DISPUTE_THRESHOLD or (
        has_high_clinical and has_high_billing
    ):
        steps.append(
            {
                "title": "Consider professional advice from an advocate",
                "when": (
                    "For a large disputed amount or when both clinical and billing "
                    "concerns are strong, you may wish to consult a professional."
                ),
                "what_to_attach": [
                    "Itemized bill",
                    "All correspondence",
                    "This dispute pack",
                ],
                "typical_timeline": "At your discretion.",
            }
        )

    ladder: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        ladder.append(
            {
                "step": index,
                "title": sanitize_text(step["title"]),
                "when": sanitize_text(step["when"]),
                "what_to_attach": [sanitize_text(part) for part in step["what_to_attach"]],
                "typical_timeline": sanitize_text(step["typical_timeline"]),
                "disclaimer": (
                    "This is general procedural guidance, not legal advice; "
                    "steps and timelines vary by hospital, insurer, and state."
                ),
            }
        )
    return ladder


def _build_complaint_templates(
    flags: list[dict[str, Any]],
    tiers: list[str],
) -> list[dict[str, Any]]:
    actionable = [
        flag
        for flag, tier in zip(flags, tiers)
        if tier in {"A", "B"} and isinstance(flag, dict)
    ]
    if not actionable:
        return []

    included_flags = [
        sanitize_text(
            str(
                flag.get("display_label")
                or flag_display_label(str(flag.get("type") or ""))
            )
            + (f" ({flag.get('item')})" if flag.get("item") else "")
        )
        for flag in actionable
    ]
    flag_lines = "\n".join(f"- {label}" for label in included_flags)

    templates_raw = [
        {
            "id": "hospital_billing_grievance",
            "audience": "Hospital billing / grievance officer",
            "subject": "Request to review specific charges on my hospital bill",
            "body": (
                "Dear Sir/Madam,\n\n"
                "I am writing about the bill for {patient} at {hospital} dated {date}. "
                "On reviewing the itemized bill, I would like clarification on the "
                "following items before I treat the amount of {amount} as final:\n\n"
                f"{flag_lines}\n\n"
                "Please share the supporting prescriptions, package inclusions, and "
                "the reference rates used for these items. I am happy to provide any "
                "documents you need. I look forward to your written response.\n\n"
                "Thank you,\n{patient}"
            ),
        },
        {
            "id": "insurer_scheme_escalation",
            "audience": "Insurer / government-scheme nodal officer",
            "subject": "Clarification request on hospital charges under my claim",
            "body": (
                "Dear Sir/Madam,\n\n"
                "This concerns the claim for {patient} treated at {hospital} on {date}. "
                "While reviewing the itemized bill totaling {amount}, I noticed the "
                "following items that I would like verified against the applicable "
                "rates and my policy or scheme terms:\n\n"
                f"{flag_lines}\n\n"
                "Kindly review these items during claim processing and let me know if "
                "you require any further documents.\n\n"
                "Thank you,\n{patient}"
            ),
        },
        {
            "id": "consumer_forum_summary",
            "audience": "Consumer disputes redressal commission",
            "subject": "Summary of unresolved hospital billing concerns",
            "body": (
                "To the Honourable Commission,\n\n"
                "I am submitting a summary of billing concerns regarding treatment of "
                "{patient} at {hospital} on {date}, for a bill amount of {amount}, that "
                "remained unresolved after I approached the hospital and, where "
                "applicable, my insurer. The items I asked to be clarified are:\n\n"
                f"{flag_lines}\n\n"
                "Supporting documents, correspondence, and the accompanying dispute "
                "pack are enclosed for your consideration.\n\n"
                "Respectfully,\n{patient}"
            ),
        },
    ]

    templates: list[dict[str, Any]] = []
    for template in templates_raw:
        templates.append(
            {
                "id": template["id"],
                "audience": sanitize_text(template["audience"]),
                "subject": sanitize_text(template["subject"]),
                "body": sanitize_text(template["body"]),
                "included_flags": included_flags,
                "requires_confirmation": True,
            }
        )
    return templates


def _build_evidence_pack_items(
    flags: list[dict[str, Any]],
    tiers: list[str],
    line_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for flag, tier in zip(flags, tiers):
        if tier not in {"A", "B"} or not isinstance(flag, dict):
            continue
        line_item = _match_line_item(flag, line_items)
        item = str(flag.get("item") or "").strip()
        question = _recommendation_to_question(
            str(flag.get("recommendation") or ""), item
        )
        items.append(
            {
                "type": flag.get("type"),
                "item": flag.get("item"),
                "display_label": flag.get("display_label")
                or flag_display_label(str(flag.get("type") or "")),
                "confidence": flag.get("confidence") or "LOW",
                "tier": tier,
                "bill_line": line_item or None,
                "reference_rate": _reference_rate(line_item),
                "stg_excerpt": _stg_excerpt(flag),
                "questions": [sanitize_text(question)] if question else [],
            }
        )
    return items


def _build_combined_narrative(
    *,
    flags: list[dict[str, Any]],
    action_items: list[dict[str, Any]],
    recoverable_estimate: dict[str, Any],
    patient: dict[str, Any] | None,
    hospital: dict[str, Any] | None,
) -> dict[str, Any]:
    """One-paragraph factual summary for a family member or advocate."""
    patient_name = str((patient or {}).get("name") or "the patient").strip()
    hospital_name = str(
        (hospital or {}).get("name_from_bill") or (hospital or {}).get("name") or "the hospital"
    ).strip()
    actionable = [
        item
        for item in action_items
        if item.get("tier") in {"A", "B"} and (item.get("display_label") or item.get("item"))
    ]
    top_items = [
        sanitize_text(
            str(item.get("display_label") or "Item worth clarifying")
            + (f" ({item.get('item')})" if item.get("item") else "")
        )
        for item in actionable[:3]
    ]
    recoverable_total = _to_float(recoverable_estimate.get("total"))
    clinical_count = sum(
        1 for flag in flags if str(flag.get("category") or "").lower() != "billing"
    )
    billing_count = sum(
        1 for flag in flags if str(flag.get("category") or "").lower() == "billing"
    )

    if top_items:
        concern_text = ", ".join(top_items)
    elif flags:
        concern_text = "the listed clarification points"
    else:
        concern_text = "the uploaded documents"

    amount_text = (
        f" The reference-rate math suggests about INR {recoverable_total:,.0f} may be worth verifying."
        if recoverable_total > 0
        else ""
    )
    context_bits = []
    if billing_count:
        context_bits.append(f"{billing_count} billing point{'s' if billing_count != 1 else ''}")
    if clinical_count:
        context_bits.append(
            f"{clinical_count} clinical/STG point{'s' if clinical_count != 1 else ''}"
        )
    context_text = ", ".join(context_bits) if context_bits else "no high-priority finding"

    summary = (
        f"For {patient_name}, Swaasth found {context_text} for review in the documents "
        f"from {hospital_name}. The main points to verify are {concern_text}.{amount_text} "
        "Use this as a factual summary for discussion with the hospital, insurer, or an "
        "appropriate professional; it is not a medical or legal conclusion."
    )
    return {
        "summary": sanitize_text(summary),
        "disclaimer": (
            "This narrative is a plain-language summary of app findings only. "
            "Verify facts and consult qualified professionals before acting."
        ),
    }


def build_action_plan(
    *,
    flags: list[dict[str, Any]] | None,
    line_items: list[dict[str, Any]] | None,
    jan_aushadhi: dict[str, Any] | None = None,
    patient: dict[str, Any] | None = None,
    hospital: dict[str, Any] | None = None,
    clinical: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the full ``action_plan`` block from finalized flags + bill data."""
    del clinical  # Reserved for future personalization.

    flag_list = [flag for flag in (flags or []) if isinstance(flag, dict)]
    item_list = list(line_items or [])

    action_items, tiers = _build_action_items(flag_list, item_list)

    tier_summary = {
        "A": tiers.count("A"),
        "B": tiers.count("B"),
        "C": tiers.count("C"),
    }

    recoverable_estimate = _build_recoverable_estimate(item_list, jan_aushadhi)
    discharge_guidance = _build_discharge_guidance(flag_list, tiers)

    has_high_clinical = any(
        not is_billing_flag(flag)
        and str(flag.get("confidence") or "").upper() == "HIGH"
        for flag in flag_list
    )
    has_high_billing = any(
        _is_billing_strength_flag(flag) and tier == "A"
        for flag, tier in zip(flag_list, tiers)
    )
    escalation_ladder = _build_escalation_ladder(
        recoverable_total=recoverable_estimate["total"],
        has_high_clinical=has_high_clinical,
        has_high_billing=has_high_billing,
    )

    complaint_templates = _build_complaint_templates(flag_list, tiers)
    evidence_pack_items = _build_evidence_pack_items(flag_list, tiers, item_list)
    combined_narrative = _build_combined_narrative(
        flags=flag_list,
        action_items=action_items,
        recoverable_estimate=recoverable_estimate,
        patient=patient,
        hospital=hospital,
    )

    return {
        "action_items": action_items,
        "tier_summary": tier_summary,
        "recoverable_estimate": recoverable_estimate,
        "discharge_guidance": discharge_guidance,
        "escalation_ladder": escalation_ladder,
        "complaint_templates": complaint_templates,
        "evidence_pack_items": evidence_pack_items,
        "combined_narrative": combined_narrative,
        "disclaimer": _ACTION_PLAN_DISCLAIMER,
        "guardrails": {"banned_terms_filtered": True},
    }
