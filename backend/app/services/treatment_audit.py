"""STG-grounded informational clarifications (not clinical conclusions).

Compares uploaded documents — billed/prescribed items and documented case
details — against published government guideline excerpts to surface questions
for the treating doctor or hospital. Outputs are documentation, billing-
relevance, and guideline-listing findings only — not diagnosis, treatment
advice, or determinations of medical appropriateness.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from fastapi import HTTPException

from app.services.audit_advocacy import build_advocacy_payload, finalize_audit_flags
from app.services.azure_openai_client import azure_openai_json_chat
from app.services.clinical_history_relevance import filter_relevant_clinical_history
from app.services.investigation_audit import analyze_investigations
from app.services.investigation_history_audit import analyze_repeat_investigations
from app.services.lab_interpretation import analyze_lab_results
from app.services.legal_guardrails import (
    CLINICAL_FINDING_DISCLAIMER,
    CLINICAL_SECTION_DISCLAIMER,
    DISCUSS_WITH_DOCTOR,
)
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
UTI_MARKERS = ("uti", "urinary tract infection", "cystitis")
ADVANCED_IMAGING_MARKERS = ("ct", "mri", "computed tomography", "magnetic resonance")
DIABETES_MARKERS = ("diabetes", "diabetic", "type 2 diabetes", "type ii diabetes")
INFECTION_MARKERS = (
    "infection",
    "sepsis",
    "cellulitis",
    "pneumonia",
    "abscess",
    "urinary tract infection",
    "uti",
)
GLUCOSE_TEST_MARKERS = ("glucose", "sugar", "hba1c", "ketone")


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


def _prescription_items_for_audit(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").lower()
        if category not in {"medicine", "drug", "test", "procedure", "investigation", ""}:
            if item.get("item_name"):
                category = "other"
            else:
                continue
        name = str(
            item.get("item_name")
            or item.get("name")
            or item.get("description")
            or ""
        ).strip()
        if not name:
            continue
        payload: dict[str, Any] = {"name": name}
        if category:
            payload["category"] = category
        for field in ("dose", "frequency", "duration"):
            value = str(item.get(field) or "").strip()
            if value:
                payload[field] = value
        audited.append(payload)
    return audited


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
    filtered_history: dict[str, Any] | None = None,
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
                            f"Uploaded records list diagnosis '{diagnosis}' while "
                            f"{result.get('test_name')} is reported negative. Ask your "
                            "treating doctor how these were reconciled."
                        ),
                        "recommendation": (
                            "Ask your treating doctor how the malaria diagnosis was "
                            "documented given the negative malaria test on file."
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
                            f"Uploaded records list diagnosis '{diagnosis}' while "
                            f"{result.get('test_name')} is reported negative. Ask your "
                            "treating doctor how these were reconciled."
                        ),
                        "recommendation": (
                            "Ask your treating doctor how the typhoid diagnosis was "
                            "documented given the negative serological or culture result."
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
                            f"'{rx_name}' appears for '{diagnosis}' without documented "
                            "bacterial coinfection in the uploaded records — worth "
                            "confirming for billing and documentation clarity."
                        ),
                        "recommendation": (
                            "Ask your treating doctor why this antibiotic was prescribed "
                            "for this dengue case and whether a bacterial coinfection "
                            "was documented."
                        ),
                        "stg_reference": None,
                    }
                )
                break

    if any(marker in diagnosis_norm for marker in UTI_MARKERS):
        for item_name in rx_names:
            item_norm = _normalize_name(item_name)
            if not any(marker in item_norm for marker in ADVANCED_IMAGING_MARKERS):
                continue
            flags.append(
                {
                    "type": "EXCESSIVE_WORKUP",
                    "severity": "MEDIUM",
                    "item": item_name,
                    "category": "investigation",
                    "reason": (
                        f"'{item_name}' is listed for '{diagnosis}'. Advanced imaging "
                        "is often a billing-clarification point unless complicated UTI "
                        "features are documented on the records."
                    ),
                    "recommendation": (
                        "Ask your treating doctor what documented reason required this "
                        "imaging for the billed UTI case (for example obstruction, stone, "
                        "or recurrent infection)."
                    ),
                    "stg_reference": None,
                }
            )
            break

    if filtered_history and rx_names:
        allergies = [
            str(item.get("name") or "").strip()
            for item in (filtered_history.get("profile") or {}).get("allergies") or []
            if str(item.get("name") or "").strip()
        ]
        for allergy in allergies:
            allergy_norm = _normalize_name(allergy)
            for rx_name in rx_names:
                rx_norm = _normalize_name(rx_name)
                if allergy_norm and (allergy_norm in rx_norm or _similarity(allergy_norm, rx_norm) >= 0.76):
                    flags.append(
                        {
                            "type": "PRESCRIPTION_CLINICAL_MISMATCH",
                            "severity": "HIGH",
                            "item": rx_name,
                            "category": "prescription",
                            "reason": (
                                f"The patient history lists allergy to '{allergy}', while "
                                f"'{rx_name}' appears in the current medicines."
                            ),
                            "recommendation": (
                                "Ask your treating doctor or pharmacist to confirm the allergy "
                                "history against this billed or prescribed medicine."
                            ),
                            "stg_reference": None,
                        }
                    )
                    break

        prior_medicines: list[str] = []
        for report in filtered_history.get("prior_reports") or []:
            if isinstance(report, dict):
                prior_medicines.extend(
                    str(name).strip()
                    for name in report.get("medicines") or []
                    if str(name).strip()
                )
        prior_norms = {_normalize_name(name) for name in prior_medicines}
        for rx_name in rx_names:
            rx_norm = _normalize_name(rx_name)
            if not any(abx in rx_norm for abx in ANTIBIOTIC_MARKERS):
                continue
            for prior_norm in prior_norms:
                if not any(abx in prior_norm for abx in ANTIBIOTIC_MARKERS):
                    continue
                if _similarity(rx_norm, prior_norm) >= 0.7:
                    flags.append(
                        {
                            "type": "PRESCRIPTION_CLINICAL_MISMATCH",
                            "severity": "MEDIUM",
                            "item": rx_name,
                            "category": "prescription",
                            "reason": (
                                f"'{rx_name}' matches a prior antibiotic from the "
                                "patient's recent history."
                            ),
                            "recommendation": (
                                "Ask your treating doctor why the same antibiotic class "
                                "appears again on this visit's bill or prescription."
                            ),
                            "stg_reference": None,
                        }
                    )
                    break

        history_conditions = [
            str(item.get("name") or "").strip()
            for item in (filtered_history.get("profile") or {}).get("conditions") or []
            if str(item.get("name") or "").strip()
        ]
        has_diabetes_history = any(
            any(marker in _normalize_name(condition) for marker in DIABETES_MARKERS)
            for condition in history_conditions
        )
        has_infection_context = any(marker in diagnosis_norm for marker in INFECTION_MARKERS)
        if has_diabetes_history and has_infection_context:
            current_test_names = [
                _normalize_name(str(result.get("test_name") or "")) for result in results
            ]
            rx_test_names = [
                _normalize_name(name)
                for name in rx_names
                if any(token in _normalize_name(name) for token in {"test", "glucose", "sugar", "hba1c"})
            ]
            has_glucose_review = any(
                any(marker in name for marker in GLUCOSE_TEST_MARKERS)
                for name in [*current_test_names, *rx_test_names]
            )
            if not has_glucose_review:
                flags.append(
                    {
                        "type": "MISSING_REQUIRED_INVESTIGATION",
                        "severity": "MEDIUM",
                        "item": "Blood glucose review",
                        "category": "investigation",
                        "reason": (
                            "The relevant patient history includes diabetes, and the current "
                            f"diagnosis is '{diagnosis}', but no glucose or HbA1c review is "
                            "visible in the uploaded data."
                        ),
                        "recommendation": (
                            "Ask your treating doctor whether a blood glucose review was "
                            "done or billed during this infection episode, given the "
                            "documented diabetes history."
                        ),
                        "stg_reference": None,
                    }
                )

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


def _normalize_clinical_alignment(alignment: dict[str, Any] | None) -> dict[str, Any]:
    """Map model/legacy alignment into a neutral tri-state plus a compatibility alias."""
    payload = dict(alignment or {})
    raw = payload.get("documents_consistent")
    if raw is None:
        raw = payload.get("diagnosis_supported")
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in {"true", "yes", "consistent"}:
            value = "yes"
        elif value in {"false", "no", "inconsistent", "unsupported"}:
            value = "unclear"
        elif value not in {"yes", "unclear", "not_assessable"}:
            value = "not_assessable"
    elif raw is True:
        value = "yes"
    elif raw is False:
        value = "unclear"
    else:
        value = "not_assessable"
    payload["documents_consistent"] = value
    payload["diagnosis_supported"] = (
        True if value == "yes" else False if value == "unclear" else None
    )
    payload.setdefault("supporting_evidence", [])
    payload.setdefault("missing_evidence", [])
    return payload


_USER_FACING_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"review and revise prescription according to stg guidelines?",
            re.IGNORECASE,
        ),
        (
            "Ask your treating doctor why this medicine appears on the bill or "
            "prescription for your documented condition."
        ),
    ),
    (
        re.compile(
            r"conduct necessary investigations as per stg guidelines?",
            re.IGNORECASE,
        ),
        (
            "Ask your treating doctor which tests were ordered for this billed case "
            "and how they relate to the documented diagnosis."
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


def _ensure_discuss_with_doctor(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return DISCUSS_WITH_DOCTOR
    lower = cleaned.lower()
    if ("discuss" in lower and "doctor" in lower) or "ask your doctor" in lower:
        return cleaned
    if "treating doctor" in lower or "ask the hospital" in lower:
        return cleaned
    if cleaned.endswith("."):
        return f"{cleaned} {DISCUSS_WITH_DOCTOR}"
    return f"{cleaned}. {DISCUSS_WITH_DOCTOR}"


def _polish_flags_for_users(
    flags: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    clinical_categories = {"diagnosis", "investigation", "prescription"}
    polished: list[dict[str, Any]] = []
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        item = dict(flag)
        item["reason"] = _polish_user_facing_text(item.get("reason") or "")
        recommendation = _polish_user_facing_text(item.get("recommendation") or "")
        category = str(item.get("category") or "").lower()
        if category in clinical_categories:
            recommendation = _ensure_discuss_with_doctor(recommendation)
            item["disclaimer"] = CLINICAL_FINDING_DISCLAIMER
        item["recommendation"] = recommendation
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
You help a patient or caregiver prepare INFORMATIONAL clarifications and
QUESTIONS TO DISCUSS WITH THE TREATING DOCTOR (and, where relevant, the hospital
for billing documentation).

You compare uploaded documents — stated diagnosis, symptoms/test results on file,
and prescription or bill items — against India's published government treatment
guideline excerpts (ICMR, Clinical Establishments Act STG, and CRC Standard
Treatment Guidelines fallback).

You do NOT diagnose, treat, prescribe, decide medical necessity, or judge whether
care was clinically appropriate. Never write clinical conclusions. Frame every
output as a possible question or documentation/billing clarification point.

The reader does NOT have access to guideline documents.
Write reasons as plain-language gaps. Write recommendations ONLY as questions or
requests to raise with the treating doctor (or hospital for bill documentation).

Return ONLY valid JSON with this shape:
{
    "clinical_alignment": {
    "documents_consistent": "yes or unclear or not_assessable",
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
- Compare the TRIANGLE of uploaded documents: stated diagnosis vs symptoms/test
  results on file vs prescription/bill items, using only the supplied guideline
  excerpts. Prefer billing/documentation relevance when a bill is present; when
  only clinical documents are present, still frame findings as questions for the
  treating doctor — never as care instructions.
- When patient age or sex is provided, use matching guideline excerpts only to
  flag clarification points (for example pediatric vs adult first-line listings).
  Do not decide what treatment the patient should receive.
- When prescription items include dose, frequency, or duration, note mismatches
  with guideline listings as questions for the treating doctor — never as dosing advice.
- Base every flag on the supplied guideline excerpts only.
- Reasons must describe a documentation, billing-relevance, or guideline-listing
  gap in plain language. Prefer phrasing like "not clearly documented", "not
  routinely listed in the guideline excerpts for this scenario", or "worth
  confirming with your doctor".
- Recommendations MUST be questions or requests for the treating doctor/hospital,
  for example:
  "Ask your treating doctor why this antibiotic appears on the bill for a viral URTI case"
  or "Ask the hospital for the clinical note that ordered this malaria medicine."
  Every recommendation must tell the reader to discuss the point with their doctor
  before changing any treatment, test, or medicine.
- Never tell the patient to start, stop, change, or avoid a medicine or test.
- Use neutral, guideline-based phrasing in reasons. Examples:
  "For uncomplicated dengue, the following tests are not routinely listed under the guideline excerpts."
  "Guideline support for MRI in this documented scenario was not identified in the excerpts."
- Do not write that the doctor ordered unnecessary tests, that the prescription is
  wrong, that treatment was inappropriate, or that a diagnosis is incorrect.
- clinical_alignment.documents_consistent is a clarification label only:
  "yes" if uploaded documents appear consistent with the stated diagnosis under
  the retrieved guideline excerpts; "unclear" if they do not clearly line up;
  "not_assessable" if there is not enough clinical documentation. It is not a
  medical diagnosis or finding. Never output a boolean.
- Every flag MUST include guideline_basis: one short plain-language sentence
  explaining what the government guideline excerpts say about this point. Write
  at an 8th-grade reading level. No section numbers, no symbols, no jargon, no
  quotes from the document, and no instruction to read guideline documents.
  Example: "Most colds and throat infections are caused by viruses, so
  antibiotics are usually not listed as routine care in the guideline excerpts."
- NEVER tell the user to read, review, or consult STG documents.
- NEVER use vague recommendations like "revise per STG" or "follow STG guidelines".
- Every flag MUST include stg_reference when citing a guideline excerpt.
- Do not claim fraud, negligence, or clinical error.
- If clinical data is empty, set documents_consistent="not_assessable" and avoid diagnosis-specific flags.
- Do not emit INSUFFICIENT_STG_EVIDENCE unless truly unable to decide.
""".strip()


