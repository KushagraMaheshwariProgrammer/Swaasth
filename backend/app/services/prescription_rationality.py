"""Prescription rationality: duplicate class, interactions, spectrum, brand-vs-generic."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.jan_aushadhi_rates import enrich_line_items_with_jan_aushadhi
from app.item_normalization import normalize_item_name
from app.pharma_rates import get_pharma_store
from app.services.patient_gender import resolve_patient_gender

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DRUG_RATIONALITY_PATH = _BACKEND_ROOT / "data" / "medicines" / "drug_rationality.json"

FILLER_WORDS = {"tablet", "tablets", "tab", "capsule", "capsules", "cap", "syrup", "inj", "injection"}


@lru_cache(maxsize=1)
def _load_rationality_data() -> dict[str, Any]:
    if not DRUG_RATIONALITY_PATH.exists():
        return {"drugs": [], "interactions": [], "condition_first_line_antibiotics": {}}
    return json.loads(DRUG_RATIONALITY_PATH.read_text(encoding="utf-8"))


def _normalize_drug_name(text: str) -> str:
    lowered = normalize_item_name(text)
    tokens = [token for token in lowered.split() if token not in FILLER_WORDS]
    return " ".join(tokens)


def _resolve_drug_entry(name: str, drugs: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized = _normalize_drug_name(name)
    if not normalized:
        return None

    for drug in drugs:
        candidates = [drug.get("name", "")] + list(drug.get("aliases") or [])
        for candidate in candidates:
            candidate_norm = _normalize_drug_name(str(candidate))
            if not candidate_norm:
                continue
            if candidate_norm == normalized or candidate_norm in normalized or normalized in candidate_norm:
                return {**drug, "matched_as": name}
    return None


def _medicine_names(prescription_items: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for item in prescription_items:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "medicine").lower()
        if category not in {"medicine", "drug", ""}:
            continue
        name = str(item.get("name") or item.get("item_name") or "").strip()
        if name:
            names.append(name)
    return names


def _duplicate_class_flags(
    resolved: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_class: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for name, drug in resolved:
        drug_class = str(drug.get("class") or "").strip()
        if not drug_class or drug_class in {"analgesic_antipyretic", "none"}:
            continue
        by_class.setdefault(drug_class, []).append((name, drug))

    flags: list[dict[str, Any]] = []
    for drug_class, group in by_class.items():
        if len(group) < 2:
            continue
        names = [entry[0] for entry in group]
        flags.append(
            {
                "type": "DUPLICATE_THERAPEUTIC_CLASS",
                "severity": "MEDIUM",
                "item": ", ".join(names[:3]),
                "category": "prescription",
                "reason": (
                    f"This prescription contains {len(group)} medicines from the same "
                    f"therapeutic class ({drug_class.replace('_', ' ')})."
                ),
                "recommendation": (
                    "Ask your treating doctor why multiple medicines from the same "
                    "class appear on this bill or prescription."
                ),
                "guideline_basis": None,
                "stg_reference": None,
            }
        )
    return flags


def _interaction_flags(resolved: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    data = _load_rationality_data()
    interactions = data.get("interactions") or []
    canonical: dict[str, str] = {}
    for name, drug in resolved:
        canonical[_normalize_drug_name(drug.get("name") or name)] = name

    flags: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for interaction in interactions:
        drug_a = _normalize_drug_name(str(interaction.get("drug_a") or ""))
        drug_b = _normalize_drug_name(str(interaction.get("drug_b") or ""))
        if not drug_a or not drug_b:
            continue
        if drug_a not in canonical or drug_b not in canonical:
            continue
        pair = tuple(sorted((drug_a, drug_b)))
        if pair in seen:
            continue
        seen.add(pair)
        display_a = canonical[drug_a]
        display_b = canonical[drug_b]
        note = str(interaction.get("note") or "Possible interaction")
        flags.append(
            {
                "type": "DRUG_INTERACTION",
                "severity": str(interaction.get("severity") or "MEDIUM"),
                "item": f"{display_a} + {display_b}",
                "category": "prescription",
                "reason": (
                    f"{display_a} and {display_b} are a known interaction pair: {note}."
                ),
                "recommendation": (
                    f"Ask your treating doctor or pharmacist to explain why "
                    f"{display_a} and {display_b} appear together on this prescription."
                ),
                "guideline_basis": None,
                "stg_reference": None,
            }
        )
    return flags


def _broader_spectrum_flags(
    diagnosis: str,
    resolved: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    data = _load_rationality_data()
    broad_values = set(data.get("broad_spectrum_values") or ["broad", "very_broad"])
    first_line_map: dict[str, list[str]] = data.get("condition_first_line_antibiotics") or {}
    diagnosis_norm = _normalize_drug_name(diagnosis)

    matched_first_line: list[str] | None = None
    for condition, antibiotics in first_line_map.items():
        if _normalize_drug_name(condition) in diagnosis_norm or diagnosis_norm in _normalize_drug_name(condition):
            matched_first_line = [str(item) for item in antibiotics]
            break

    flags: list[dict[str, Any]] = []
    for name, drug in resolved:
        spectrum = str(drug.get("spectrum") or "")
        if spectrum not in broad_values:
            continue
        if matched_first_line is not None and not matched_first_line:
            flags.append(
                {
                    "type": "BROADER_SPECTRUM_ANTIBIOTIC",
                    "severity": "MEDIUM",
                    "item": name,
                    "category": "prescription",
                    "reason": (
                        f"The prescribed antibiotic '{name}' is broader-spectrum than "
                        f"typically listed for {diagnosis} in common first-line references."
                    ),
                    "recommendation": (
                        "Ask your treating doctor why this broader-spectrum antibiotic "
                        "appears on the bill or prescription for the documented diagnosis."
                    ),
                    "guideline_basis": None,
                    "stg_reference": None,
                }
            )
            break
    return flags


def _brand_generic_flags(medicine_names: list[str]) -> list[dict[str, Any]]:
    try:
        store = get_pharma_store()
    except (FileNotFoundError, ValueError):
        return []

    if not store.az:
        return []

    flags: list[dict[str, Any]] = []
    for name in medicine_names:
        resolution = store.az.resolve(name)
        if not resolution:
            continue
        generic = str(resolution.get("generic_name") or resolution.get("composition") or "").strip()
        if not generic:
            continue
        brand_norm = _normalize_drug_name(name)
        generic_norm = _normalize_drug_name(generic)
        if generic_norm and generic_norm in brand_norm:
            continue

        jan_note = ""
        line_item = {"item_name": name, "category": "medicine"}
        enriched, _ = enrich_line_items_with_jan_aushadhi([line_item])
        if enriched and enriched[0].get("jan_aushadhi_available"):
            mrp = enriched[0].get("jan_aushadhi_mrp") or enriched[0].get("mrp")
            if mrp is not None:
                jan_note = f" A Jan Aushadhi generic may be available (MRP around ₹{mrp})."

        flags.append(
            {
                "type": "BRAND_WITHOUT_GENERIC_QUESTION",
                "severity": "MEDIUM",
                "item": name,
                "category": "prescription",
                "reason": (
                    f"'{name}' appears to be a branded medicine (generic: {generic})."
                    f"{jan_note}"
                ),
                "recommendation": (
                    f"Ask whether an equivalent generic ({generic}) is available and "
                    "whether it would be suitable for you."
                ),
                "guideline_basis": None,
                "stg_reference": None,
                "resolved_generic": generic,
            }
        )
    return flags


def _population_safety_flags(
    resolved: list[tuple[str, dict[str, Any]]],
    *,
    patient_age: int | None,
    patient_gender: str | None,
) -> list[dict[str, Any]]:
    if not resolved:
        return []

    flags: list[dict[str, Any]] = []
    gender = resolve_patient_gender(patient_gender)
    is_female = gender == "female"
    is_pregnant_context = is_female  # conservative: flag female-specific cautions for review

    for name, entry in resolved:
        note = str(entry.get("safety_note") or "").strip()
        if entry.get("avoid_in_pregnancy") and is_pregnant_context:
            flags.append(
                {
                    "type": "PREGNANCY_CONTRAINDICATION",
                    "severity": "HIGH",
                    "item": name,
                    "category": "prescription",
                    "reason": (
                        f"{name} is commonly avoided during pregnancy."
                        + (f" {note}" if note else "")
                    ),
                    "recommendation": (
                        f"Ask whether {name} is safe in your pregnancy stage or if a "
                        "pregnancy-compatible alternative is available."
                    ),
                    "guideline_basis": None,
                    "stg_reference": None,
                }
            )
            continue

        if entry.get("caution_in_pregnancy") and is_pregnant_context:
            flags.append(
                {
                    "type": "PREGNANCY_CAUTION",
                    "severity": "MEDIUM",
                    "item": name,
                    "category": "prescription",
                    "reason": (
                        f"{name} may need extra caution during pregnancy."
                        + (f" {note}" if note else "")
                    ),
                    "recommendation": (
                        f"Ask your doctor to confirm that {name} is appropriate for "
                        "pregnancy in your specific situation."
                    ),
                    "guideline_basis": None,
                    "stg_reference": None,
                }
            )

        if entry.get("avoid_in_lactation") and is_female:
            flags.append(
                {
                    "type": "LACTATION_CAUTION",
                    "severity": "MEDIUM",
                    "item": name,
                    "category": "prescription",
                    "reason": (
                        f"{name} may need caution while breastfeeding."
                        + (f" {note}" if note else "")
                    ),
                    "recommendation": (
                        f"If you are breastfeeding, ask whether {name} is suitable or "
                        "whether feeding timing or an alternative should be discussed."
                    ),
                    "guideline_basis": None,
                    "stg_reference": None,
                }
            )
        elif entry.get("caution_in_lactation") and is_female:
            flags.append(
                {
                    "type": "LACTATION_CAUTION",
                    "severity": "MEDIUM",
                    "item": name,
                    "category": "prescription",
                    "reason": (
                        f"{name} may need extra review while breastfeeding."
                        + (f" {note}" if note else "")
                    ),
                    "recommendation": (
                        f"Ask your treating doctor why {name} appears on the prescription "
                        "if you are breastfeeding."
                    ),
                    "guideline_basis": None,
                    "stg_reference": None,
                }
            )

        caution_age = entry.get("caution_under_age")
        if patient_age is not None and isinstance(caution_age, (int, float)):
            if patient_age < int(caution_age):
                flags.append(
                    {
                        "type": "PEDIATRIC_DOSING_CAUTION",
                        "severity": "HIGH" if patient_age < max(int(caution_age) - 4, 0) else "MEDIUM",
                        "item": name,
                        "category": "prescription",
                        "reason": (
                            f"{name} is often used cautiously in patients under "
                            f"{int(caution_age)} years (patient age recorded as {patient_age})."
                            + (f" {note}" if note else "")
                        ),
                        "recommendation": (
                            f"Ask whether the dose and choice of {name} are age-appropriate "
                            "for a child or adolescent."
                        ),
                        "guideline_basis": None,
                        "stg_reference": None,
                    }
                )

    return flags


def analyze_prescription_rationality(
    *,
    diagnosis: str,
    prescription_items: list[dict[str, Any]] | None = None,
    patient_age: int | None = None,
    patient_gender: str | None = None,
) -> list[dict[str, Any]]:
    prescription_items = prescription_items or []
    medicine_names = _medicine_names(prescription_items)
    if not medicine_names:
        return []

    data = _load_rationality_data()
    drugs = data.get("drugs") or []
    resolved: list[tuple[str, dict[str, Any]]] = []
    for name in medicine_names:
        entry = _resolve_drug_entry(name, drugs)
        if entry:
            resolved.append((name, entry))

    flags: list[dict[str, Any]] = []
    flags.extend(_duplicate_class_flags(resolved))
    flags.extend(_interaction_flags(resolved))
    if diagnosis.strip():
        flags.extend(_broader_spectrum_flags(diagnosis, resolved))
    flags.extend(_brand_generic_flags(medicine_names))
    flags.extend(
        _population_safety_flags(
            resolved,
            patient_age=patient_age,
            patient_gender=patient_gender,
        )
    )
    return flags
