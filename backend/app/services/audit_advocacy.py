"""Shared patient-advocacy helpers: confidence, neutral labels, and question lists."""

from __future__ import annotations

import re
from typing import Any

from app.services.rag_pipeline import _find_supporting_chunk

LOW_CONFIDENCE_TYPES = frozenset(
    {
        "INSUFFICIENT_STG_EVIDENCE",
        "INSUFFICIENT_CLINICAL_DATA",
        "GUIDELINE_SUPPORT_NOT_IDENTIFIED",
    }
)

CLINICAL_GROUNDED_TYPES = frozenset(
    {
        "UNNECESSARY_TEST",
        "UNNECESSARY_PROCEDURE",
        "NOT_INDICATED_MEDICINE",
        "PRESCRIBED_NOT_IN_STG",
        "DIAGNOSIS_UNSUPPORTED",
        "DIAGNOSIS_TEST_MISMATCH",
        "MISSING_REQUIRED_INVESTIGATION",
        "PRESCRIPTION_CLINICAL_MISMATCH",
        "EXCESSIVE_WORKUP",
        "INVESTIGATION_NOT_ROUTINELY_RECOMMENDED",
        "DUPLICATE_THERAPEUTIC_CLASS",
        "BROADER_SPECTRUM_ANTIBIOTIC",
        "DRUG_INTERACTION",
        "BRAND_WITHOUT_GENERIC_QUESTION",
        "ABNORMAL_LAB_VALUE",
        "REPEAT_INVESTIGATION",
        "PREGNANCY_CONTRAINDICATION",
        "PREGNANCY_CAUTION",
        "LACTATION_CAUTION",
        "PEDIATRIC_DOSING_CAUTION",
    }
)

BILLING_HEURISTIC_TYPES = frozenset(
    {
        "DUPLICATE_ITEM",
        "NEAR_DUPLICATE_ITEM",
        "UNREALISTIC_REPETITION",
        "LAB_REPETITION",
        "PACKAGE_COMPONENT_CHARGED_SEPARATELY",
        "MEDICINE_PRICE_DISCREPANCY",
        "BILLED_NOT_PRESCRIBED",
    }
)

FLAG_DISPLAY_LABELS: dict[str, str] = {
    "UNNECESSARY_TEST": "Not routinely recommended",
    "UNNECESSARY_PROCEDURE": "Not routinely recommended",
    "INVESTIGATION_NOT_ROUTINELY_RECOMMENDED": "Not routinely recommended",
    "NOT_INDICATED_MEDICINE": "Not in guideline for this scenario",
    "PRESCRIBED_NOT_IN_STG": "Not listed in guideline",
    "INSUFFICIENT_STG_EVIDENCE": "Guideline support not identified",
    "GUIDELINE_SUPPORT_NOT_IDENTIFIED": "Guideline support not identified",
    "INSUFFICIENT_CLINICAL_DATA": "Needs more clinical information",
    "DIAGNOSIS_UNSUPPORTED": "Diagnosis not supported by reported evidence",
    "DIAGNOSIS_TEST_MISMATCH": "Diagnosis conflicts with test results",
    "MISSING_REQUIRED_INVESTIGATION": "Recommended test may be missing",
    "PRESCRIPTION_CLINICAL_MISMATCH": "Treatment may not match clinical picture",
    "EXCESSIVE_WORKUP": "Workup may be more than typically needed",
    "DUPLICATE_ITEM": "Repeated bill item",
    "NEAR_DUPLICATE_ITEM": "Possibly duplicate bill item",
    "UNREALISTIC_REPETITION": "Unusually high repetition",
    "LAB_REPETITION": "Repeated lab or test charge",
    "PACKAGE_COMPONENT_CHARGED_SEPARATELY": "Package and component both billed",
    "MEDICINE_PRICE_DISCREPANCY": "Medicine price above reference",
    "BILLED_NOT_PRESCRIBED": "Billed without prescription match",
    "PREAUTH_AMOUNT_ABOVE_APPROVED": "Bill above pre-authorization amount",
    "PREAUTH_ITEM_OUTSIDE_AUTHORIZATION": "Item not clearly listed in pre-authorization",
    "DUPLICATE_THERAPEUTIC_CLASS": "Duplicate therapeutic class",
    "BROADER_SPECTRUM_ANTIBIOTIC": "Broader-spectrum antibiotic than typical",
    "DRUG_INTERACTION": "Possible drug interaction",
    "BRAND_WITHOUT_GENERIC_QUESTION": "Branded medicine with generic alternative",
    "ABNORMAL_LAB_VALUE": "Lab result outside expected range",
    "REPEAT_INVESTIGATION": "Repeat test from recent visit",
    "PREGNANCY_CONTRAINDICATION": "Medicine commonly avoided in pregnancy",
    "PREGNANCY_CAUTION": "Medicine needs pregnancy review",
    "LACTATION_CAUTION": "Medicine needs breastfeeding review",
    "PEDIATRIC_DOSING_CAUTION": "Medicine needs age-appropriate review",
}

ADVOCACY_SCOPE_CHECKED = [
    "Government treatment guideline retrieval and comparison",
    "Billing pattern checks (repetition, package components)",
    "Prescription rationality checks where data is available",
    "Restricted medicine list screening",
]

ADVOCACY_SCOPE_NOT_CHECKED = [
    "Final medical diagnosis or emergency exceptions",
    "Individual clinician judgment",
    "Definitive legal or regulatory findings against any provider",
]


def flag_display_label(flag_type: str | None) -> str:
    key = str(flag_type or "").strip()
    if not key:
        return "Item worth clarifying"
    return FLAG_DISPLAY_LABELS.get(key, key.replace("_", " ").title())


