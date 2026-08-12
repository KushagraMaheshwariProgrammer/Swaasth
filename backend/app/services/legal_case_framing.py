"""Educational legal-pathway hints for flagged findings.

This module describes *hypothetical* legal angles patients may discuss with a
qualified advocate. It does not accuse any provider and is not legal advice.
"""

from __future__ import annotations

from typing import Any

from app.services.legal_guardrails import POSSIBLE_ISSUE_NOTICE, sanitize_value

_PATHWAYS: dict[str, dict[str, Any]] = {
    "billing": {
        "broader_concept": "Deficiency in service / unfair trade practice (billing)",
        "specific_angle": (
            "A complaint may focus on unexplained duplicate charges, package "
            "components billed twice, or amounts above reference rates."
        ),
        "what_must_be_proven": (
            "You would typically need itemized bills, prescriptions, package "
            "terms, and proof that a specific charge was not agreed or not justified."
        ),
        "not_an_accusation": (
            "This is a possible grievance framing, not a finding against any "
            "hospital or clinician."
        ),
    },
    "clinical": {
        "broader_concept": "Medical negligence / deficiency in medical service",
        "specific_angle": (
            "A lawyer may ask whether care departed from accepted medical practice "
            "for the documented diagnosis, symptoms, and test results."
        ),
        "what_must_be_proven": (
            "Expert medical opinion, complete records, and a causal link between "
            "the alleged departure and harm are usually required."
        ),
        "not_an_accusation": (
            "A guideline mismatch is a question for clinical review, not proof of "
            "medical negligence."
        ),
    },
    "preauth": {
        "broader_concept": "Insurance / scheme deficiency in service",
        "specific_angle": (
            "A complaint may ask whether billed items exceeded pre-authorization "
            "or were excluded under policy or scheme terms."
        ),
        "what_must_be_proven": (
            "Pre-authorization letter, final bill, policy wording, and insurer "
            "correspondence are typically required."
        ),
        "not_an_accusation": (
            "A mismatch flag is a factual comparison only; it does not establish "
            "insurer or hospital wrongdoing."
        ),
    },
}

_FLAG_OVERRIDES: dict[str, dict[str, str]] = {
    "DUPLICATE_ITEM": {
        "specific_angle": (
            "Repeated identical line items may support a billing deficiency "
            "complaint if the hospital cannot show separate services."
        ),
    },
    "PACKAGE_COMPONENT_CHARGED_SEPARATELY": {
        "specific_angle": (
            "Charging a package and its components separately may be raised as "
            "misleading billing or deficiency in service."
        ),
    },
    "PREAUTH_AMOUNT_ABOVE_APPROVED": {
        "broader_concept": "Insurance / scheme dispute",
    },
    "PREAUTH_ITEM_OUTSIDE_AUTHORIZATION": {
        "broader_concept": "Insurance / scheme dispute",
    },
    "DIAGNOSIS_TEST_MISMATCH": {
        "specific_angle": (
            "Conflicting diagnosis and test results may be discussed as a "
            "possible diagnostic deficiency if expert opinion supports it."
        ),
    },
    "NOT_INDICATED_MEDICINE": {
        "specific_angle": (
            "A medicine not aligned with guidelines may be framed as a treatment "
            "appropriateness question in a medical negligence inquiry."
        ),
    },
    "UNNECESSARY_TEST": {
        "specific_angle": (
            "Tests not routinely indicated may support questions about excessive "
            "investigation or billing for unneeded services."
        ),
    },
    "EXCESSIVE_WORKUP": {
        "specific_angle": (
            "Advanced imaging or broad workup without documented indication may "
            "be raised in both clinical and billing grievances."
        ),
    },
}


def _pathway_category(flag: dict[str, Any]) -> str:
    flag_type = str(flag.get("type") or "")
    if flag_type.startswith("PREAUTH_"):
        return "preauth"
    if str(flag.get("category") or "").lower() == "billing":
        return "billing"
    if flag_type in {
        "DUPLICATE_ITEM",
        "NEAR_DUPLICATE_ITEM",
        "PACKAGE_COMPONENT_CHARGED_SEPARATELY",
        "MEDICINE_PRICE_DISCREPANCY",
        "BILLED_NOT_PRESCRIBED",
    }:
        return "billing"
    return "clinical"


def build_legal_pathway_for_flag(flag: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(flag, dict):
        return None
    flag_type = str(flag.get("type") or "")
    if flag_type in {
        "INSUFFICIENT_STG_EVIDENCE",
        "INSUFFICIENT_CLINICAL_DATA",
        "GUIDELINE_SUPPORT_NOT_IDENTIFIED",
    }:
        return None

    base = dict(_PATHWAYS[_pathway_category(flag)])
    override = _FLAG_OVERRIDES.get(flag_type, {})
    base.update(override)
    item = str(flag.get("item") or "").strip()
    if item:
        base["item_context"] = item

    base["disclaimer"] = (
        f"{POSSIBLE_ISSUE_NOTICE} Educational summary only — not legal advice. "
        "An advocate must review your records before any complaint, forum filing, "
        "or allegation."
    )
    return base


def attach_legal_pathways(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        item = dict(flag)
        pathway = build_legal_pathway_for_flag(item)
        if pathway:
            item["legal_pathway"] = sanitize_value(pathway)
        enriched.append(item)
    return enriched
