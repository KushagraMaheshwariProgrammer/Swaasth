"""Rule-based lab result interpretation and abnormal-value flagging."""

from __future__ import annotations

import re
from typing import Any

from app.item_normalization import normalize_item_name

ABNORMAL_RESULTS = frozenset({"high", "low", "abnormal", "positive"})
NORMAL_RESULTS = frozenset({"normal", "negative"})

RANGE_PATTERN = re.compile(
    r"^\s*(?P<lower_op><|<=|≤)?\s*(?P<lower>[\d.]+)\s*(?:[-–—to]+\s*(?P<upper>[\d.]+)\s*(?P<upper_op><|<=|≤)?|(?P<upper_only_op><|<=|≤)\s*(?P<upper_only>[\d.]+))?\s*$",
    re.IGNORECASE,
)
SINGLE_BOUND_PATTERN = re.compile(
    r"^\s*(?P<op><|<=|≤|>|>=|≥)\s*(?P<value>[\d.]+)\s*$",
    re.IGNORECASE,
)


def _parse_numeric(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", "")
    if not cleaned:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _parse_reference_range(reference_range: str | None) -> dict[str, float | None] | None:
    text = str(reference_range or "").strip()
    if not text:
        return None

    normalized = text.lower().replace("upto", "up to")
    normalized = re.sub(r"\s+", " ", normalized)

    single = SINGLE_BOUND_PATTERN.match(normalized)
    if single:
        op = single.group("op")
        bound = _parse_numeric(single.group("value"))
        if bound is None:
            return None
        if op in {"<", "<=", "≤"}:
            return {"min": None, "max": bound}
        return {"min": bound, "max": None}

    match = RANGE_PATTERN.match(normalized)
    if match:
        lower = _parse_numeric(match.group("lower"))
        upper = _parse_numeric(match.group("upper") or match.group("upper_only"))
        return {"min": lower, "max": upper}

    between_match = re.match(
        r"^\s*(?P<lower>[\d.]+)\s*(?:[-–—]|to)\s*(?P<upper>[\d.]+)\s*$",
        normalized,
        re.IGNORECASE,
    )
    if between_match:
        return {
            "min": _parse_numeric(between_match.group("lower")),
            "max": _parse_numeric(between_match.group("upper")),
        }

    return None


def _compare_to_range(value: float, bounds: dict[str, float | None]) -> str | None:
    lower = bounds.get("min")
    upper = bounds.get("max")
    if lower is not None and value < lower:
        return "low"
    if upper is not None and value > upper:
        return "high"
    if lower is not None or upper is not None:
        return "normal"
    return None


def _plain_interpretation(test_name: str, status: str, value_text: str, range_text: str) -> tuple[str, str]:
    label = test_name or "Lab test"
    if status == "high":
        reason = (
            f"{label} is reported as high"
            + (f" ({value_text})" if value_text else "")
            + (f"; reference range is {range_text}." if range_text else ".")
        )
        recommendation = (
            f"Ask your doctor what the elevated {label} means for your diagnosis "
            "and whether any follow-up tests or treatment changes are needed."
        )
        return reason, recommendation

    if status == "low":
        reason = (
            f"{label} is reported as low"
            + (f" ({value_text})" if value_text else "")
            + (f"; reference range is {range_text}." if range_text else ".")
        )
        recommendation = (
            f"Ask your doctor whether the low {label} is expected for your condition "
            "or needs further evaluation."
        )
        return reason, recommendation

    reason = (
        f"{label} is reported as {status}"
        + (f" ({value_text})" if value_text else ".")
    )
    recommendation = (
        f"Ask your doctor to explain the {label} result and whether it supports "
        "the current diagnosis or treatment plan."
    )
    return reason, recommendation


def analyze_lab_results(test_results: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Return audit flags for abnormal or out-of-range lab values."""
    if not test_results:
        return []

    flags: list[dict[str, Any]] = []
    seen: set[str] = set()

    for result in test_results:
        if not isinstance(result, dict):
            continue
        test_name = str(result.get("test_name") or "").strip()
        if not test_name:
            continue

        norm_key = normalize_item_name(test_name)
        if norm_key in seen:
            continue

        value_text = str(result.get("value") or "").strip()
        unit = str(result.get("unit") or "").strip()
        range_text = str(result.get("reference_range") or "").strip()
        qualitative = str(result.get("result") or "").strip().lower()
        display_value = " ".join(part for part in [value_text, unit] if part).strip()

        status: str | None = None
        numeric_value = _parse_numeric(value_text)
        bounds = _parse_reference_range(range_text)

        if numeric_value is not None and bounds:
            status = _compare_to_range(numeric_value, bounds)
        elif qualitative in ABNORMAL_RESULTS:
            status = qualitative if qualitative != "positive" else "abnormal"
        elif qualitative in NORMAL_RESULTS:
            continue

        if not status or status == "normal":
            continue

        seen.add(norm_key)
        reason, recommendation = _plain_interpretation(
            test_name,
            status,
            display_value,
            range_text,
        )
        severity = "HIGH" if status in {"high", "low", "abnormal"} else "MEDIUM"
        flags.append(
            {
                "type": "ABNORMAL_LAB_VALUE",
                "severity": severity,
                "item": test_name,
                "category": "diagnosis",
                "reason": reason,
                "recommendation": recommendation,
                "guideline_basis": None,
                "stg_reference": None,
                "lab_status": status,
                "lab_value": display_value or None,
                "reference_range": range_text or None,
            }
        )

    return flags
