"""Birth year validation and approximate age derivation for patient context."""

from __future__ import annotations

from datetime import datetime

MIN_BIRTH_YEAR = 1900
MAX_AGE = 150


def current_year() -> int:
    return datetime.now().year


def validate_birth_year(birth_year: int | None) -> int | None:
    if birth_year is None:
        return None
    year = int(birth_year)
    current = current_year()
    if year < MIN_BIRTH_YEAR or year > current:
        raise ValueError(
            f"Birth year must be between {MIN_BIRTH_YEAR} and {current}."
        )
    return year


def derive_age_from_birth_year(birth_year: int | None) -> int | None:
    if birth_year is None:
        return None
    age = current_year() - int(birth_year)
    if 0 <= age <= MAX_AGE:
        return age
    return None


def resolve_patient_age(
    *,
    patient_age: int | None = None,
    patient_birth_year: int | None = None,
) -> int | None:
    derived = derive_age_from_birth_year(patient_birth_year)
    if derived is not None:
        return derived
    if patient_age is None:
        return None
    age = int(patient_age)
    if 0 <= age <= MAX_AGE:
        return age
    return None
