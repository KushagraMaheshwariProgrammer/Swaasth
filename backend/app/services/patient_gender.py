"""Patient gender normalization for clinical guideline context."""

from __future__ import annotations

from typing import Literal

PatientGender = Literal["male", "female"]

_GENDER_ALIASES: dict[str, PatientGender] = {
    "male": "male",
    "m": "male",
    "man": "male",
    "boy": "male",
    "female": "female",
    "f": "female",
    "woman": "female",
    "girl": "female",
}


def resolve_patient_gender(patient_gender: str | None) -> PatientGender | None:
    """Return canonical gender for guideline filtering, or None when unknown/unspecified."""
    if not patient_gender:
        return None
    normalized = str(patient_gender).strip().lower()
    if not normalized or normalized in {"other", "prefer_not_to_say", "unknown"}:
        return None
    return _GENDER_ALIASES.get(normalized)


def gender_display_label(patient_gender: str | None) -> str | None:
    """Human-readable gender label for LLM prompts."""
    resolved = resolve_patient_gender(patient_gender)
    if resolved == "male":
        return "male"
    if resolved == "female":
        return "female"
    if patient_gender and str(patient_gender).strip():
        return str(patient_gender).strip()
    return None
