"""STG-grounded treatment appropriateness audit with clinical triangle checks."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from fastapi import HTTPException

from app.services.audit_advocacy import build_advocacy_payload, finalize_audit_flags
from app.services.groq_client import groq_json_chat
from app.services.investigation_audit import analyze_investigations
from app.services.prescription_rationality import analyze_prescription_rationality
from app.services.rag_pipeline import (
    _find_supporting_chunk,
    format_guideline_basis,
    sanitize_display_text,
    validate_stg_citations,
)
from app.services.stg_retrieval import retrieve_stg_context

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

MALARIA_MARKERS = ("malaria", "plasmodium")
MALARIA_TEST_MARKERS = ("malaria", "rdt", "smear", "parasite", "mp", "rapid diagnostic")
DENGUE_MARKERS = ("dengue",)
DENGUE_TEST_MARKERS = ("dengue", "ns1", "igg", "igm", "platelet")
ANTIBIOTIC_MARKERS = (
    "azithromycin",
    "ceftriaxone",
    "meropenem",
    "amoxicillin",
    "ciprofloxacin",
    "levofloxacin",
    "doxycycline",
)
TYPHOID_MARKERS = ("typhoid", "enteric fever", "salmonella typhi")
TYPHOID_TEST_MARKERS = ("widal", "typhidot", "blood culture", "salmonella")


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


def _symptom_names(clinical_context: dict[str, Any] | None) -> list[str]:
    if not clinical_context:
        return []
    names: list[str] = []
    for item in clinical_context.get("symptoms") or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _test_results(clinical_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not clinical_context:
        return []
    return [
        item
        for item in (clinical_context.get("test_results") or [])
        if isinstance(item, dict)
    ]


def _has_clinical_data(clinical_context: dict[str, Any] | None) -> bool:
    return bool(_symptom_names(clinical_context) or _test_results(clinical_context))


def _contains_marker(text: str, markers: tuple[str, ...]) -> bool:
    normalized = _normalize_name(text)
    return any(marker in normalized for marker in markers)


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
                "category": "prescription",
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


def _rule_based_clinical_flags(
    diagnosis: str,
    clinical_context: dict[str, Any] | None,
    prescription_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not clinical_context:
        return []

    flags: list[dict[str, Any]] = []
    diagnosis_norm = _normalize_name(diagnosis)
    results = _test_results(clinical_context)
    rx_names = _collect_item_names(prescription_items or [])

    if any(marker in diagnosis_norm for marker in MALARIA_MARKERS):
        for result in results:
            test_name = _normalize_name(str(result.get("test_name") or ""))
            if not any(marker in test_name for marker in MALARIA_TEST_MARKERS):
                continue
            qualitative = str(result.get("result") or "").lower()
            if qualitative == "negative":
                flags.append(
                    {
                        "type": "DIAGNOSIS_TEST_MISMATCH",
                        "severity": "HIGH",
                        "item": diagnosis,
                        "category": "diagnosis",
                        "reason": (
                            f"Diagnosis is '{diagnosis}' but "
                            f"{result.get('test_name')} is reported negative."
                        ),
                        "recommendation": (
                            "Ask the clinician to reconcile the diagnosis with the "
                            "negative malaria test result using standard diagnostic criteria."
                        ),
                        "stg_reference": None,
                    }
                )
                break

    if any(marker in diagnosis_norm for marker in TYPHOID_MARKERS):
        for result in results:
            test_name = _normalize_name(str(result.get("test_name") or ""))
            if not any(marker in test_name for marker in TYPHOID_TEST_MARKERS):
                continue
            qualitative = str(result.get("result") or "").lower()
            if qualitative == "negative":
                flags.append(
                    {
                        "type": "DIAGNOSIS_TEST_MISMATCH",
                        "severity": "HIGH",
                        "item": diagnosis,
                        "category": "diagnosis",
                        "reason": (
                            f"Diagnosis is '{diagnosis}' but "
                            f"{result.get('test_name')} is reported negative."
                        ),
                        "recommendation": (
                            "Ask the clinician to reconcile the typhoid diagnosis "
                            "with the negative serological or culture result."
                        ),
                        "stg_reference": None,
                    }
                )
                break

    if any(marker in diagnosis_norm for marker in DENGUE_MARKERS):
        dengue_evidence = any(
            _contains_marker(str(result.get("test_name") or ""), DENGUE_TEST_MARKERS)
            and str(result.get("result") or "").lower() in {"positive", "low", "high"}
            for result in results
        ) or any(
            _contains_marker(name, DENGUE_MARKERS)
            for name in _symptom_names(clinical_context)
        )
        if dengue_evidence:
            for rx_name in rx_names:
                rx_norm = _normalize_name(rx_name)
                if not any(abx in rx_norm for abx in ANTIBIOTIC_MARKERS):
                    continue
                if "doxycycline" in rx_norm and "leptospirosis" not in diagnosis_norm:
                    continue
                flags.append(
                    {
                        "type": "NOT_INDICATED_MEDICINE",
                        "severity": "MEDIUM",
                        "item": rx_name,
                        "category": "prescription",
                        "reason": (
                            f"'{rx_name}' is prescribed for '{diagnosis}' without "
                            "documented bacterial coinfection evidence."
                        ),
                        "recommendation": (
                            "Ask your doctor whether antibiotics are needed. For dengue, "
                            "antibiotics are usually not given unless there is clear "
                            "evidence of a bacterial infection."
                        ),
                        "stg_reference": None,
                    }
                )
                break

    return flags


def _compute_risk_level(flags: list[dict[str, Any]]) -> str:
    actionable = [
        flag
        for flag in flags
        if flag.get("type")
        not in {"INSUFFICIENT_STG_EVIDENCE", "INSUFFICIENT_CLINICAL_DATA"}
    ]
    if not actionable:
        return "LOW"
    if any(flag.get("severity") == "HIGH" for flag in actionable) or len(actionable) >= 3:
        return "HIGH"
    return "MEDIUM"


_USER_FACING_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"review and revise prescription according to stg guidelines?",
            re.IGNORECASE,
        ),
        (
            "Ask your doctor whether this medicine is necessary for your condition "
            "and whether a simpler or standard alternative is available."
        ),
    ),
    (
        re.compile(
            r"conduct necessary investigations as per stg guidelines?",
            re.IGNORECASE,
        ),
        (
            "Ask your doctor which tests are needed to confirm the diagnosis "
            "before starting or continuing treatment."
        ),
    ),
    (re.compile(r"\bper stg\b", re.IGNORECASE), "per government treatment guidelines"),
    (
        re.compile(r"\baccording to stg\b", re.IGNORECASE),
        "based on government treatment guidelines",
    ),
    (re.compile(r"\bstg criteria\b", re.IGNORECASE), "standard diagnostic criteria"),
    (re.compile(r"\bstg guidelines?\b", re.IGNORECASE), "government treatment guidelines"),
)


def _polish_user_facing_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned
    for pattern, replacement in _USER_FACING_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned.strip()


def _polish_flags_for_users(
    flags: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    polished: list[dict[str, Any]] = []
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        item = dict(flag)
        item["reason"] = _polish_user_facing_text(item.get("reason") or "")
        item["recommendation"] = _polish_user_facing_text(item.get("recommendation") or "")
        basis = sanitize_display_text(str(item.get("guideline_basis") or ""))
        if basis:
            item["guideline_basis"] = _polish_user_facing_text(basis)
        elif chunks:
            support = _find_supporting_chunk(item, chunks)
            if support:
                item["guideline_basis"] = format_guideline_basis(support)
        polished.append(item)
    return polished


_TRIANGLE_AUDIT_SYSTEM = """
You are reviewing a clinical case against India's government treatment guidelines
(ICMR, Clinical Establishments Act STG, and CRC Standard Treatment Guidelines fallback).

