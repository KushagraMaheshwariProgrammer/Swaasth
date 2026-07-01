"""Gender applicability rules for Indian Standard Treatment Guidelines retrieval."""

from __future__ import annotations

import re
from typing import Any

from app.services.patient_gender import PatientGender, resolve_patient_gender

# Condition/chapter titles that apply to one sex only.
_FEMALE_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bpregnan",
        r"\bobstetric",
        r"\bgynaecolog",
        r"\bgynecolog",
        r"\bovarian\b",
        r"\buterine\b",
        r"\bvaginal\b",
        r"\bvulv",
        r"\bhyster",
        r"\bmenopause",
        r"\bmenstrual\b",
        r"\bmenorrhagia\b",
        r"\bpcos\b",
        r"polycystic ovarian",
        r"\bendometri",
        r"\bectopic preg",
        r"\babortion\b",
        r"\blactat",
        r"\bmtp\b",
        r"medical termination of pregnancy",
        r"\bcaesarean\b",
        r"\bcesarean\b",
        r"\bpre-?eclamps",
        r"\beclampsia\b",
        r"\bgestational\b",
        r"\bfoetal\b",
        r"\bfetal\b",
        r"\bpuerper",
        r"\bpostpartum\b",
        r"\bfemale urethral\b",
        r"cancer cervix",
        r"cervical cancer",
        r"carcinoma cerv",
        r"\bbreast cancer\b",
        r"carcinoma breast\b",
        r"\bbreast abscess\b",
        r"recurrent spontaneous abortion",
        r"drugs and pregnancy",
        r"drug use in lactating",
        r"abnormal uterine bleeding",
        r"operative vaginal delivery",
        r"vaginal discharge",
        r"bleeding in first trimester",
        r"post-?term pregnancy",
        r"diabetes in pregnancy",
        r"anaemia in pregnancy",
        r"anemia in pregnancy",
        r"urinary tract infection in pregnancy",
        r"hypertensive disorders of pregnancy",
        r"pregnancy with",
        r"nausea and vomiting in pregnancy",
    )
)

_MALE_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bprostate\b",
        r"\btesticular\b",
        r"\btestis\b",
        r"\bpenile\b",
        r"\bpenis\b",
        r"\bepididym",
        r"\bscrotal\b",
        r"\bscrotum\b",
        r"\borchitis\b",
        r"\bvaricocele\b",
        r"\bphimosis\b",
        r"\bbph\b",
        r"benign prostatic",
        r"\bmale urethral\b",
    )
)

# Anatomical "cervical" uses that are not gynaecological.
_NEUTRAL_TITLE_OVERRIDES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"cervical spondyl",
        r"cervical lymphadenopathy",
        r"cervical spine",
        r"cervical rib",
        r"cervical disc",
        r"cervical myelopathy",
    )
)

# Section-level signals inside mixed chapters (e.g. hypertension with pregnancy subsection).
_FEMALE_CONTENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bhypertension in pregnancy\b",
        r"\bin pregnant women\b",
        r"\bin pregnancy\b",
        r"\bfor pregnant\b",
        r"\bfemale urethral\b",
        r"\bfemale patient\b",
        r"\bwomen with\b",
        r"\bcontraindicated.{0,40}pregnan",
        r"\bacei.{0,40}contraindicated.{0,40}foet",
        r"\barbs?.{0,40}contraindicated",
        r"\bpre-?eclamps",
        r"\bgestational\b",
        r"\blactating mother",
    )
)

_MALE_CONTENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bprostate\b",
        r"\btesticular\b",
        r"\bpenile\b",
        r"\bmale urethral\b",
        r"\bscrotal\b",
        r"\bepididym",
        r"\bbenign prostatic\b",
        r"\bmale predominance\b",
        r"\bin men\b",
        r"\bfor men\b",
    )
)


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def infer_gender_applicability(
    label: str,
    *,
    chapter: str = "",
) -> frozenset[PatientGender] | None:
    """Return applicable sexes for a guideline topic, or None when both/neutral."""
    combined = f"{label} {chapter}".strip()
    if not combined:
        return None
    if _matches_any(combined, _NEUTRAL_TITLE_OVERRIDES):
        return None

    female = _matches_any(combined, _FEMALE_TITLE_PATTERNS)
    male = _matches_any(combined, _MALE_TITLE_PATTERNS)
    if female and not male:
        return frozenset({"female"})
    if male and not female:
        return frozenset({"male"})
    return None


def condition_applies_to_gender(
    condition: str,
    *,
    chapter: str = "",
    patient_gender: str | None,
) -> bool:
    gender = resolve_patient_gender(patient_gender)
    if gender is None:
        return True
    applicability = infer_gender_applicability(condition, chapter=chapter)
    if applicability is None:
        return True
    return gender in applicability


def chunk_applies_to_gender(
    chunk: dict[str, Any],
    patient_gender: str | None,
) -> bool:
    gender = resolve_patient_gender(patient_gender)
    if gender is None:
        return True

    condition = str(chunk.get("condition") or "")
    chapter = str(chunk.get("chapter") or "")
    if not condition_applies_to_gender(
        condition,
        chapter=chapter,
        patient_gender=patient_gender,
    ):
        return False

    text = str(chunk.get("text") or "")[:2500]
    if not text.strip():
        return True

    female_signal = _matches_any(text, _FEMALE_CONTENT_PATTERNS)
    male_signal = _matches_any(text, _MALE_CONTENT_PATTERNS)
    if female_signal and not male_signal:
        return gender == "female"
    if male_signal and not female_signal:
        return gender == "male"
    return True


def filter_conditions_by_gender(
    conditions: list[str],
    patient_gender: str | None,
    *,
    chapters_by_condition: dict[str, str] | None = None,
) -> list[str]:
    chapters = chapters_by_condition or {}
    return [
        condition
        for condition in conditions
        if condition_applies_to_gender(
            condition,
            chapter=chapters.get(condition, ""),
            patient_gender=patient_gender,
        )
    ]


def filter_chunks_by_gender(
    chunks: list[dict[str, Any]],
    patient_gender: str | None,
) -> list[dict[str, Any]]:
    return [chunk for chunk in chunks if chunk_applies_to_gender(chunk, patient_gender)]