def _has_grounded_citation(flag: dict[str, Any], chunks: list[dict[str, Any]]) -> bool:
    if flag.get("citation_verified") is True:
        return True
    reference = flag.get("stg_reference")
    if isinstance(reference, dict) and reference.get("condition"):
        return True
    basis = str(flag.get("guideline_basis") or "").strip()
    if basis and basis.lower().startswith("based on"):
        return True
    if chunks and basis:
        support = _find_supporting_chunk(flag, chunks)
        return support is not None
    return False


def assign_confidence(
    flag: dict[str, Any],
    *,
    chunks: list[dict[str, Any]] | None = None,
) -> str:
    if flag.get("confidence") in {"HIGH", "MEDIUM", "LOW"}:
        return str(flag["confidence"])

    flag_type = str(flag.get("type") or "")
    if flag_type in LOW_CONFIDENCE_TYPES:
        return "LOW"

    chunk_list = chunks or []
    grounded = _has_grounded_citation(flag, chunk_list)

    if flag_type in CLINICAL_GROUNDED_TYPES:
        if grounded and flag.get("stg_reference"):
            return "HIGH"
        if grounded:
            return "MEDIUM"
        return "LOW"

    if flag_type in BILLING_HEURISTIC_TYPES:
        return "MEDIUM"

    if grounded and flag.get("severity") == "HIGH":
        return "HIGH"
    if grounded:
        return "MEDIUM"
    return "LOW"


def _recommendation_to_question(recommendation: str, item: str) -> str:
    text = str(recommendation or "").strip()
    if not text:
        if item:
            return f"Why was {item} ordered or billed?"
        return "Can you explain this charge or treatment decision?"

    if text.endswith("?"):
        return text

    lowered = text.lower()
    if lowered.startswith("ask "):
        # "Ask your doctor whether..." -> "Why...?" / keep as imperative question prompt
        whether_match = re.search(
            r"ask (?:your doctor|the clinician|the hospital)(?: to)? whether (.+)",
            text,
            re.IGNORECASE,
        )
        if whether_match:
            clause = whether_match.group(1).rstrip(".")
            return f"Why {clause}?"
        for_match = re.search(
            r"ask (?:the )?hospital for (.+)",
            text,
            re.IGNORECASE,
        )
        if for_match:
            return f"Can the hospital provide {for_match.group(1).rstrip('.')}?"
        explain_match = re.search(
            r"ask (?:the )?hospital to explain (.+)",
            text,
            re.IGNORECASE,
        )
        if explain_match:
            return f"Why {explain_match.group(1).rstrip('.')}?"
        return text

    if item and item.lower() not in text.lower():
        return f"{text} ({item})"
    return text


def build_patient_questions(
    flags: list[dict[str, Any]],
    *,
    max_questions: int = 12,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    questions: list[dict[str, Any]] = []

    confidence_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sorted_flags = sorted(
        flags,
        key=lambda flag: (
            confidence_order.get(str(flag.get("confidence") or "LOW"), 2),
            0 if flag.get("severity") == "HIGH" else 1,
        ),
    )

    for flag in sorted_flags:
        if not isinstance(flag, dict):
            continue
        item = str(flag.get("item") or "").strip()
        recommendation = str(flag.get("recommendation") or "").strip()
        question = _recommendation_to_question(recommendation, item)
        dedupe_key = re.sub(r"\s+", " ", question.lower()).strip()
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        questions.append(
            {
                "question": question,
                "item": item or None,
                "confidence": flag.get("confidence") or "LOW",
                "guideline_basis": flag.get("guideline_basis") or None,
                "flag_type": flag.get("type"),
                "display_label": flag_display_label(str(flag.get("type") or "")),
                "category": flag.get("category"),
            }
        )
        if len(questions) >= max_questions:
            break

    return questions


def finalize_audit_flags(
    flags: list[dict[str, Any]],
    *,
    chunks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    finalized: list[dict[str, Any]] = []
    chunk_list = chunks or []
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        item = dict(flag)
        item["confidence"] = assign_confidence(item, chunks=chunk_list)
        if (
            str(item.get("type") or "") in CLINICAL_GROUNDED_TYPES
            and item["confidence"] == "HIGH"
            and not _has_grounded_citation(item, chunk_list)
        ):
            item["confidence"] = "LOW"
        item["display_label"] = flag_display_label(str(item.get("type") or ""))
        finalized.append(item)
    return finalized


def merge_patient_questions(
    *sources: list[dict[str, Any]] | None,
    max_questions: int = 15,
) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for source in sources:
        if not source:
            continue
        combined.extend(source)
    return build_patient_questions(
        [{"recommendation": item.get("question"), **item} for item in combined],
        max_questions=max_questions,
    )


def build_advocacy_payload(
    flags: list[dict[str, Any]],
    *,
    chunks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from app.services.legal_case_framing import attach_legal_pathways
    from app.services.rag_pipeline import validate_stg_citations

    chunk_list = chunks or []
    validated = validate_stg_citations(flags, chunk_list)
    finalized = finalize_audit_flags(validated, chunks=chunk_list)
    with_pathways = attach_legal_pathways(finalized)
    return {
        "flags": with_pathways,
        "flags_count": len(with_pathways),
        "patient_questions": build_patient_questions(with_pathways),
        "advocacy_scope": {
            "checked": list(ADVOCACY_SCOPE_CHECKED),
            "not_checked": list(ADVOCACY_SCOPE_NOT_CHECKED),
        },
    }
