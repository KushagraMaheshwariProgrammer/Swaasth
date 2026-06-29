"""Hospital tier / type helpers and shared bill-item name normalization."""

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

TIER_KEYS: dict[str, str] = {
    "tier_1": "Tier I (X City)",
    "tier_i": "Tier I (X City)",
    "1": "Tier I (X City)",
    "tier_2": "Tier II (Y City)",
    "tier_ii": "Tier II (Y City)",
    "2": "Tier II (Y City)",
    "tier_3": "Tier III (Z City)",
    "tier_iii": "Tier III (Z City)",
    "3": "Tier III (Z City)",
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


def resolve_tier(tier: str | None) -> str:
    if not tier:
        return TIER_KEYS["tier_1"]
    key = tier.strip().lower().replace(" ", "_")
    if key in TIER_KEYS:
        return TIER_KEYS[key]
    for canonical in TIER_KEYS.values():
        if tier.strip().lower() == canonical.lower():
            return canonical
    raise ValueError(
        f"Invalid tier '{tier}'. Use tier_1, tier_2, or tier_3 "
        "(Tier I/II/III cities)."
    )


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