The reader is a patient or caregiver who does NOT have access to guideline documents.
Write reasons and recommendations they can act on immediately.

Return ONLY valid JSON with this shape:
{
  "clinical_alignment": {
    "diagnosis_supported": true or false or null,
    "supporting_evidence": ["string"],
    "missing_evidence": ["string"]
  },
  "flags": [
    {
      "type": "DIAGNOSIS_UNSUPPORTED|DIAGNOSIS_TEST_MISMATCH|MISSING_REQUIRED_INVESTIGATION|PRESCRIPTION_CLINICAL_MISMATCH|UNNECESSARY_TEST|UNNECESSARY_PROCEDURE|NOT_INDICATED_MEDICINE|EXCESSIVE_WORKUP|PRESCRIBED_NOT_IN_STG|INSUFFICIENT_STG_EVIDENCE",
      "severity": "MEDIUM|HIGH",
      "item": "string",
      "category": "diagnosis|investigation|prescription",
      "reason": "string",
      "recommendation": "string",
      "guideline_basis": "string",
      "stg_reference": {
        "condition": "string",
        "section": "string",
        "page": number or null
      }
    }
  ]
}

Rules:
- Evaluate the TRIANGLE: diagnosis vs symptoms/test results vs prescription/bill items.
- Base every flag on the supplied guideline excerpts only.
- Reasons must explain the clinical concern in plain language.
- Recommendations must be concrete actions for the patient, for example:
  "Ask your doctor whether antibiotics are needed for a viral URTI" or
  "Request a malaria RDT before starting antimalarial treatment".
