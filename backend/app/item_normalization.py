"""Shared bill-item name normalization and hospital type validation."""

from __future__ import annotations

import re

TERM_ALIASES: dict[str, str] = {
    "complete blood count": "cbc",
    "complete haemogram": "cbc",
    "complete hemogram": "cbc",
    "liver function test": "lft",
    "kidney function test": "kft",
    "renal function test": "kft",
    "erythrocyte sedimentation rate": "esr",
    "electrocardiogram": "ecg",
    "electroencephalogram": "eeg",
    "ultrasonography": "ultrasound",
    "usg": "ultrasound",
    "magnetic resonance imaging": "mri",
    "computed tomography": "ct scan",
    "operation theatre": "ot",
    "operation theater": "ot",
    "international normalized ratio": "inr",
    "activated partial thromboplastin time": "aptt",
    "prothrombin time": "pt",
    "glycated hemoglobin": "hba1c",
    "thyroid function test": "thyroid profile",
    "urine routine examination": "urine routine",
    "urine routine microscopy": "urine routine",
    "culture and sensitivity": "culture sensitivity",
    "xray": "x ray",
}

HOSPITAL_TYPE_KEYS: dict[str, str] = {
    "general": "general",
    "general_hospital": "general",
    "speciality": "speciality",
    "specialty": "speciality",
    "speciality_hospital": "speciality",
    "specialty_hospital": "speciality",
}


def normalize_item_name(item_name: str) -> str:
    normalized = item_name.lower().strip()
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = normalized.replace("&", " and ").replace("/", " ")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)

    for source, target in TERM_ALIASES.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)

    return re.sub(r"\s+", " ", normalized).strip()


def resolve_hospital_type(hospital_type: str | None) -> str:
    if not hospital_type:
        raise ValueError("hospital_type is required.")
    key = hospital_type.strip().lower().replace(" ", "_")
    if key in HOSPITAL_TYPE_KEYS:
        return HOSPITAL_TYPE_KEYS[key]
    raise ValueError(
        f"Invalid hospital_type '{hospital_type}'. "
        "Use general or speciality."
    )
