"""Rule-based audit for suspicious or unnecessary hospital bill charges."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

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

PACKAGE_KEYWORDS = ("package", "surgery", "procedure", "operation")
COMPONENT_KEYWORDS = (
    "anaesthesia",
    "anesthesia",
    "operation theatre",
    "operation theater",
    "assistant surgeon",
    "surgeon",
    "consumables",
    "consumable",
)
LAB_KEYWORDS = (
    "blood",
    "sample",
    "cbc",
    "urine",
    "test",
    "lab",
    "xray",
    "x-ray",
    "scan",
)
SURGERY_KEYWORDS = ("surgery", "procedure", "package", "operation")

SIMILARITY_THRESHOLD = 0.85
REPETITION_THRESHOLD = 2


def normalize_description(text: str) -> str:
    lowered = text.lower()
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    tokens = [token for token in cleaned.split() if token and token not in FILLER_WORDS]
    return " ".join(tokens)


def _item_name(item: dict[str, Any]) -> str:
    return str(
        item.get("item_name") or item.get("description") or item.get("name") or ""
    ).strip()


def _item_quantity(item: dict[str, Any]) -> float:
    try:
        value = item.get("quantity")
        if value is None:
            return 1.0
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return 1.0


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = normalize_description(text)
    if not normalized:
        return False

    for keyword in keywords:
        if " " in keyword:
            if keyword in normalized:
                return True
            continue
        if re.search(rf"\b{re.escape(keyword)}\b", normalized):
            return True
    return False


def _is_surgery_like(entry: dict[str, Any]) -> bool:
    if entry["category"] == "procedure":
        return True
    return _contains_keyword(entry["name"], SURGERY_KEYWORDS)


def _is_lab_like(entry: dict[str, Any]) -> bool:
    if entry["category"] == "test":
        return True
    return _contains_keyword(entry["name"], LAB_KEYWORDS)


def _compute_risk_level(flags: list[dict[str, str]]) -> str:
    if not flags:
        return "LOW"
    if any(flag["severity"] == "HIGH" for flag in flags) or len(flags) >= 3:
        return "HIGH"
    return "MEDIUM"


def _similar_count(entries: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    current = entries[index]
    if not current["norm"]:
        return [current]

    cluster = [current]
    for other_index, other in enumerate(entries):
        if other_index == index or not other["norm"]:
            continue
        if current["norm"] == other["norm"] or _similarity(
            current["norm"], other["norm"]
        ) >= SIMILARITY_THRESHOLD:
            cluster.append(other)
    return cluster


def analyze_claim_items(
    items: list[dict[str, Any]],
    city: str | None = None,
) -> dict[str, Any]:
    del city  # Reserved for future city-specific audit rules.

    if not items:
        return {"flags_count": 0, "risk_level": "LOW", "flags": []}

    entries: list[dict[str, Any]] = []
    for item in items:
        name = _item_name(item)
        entries.append(
            {
                "item": item,
                "name": name or "Unknown item",
                "norm": normalize_description(name),
                "qty": _item_quantity(item),
                "category": str(item.get("category") or "").lower(),
            }
        )

    flags: list[dict[str, str]] = []
    flagged_norms: set[str] = set()
    flagged_pairs: set[tuple[str, str]] = set()
    flagged_surgery_clusters: set[frozenset[str]] = set()
    flagged_lab_norms: set[str] = set()

    norm_groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if entry["norm"]:
            norm_groups.setdefault(entry["norm"], []).append(entry)

    for norm, group in norm_groups.items():
        if len(group) < 2:
            continue
        total_qty = sum(entry["qty"] for entry in group)
        display_name = group[0]["name"]
        severity = "HIGH" if len(group) > REPETITION_THRESHOLD or total_qty > REPETITION_THRESHOLD else "MEDIUM"
        flags.append(
            {
                "type": "DUPLICATE_ITEM",
                "severity": severity,
                "item": display_name,
                "reason": (
                    f'This item appears {len(group)} times on the bill '
                    f"(total quantity: {total_qty:g})."
                ),
                "recommendation": "Ask hospital for justification or supporting prescription.",
            }
        )
        flagged_norms.add(norm)

    for left_index, left in enumerate(entries):
        if not left["norm"]:
            continue
        for right in entries[left_index + 1 :]:
            if not right["norm"] or left["norm"] == right["norm"]:
                continue
            score = _similarity(left["norm"], right["norm"])
            if score < SIMILARITY_THRESHOLD:
                continue
            pair_key = tuple(sorted((left["norm"], right["norm"])))
            if pair_key in flagged_pairs:
                continue
            flagged_pairs.add(pair_key)
            flags.append(
                {
                    "type": "NEAR_DUPLICATE_ITEM",
                    "severity": "MEDIUM",
                    "item": left["name"],
                    "reason": (
                        f'Similar to "{right["name"]}" '
                        f"(possible duplicate spelling, {score:.0%} match)."
                    ),
                    "recommendation": "Verify these are distinct services and not double-billed.",
                }
            )

    for index, entry in enumerate(entries):
        if not _is_surgery_like(entry):
            continue

        cluster = _similar_count(entries, index)
        cluster_key = frozenset(member["norm"] or member["name"] for member in cluster)
        if cluster_key in flagged_surgery_clusters:
            continue

        occurrence_count = len(cluster)
        total_qty = sum(member["qty"] for member in cluster)
        if occurrence_count <= REPETITION_THRESHOLD and total_qty <= REPETITION_THRESHOLD:
            continue

        if entry["norm"] in flagged_norms and occurrence_count == len(
            norm_groups.get(entry["norm"], [])
        ):
            continue

        flagged_surgery_clusters.add(cluster_key)
        severity = "HIGH" if total_qty > REPETITION_THRESHOLD else "MEDIUM"
        flags.append(
            {
                "type": "UNREALISTIC_REPETITION",
                "severity": severity,
                "item": entry["name"],
                "reason": (
                    f"This surgery/procedure appears {occurrence_count} time(s) "
                    f"with total quantity {total_qty:g}, which is unusually high."
                ),
                "recommendation": "Ask hospital for justification or supporting prescription.",
            }
        )

    lab_norm_groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if _is_lab_like(entry) and entry["norm"]:
            lab_norm_groups.setdefault(entry["norm"], []).append(entry)

    for norm, group in lab_norm_groups.items():
        if norm in flagged_norms:
            continue
        if norm in flagged_lab_norms:
            continue

        occurrence_count = len(group)
        total_qty = sum(member["qty"] for member in group)
        if occurrence_count <= REPETITION_THRESHOLD and total_qty <= REPETITION_THRESHOLD:
            continue

        flagged_lab_norms.add(norm)
        severity = "HIGH" if total_qty > REPETITION_THRESHOLD else "MEDIUM"
        flags.append(
            {
                "type": "LAB_REPETITION",
                "severity": severity,
                "item": group[0]["name"],
                "reason": (
                    f"Lab/sample/test item appears {occurrence_count} time(s) "
                    f"with total quantity {total_qty:g}, which may be excessive."
                ),
                "recommendation": "Ask hospital for justification or supporting prescription.",
            }
        )

    package_items = [
        entry for entry in entries if _contains_keyword(entry["name"], PACKAGE_KEYWORDS)
    ]
    component_items = [
        entry
        for entry in entries
        if _contains_keyword(entry["name"], COMPONENT_KEYWORDS)
        or re.search(r"\bot\b", normalize_description(entry["name"]))
    ]

    if package_items and component_items:
        package_names = ", ".join(entry["name"] for entry in package_items[:3])
        component_names = ", ".join(entry["name"] for entry in component_items[:3])
        flags.append(
            {
                "type": "PACKAGE_COMPONENT_CHARGED_SEPARATELY",
                "severity": "HIGH",
                "item": package_names,
                "reason": (
                    "A package/surgery/procedure charge appears alongside separate "
                    f"component charges such as {component_names}."
                ),
                "recommendation": (
                    "Ask whether the package already includes OT, anaesthesia, surgeon, "
                    "or consumables before paying separately."
                ),
            }
        )

    return {
        "flags_count": len(flags),
        "risk_level": _compute_risk_level(flags),
        "flags": flags,
    }