- Use neutral, guideline-based phrasing in reasons. Examples:
  "For uncomplicated dengue, the following tests are not routinely recommended under the guideline."
  "Guideline support for MRI in this clinical scenario was not identified."
- Do not write that the doctor ordered unnecessary tests or that the prescription is wrong.
- Every flag MUST include guideline_basis: one short plain-language sentence
  explaining what the government guidelines say about this issue. Write at an
  8th-grade reading level. No section numbers, no symbols, no jargon, no quotes
  from the document, and no instruction to read guideline documents.
  Example: "Most colds and throat infections are caused by viruses, so
  antibiotics are usually not needed."
- NEVER tell the user to read, review, or consult STG documents.
- NEVER use vague recommendations like "revise per STG" or "follow STG guidelines".
- Every flag MUST include stg_reference when citing a guideline excerpt.
- Do not claim fraud; use guideline-based language.
- If clinical data is empty, set diagnosis_supported=null and avoid diagnosis-specific flags.
- Do not emit INSUFFICIENT_STG_EVIDENCE unless truly unable to decide.
""".strip()


def _groq_triangle_audit(
    *,
    diagnosis: str,
    diagnosis_user_provided: bool,
    symptoms: list[str],
    test_results: list[dict[str, Any]],
    prescription_items: list[str],
    bill_items: list[str],
    context_text: str,
    matched_conditions: list[str],
    retrieval_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    user = f"""
Diagnosis: {diagnosis}
Diagnosis user-provided: {diagnosis_user_provided}
Matched government guideline topics: {json.dumps(matched_conditions)}

Symptoms:
{json.dumps(symptoms, ensure_ascii=False)}

Test results:
{json.dumps(test_results, ensure_ascii=False)}

Prescribed / ordered items:
{json.dumps(prescription_items, ensure_ascii=False)}

Billed items (optional):
{json.dumps(bill_items, ensure_ascii=False)}

