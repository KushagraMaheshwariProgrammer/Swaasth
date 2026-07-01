"""Tests for patient age helpers."""

from __future__ import annotations

import pytest

from app.services.patient_age import (
    derive_age_from_birth_year,
    resolve_patient_age,
    validate_birth_year,
)


def test_derive_age_from_birth_year() -> None:
    current_year = derive_age_from_birth_year(2000)
    assert current_year is not None
    assert current_year >= 20


def test_resolve_patient_age_prefers_birth_year() -> None:
    birth_year = 2010
    expected = derive_age_from_birth_year(birth_year)
    assert resolve_patient_age(patient_age=40, patient_birth_year=birth_year) == expected


def test_validate_birth_year_rejects_future() -> None:
    with pytest.raises(ValueError):
        validate_birth_year(3000)


def test_validate_birth_year_accepts_plausible_year() -> None:
    assert validate_birth_year(1990) == 1990