def _ai_triangle_audit(
    *,
    diagnosis: str,
    diagnosis_user_provided: bool,
    symptoms: list[str],
    test_results: list[dict[str, Any]],
    prescription_items: list[dict[str, Any]],
    bill_items: list[str],
    context_text: str,
    matched_conditions: list[str],
    retrieval_chunks: list[dict[str, Any]],
    filtered_history: dict[str, Any] | None = None,
    patient_age: int | None = None,
    patient_birth_year: int | None = None,
    patient_gender: str | None = None,
) -> dict[str, Any]:
    history_block = ""
    if filtered_history and (
        filtered_history.get("included")
        or filtered_history.get("profile")
        or filtered_history.get("prior_reports")
        or filtered_history.get("legacy_documents")
    ):
        history_block = (
            "\n\nRelevant patient history:\n"
            f"{json.dumps(filtered_history, ensure_ascii=False)}"
        )

    age_block = ""
    if patient_age is not None or patient_birth_year is not None:
        age_block = (
            "\n\nPatient age context:\n"
            f"{json.dumps({'birth_year': patient_birth_year, 'approximate_age_years': patient_age}, ensure_ascii=False)}"
        )

    gender_block = ""
    if patient_gender:
        gender_block = (
            "\n\nPatient sex context:\n"
            f"{json.dumps({'gender': patient_gender}, ensure_ascii=False)}"
        )

    user = f"""
Diagnosis: {diagnosis}
Diagnosis user-provided: {diagnosis_user_provided}
Matched government guideline topics: {json.dumps(matched_conditions)}
{age_block}{gender_block}
Symptoms:
{json.dumps(symptoms, ensure_ascii=False)}

Test results:
{json.dumps(test_results, ensure_ascii=False)}

Prescribed / ordered items (include dose/frequency/duration when available):
{json.dumps(prescription_items, ensure_ascii=False)}

Billed items (optional):
{json.dumps(bill_items, ensure_ascii=False)}
{history_block}

Government guideline excerpts (ICMR / Clinical Establishments / CRC STG fallback):
{context_text}
""".strip()

    parsed = azure_openai_json_chat(_TRIANGLE_AUDIT_SYSTEM, user, max_tokens=3000)
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
    clinical_history: dict[str, Any] | None = None,
    patient_age: int | None = None,
    patient_birth_year: int | None = None,
    patient_gender: str | None = None,
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

    relevance_cache: dict[str, dict[str, Any]] = {}
    filtered_history = filter_relevant_clinical_history(
        diagnosis,
        symptoms,
        test_results,
        clinical_history,
        _cache=relevance_cache,
    )
    history_for_retrieval = {
        "profile": filtered_history.get("profile") or {},
        "prior_reports": filtered_history.get("prior_reports") or [],
        "legacy_documents": filtered_history.get("legacy_documents") or [],
    }

    retrieval = retrieve_stg_context(
        diagnosis,
        all_items,
        symptoms=symptoms,
        test_results=test_results,
        clinical_history=history_for_retrieval,
        patient_age=patient_age,
        patient_gender=patient_gender,
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
            filtered_history=filtered_history,
        )
    )
    flags.extend(analyze_lab_results(test_results))
    flags.extend(
        analyze_repeat_investigations(
            prescription_items=prescription_items,
            bill_items=bill_items,
            clinical_context=clinical_context,
            filtered_history=filtered_history,
        )
    )

    flags.extend(
        analyze_prescription_rationality(
            diagnosis=diagnosis,
            prescription_items=prescription_items,
            patient_age=patient_age,
            patient_gender=patient_gender,
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
        "documents_consistent": "not_assessable",
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
                    "No symptoms or test results were provided, so this bill or "
                    "prescription could not be fully compared with government "
                    "guideline excerpts for clarification questions."
                ),
                "recommendation": (
                    "Add symptoms and lab results from your records so we can "
                    "prepare clearer questions for your treating doctor or hospital."
                ),
                "stg_reference": None,
            }
        )

    if context_text:
        audit_result = _ai_triangle_audit(
            diagnosis=diagnosis,
            diagnosis_user_provided=diagnosis_user_provided,
            symptoms=symptoms,
            test_results=test_results,
            prescription_items=_prescription_items_for_audit(prescription_items),
            bill_items=bill_names,
            context_text=context_text,
            matched_conditions=matched_conditions,
            retrieval_chunks=retrieval_chunks,
            filtered_history=filtered_history,
            patient_age=patient_age,
            patient_birth_year=patient_birth_year,
            patient_gender=patient_gender,
        )
        clinical_alignment = _normalize_clinical_alignment(
            audit_result.get("clinical_alignment") or clinical_alignment
        )
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
                    "Confirm the diagnosis spelling with your doctor, or choose a "
                    "closer condition name."
                ),
                "stg_reference": None,
            }
        )

    flags = _polish_flags_for_users(flags, retrieval_chunks)
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
        "clinical_alignment": _normalize_clinical_alignment(clinical_alignment),
        "guideline_sources": retrieval.get("guideline_sources") or [],
        "used_fallback": bool(retrieval.get("used_fallback")),
        "flags": advocacy["flags"],
        "patient_questions": advocacy["patient_questions"],
        "advocacy_scope": advocacy["advocacy_scope"],
        "disclaimer": CLINICAL_SECTION_DISCLAIMER,
        "diagnosis_confidence": diagnosis_confidence,
        "clinical_history_used": filtered_history,
    }