Government guideline excerpts (ICMR / Clinical Establishments / CRC STG fallback):
{context_text}
""".strip()

    parsed = groq_json_chat(_TRIANGLE_AUDIT_SYSTEM, user, max_tokens=3000)
    flags = parsed.get("flags") or []
    if not isinstance(flags, list):
        flags = []
    alignment = parsed.get("clinical_alignment") or {}
    if not isinstance(alignment, dict):
        alignment = {}
    flags = validate_stg_citations(flags, retrieval_chunks)
    flags = _polish_flags_for_users(flags, retrieval_chunks)
    return {"flags": flags, "clinical_alignment": alignment}


def analyze_treatment(
    *,
    diagnosis: str,
    prescription_items: list[dict[str, Any]] | None = None,
    bill_items: list[dict[str, Any]] | None = None,
    clinical_context: dict[str, Any] | None = None,
    diagnosis_user_provided: bool = False,
    diagnosis_confidence: str | None = None,
) -> dict[str, Any]:
    diagnosis = str(diagnosis or "").strip()
    if not diagnosis:
        raise HTTPException(status_code=400, detail="Diagnosis is required.")

    prescription_items = prescription_items or []
    bill_items = bill_items or []
    clinical_context = clinical_context or {}

    rx_names = _collect_item_names(prescription_items)
    bill_names = _collect_item_names(bill_items)
    all_items = list(dict.fromkeys(rx_names + bill_names))
    symptoms = _symptom_names(clinical_context)
    test_results = _test_results(clinical_context)

    retrieval = retrieve_stg_context(
        diagnosis,
        all_items,
        symptoms=symptoms,
        test_results=test_results,
    )
    matched_conditions = retrieval.get("matched_conditions") or []
    context_text = retrieval.get("context_text") or ""
    retrieval_chunks = retrieval.get("chunks") or []

    flags: list[dict[str, Any]] = []
    flags.extend(_rule_based_bill_prescription_flags(bill_items, prescription_items))
    flags.extend(
        _rule_based_clinical_flags(
            diagnosis,
            clinical_context,
            prescription_items=prescription_items,
        )
    )

    flags.extend(
        analyze_prescription_rationality(
            diagnosis=diagnosis,
            prescription_items=prescription_items,
        )
    )

    investigation_items = [
        str(item.get("name") or item.get("item_name") or "").strip()
        for item in prescription_items + bill_items
        if isinstance(item, dict)
        and str(item.get("category") or "").lower() in {"test", "procedure", "investigation"}
        and str(item.get("name") or item.get("item_name") or "").strip()
    ]
    investigation_items = list(dict.fromkeys(investigation_items))
    flagged_norms = {
        _normalize_name(str(flag.get("item") or ""))
        for flag in flags
        if flag.get("item")
    }
    flags.extend(
        analyze_investigations(
            diagnosis=diagnosis,
            investigation_items=investigation_items,
            retrieval_chunks=retrieval_chunks,
            flagged_item_norms=flagged_norms,
        )
    )

    clinical_alignment: dict[str, Any] = {
        "diagnosis_supported": None,
        "supporting_evidence": [],
        "missing_evidence": [],
    }

    if not _has_clinical_data(clinical_context):
        flags.append(
            {
                "type": "INSUFFICIENT_CLINICAL_DATA",
                "severity": "MEDIUM",
                "item": diagnosis,
                "category": "diagnosis",
                "reason": (
                    "No symptoms or test results were provided, so diagnosis support "
                    "could not be fully assessed against government treatment guidelines."
                ),
                "recommendation": (
                    "Add symptoms and lab results for a stronger clinical triangle check."
                ),
                "stg_reference": None,
            }
        )

    if context_text:
        audit_result = _groq_triangle_audit(
            diagnosis=diagnosis,
            diagnosis_user_provided=diagnosis_user_provided,
            symptoms=symptoms,
            test_results=test_results,
            prescription_items=rx_names,
            bill_items=bill_names,
            context_text=context_text,
            matched_conditions=matched_conditions,
            retrieval_chunks=retrieval_chunks,
        )
        clinical_alignment = audit_result.get("clinical_alignment") or clinical_alignment
        for flag in audit_result.get("flags") or []:
            if not isinstance(flag, dict):
                continue
            if flag.get("type") == "INSUFFICIENT_STG_EVIDENCE":
                continue
            if not flag.get("category"):
                flag_type = str(flag.get("type") or "")
                if flag_type.startswith("DIAGNOSIS"):
                    flag["category"] = "diagnosis"
                elif "INVESTIGATION" in flag_type or "TEST" in flag_type:
                    flag["category"] = "investigation"
                else:
                    flag["category"] = "prescription"
            flags.append(flag)
        flags = _polish_flags_for_users(flags, retrieval_chunks)
    elif not matched_conditions:
        flags.append(
            {
                "type": "INSUFFICIENT_STG_EVIDENCE",
                "severity": "MEDIUM",
                "item": diagnosis,
                "category": "diagnosis",
                "reason": (
                    f"Could not map diagnosis '{diagnosis}' to a condition in the "
                    "government treatment guidelines index."
                ),
                "recommendation": (
                    "Confirm the diagnosis spelling or choose a closer condition name."
                ),
                "stg_reference": None,
            }
        )

    flags = finalize_audit_flags(flags, chunks=retrieval_chunks)

    if str(diagnosis_confidence or "").lower() in {"low", "missing"}:
        for flag in flags:
            if flag.get("confidence") == "HIGH":
                flag["confidence"] = "MEDIUM"

    advocacy = build_advocacy_payload(flags, chunks=retrieval_chunks)

    return {
        "flags_count": advocacy["flags_count"],
        "risk_level": _compute_risk_level(advocacy["flags"]),
        "matched_stg_conditions": matched_conditions,
        "clinical_alignment": clinical_alignment,
        "guideline_sources": retrieval.get("guideline_sources") or [],
        "used_fallback": bool(retrieval.get("used_fallback")),
        "flags": advocacy["flags"],
        "patient_questions": advocacy["patient_questions"],
        "advocacy_scope": advocacy["advocacy_scope"],
        "diagnosis_confidence": diagnosis_confidence,
    }
