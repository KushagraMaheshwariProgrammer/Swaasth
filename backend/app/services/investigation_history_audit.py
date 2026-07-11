"""Detect repeat or recently duplicated investigations across prior visits."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from app.item_normalization import normalize_item_name

RECENT_WINDOW_DAYS = 14
STRONG_MATCH_THRESHOLD = 0.88
MIN_MATCH_THRESHOLD = 0.72

TEST_MARKERS = (
    "test",
    "lab",
    "profile",
    "panel",
    "scan",
    "xray",
    "x-ray",
    "mri",
    "ct",
    "usg",
    "ultrasound",
    "cbc",
    "lft",
    "kft",
    "rft",
    "culture",
    "serology",
    "biopsy",
    "ecg",
    "echo",
    "pathology",
    "investigation",
)


def _normalize_investigation_name(name: str) -> str:
    return normalize_item_name(name)


def _looks_like_investigation(name: str, category: str | None = None) -> bool:
    category_norm = str(category or "").lower()
    if category_norm in {"test", "procedure", "investigation"}:
        return True
    lowered = _normalize_investigation_name(name)
    return any(marker in lowered for marker in TEST_MARKERS)


def _names_match(current: str, prior: str) -> bool:
    left = _normalize_investigation_name(current)
    right = _normalize_investigation_name(prior)
    if not left or not right:
        return False
    if left == right:
        return True
    if left in right or right in left:
        return True
    return SequenceMatcher(None, left, right).ratio() >= STRONG_MATCH_THRESHOLD


def _parse_report_date(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _collect_current_investigations(
    prescription_items: list[dict[str, Any]] | None,
    bill_items: list[dict[str, Any]] | None,
    clinical_context: dict[str, Any] | None,
) -> list[str]:
    names: list[str] = []

    for item in prescription_items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("item_name") or "").strip()
        if name and _looks_like_investigation(name, item.get("category")):
            names.append(name)

    for item in bill_items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("item_name") or item.get("name") or "").strip()
        category = item.get("category")
        if name and _looks_like_investigation(name, category):
            names.append(name)

    for result in (clinical_context or {}).get("test_results") or []:
        if not isinstance(result, dict):
            continue
        name = str(result.get("test_name") or "").strip()
        if name:
            names.append(name)

    deduped: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = _normalize_investigation_name(name)
        if key and key not in seen:
            seen.add(key)
            deduped.append(name)
    return deduped


def _prior_investigations_from_history(
    filtered_history: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not filtered_history:
        return []

    entries: list[dict[str, Any]] = []
    for report in filtered_history.get("prior_reports") or []:
        if not isinstance(report, dict):
            continue
        report_date = _parse_report_date(str(report.get("date") or ""))
        for result in report.get("test_results") or []:
            if not isinstance(result, dict):
                continue
            name = str(result.get("test_name") or "").strip()
            if name:
                entries.append({"name": name, "date": report_date, "source": "prior_report"})
        for medicine in report.get("medicines") or []:
            name = str(medicine or "").strip()
            if name and _looks_like_investigation(name):
                entries.append({"name": name, "date": report_date, "source": "prior_report"})

    for document in filtered_history.get("legacy_documents") or []:
        if not isinstance(document, dict):
            continue
        summary = document.get("extractedSummary") or {}
        report_date = _parse_report_date(
            str(document.get("documentDate") or summary.get("document_date") or "")
        )
        for result in summary.get("test_results") or []:
            if not isinstance(result, dict):
                continue
            name = str(result.get("test_name") or "").strip()
            if name:
                entries.append({"name": name, "date": report_date, "source": "legacy_document"})

    return entries


def analyze_repeat_investigations(
    *,
    prescription_items: list[dict[str, Any]] | None = None,
    bill_items: list[dict[str, Any]] | None = None,
    clinical_context: dict[str, Any] | None = None,
    filtered_history: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Flag investigations that appear to repeat a recent prior test."""
    current_names = _collect_current_investigations(
        prescription_items,
        bill_items,
        clinical_context,
    )
    prior_entries = _prior_investigations_from_history(filtered_history)
    if not current_names or not prior_entries:
        return []

    now = datetime.now(UTC)
    flags: list[dict[str, Any]] = []
    seen_current: set[str] = set()

    for current_name in current_names:
        current_key = _normalize_investigation_name(current_name)
        if current_key in seen_current:
            continue

        matches: list[dict[str, Any]] = []
        for prior in prior_entries:
            if _names_match(current_name, prior["name"]):
                matches.append(prior)

        if not matches:
            continue

        seen_current.add(current_key)
        dated_matches = [entry for entry in matches if entry.get("date")]
        recent_matches = [
            entry
            for entry in dated_matches
            if entry["date"] and (now - entry["date"]) <= timedelta(days=RECENT_WINDOW_DAYS)
        ]
        chosen = recent_matches or dated_matches or matches
        prior_name = chosen[0]["name"]
        prior_date = chosen[0].get("date")
        days_ago: int | None = None
        if prior_date:
            days_ago = max((now - prior_date).days, 0)

        if days_ago is not None and days_ago <= RECENT_WINDOW_DAYS:
            severity = "HIGH"
            timing = f"{days_ago} day(s) ago"
        elif days_ago is not None:
            severity = "MEDIUM"
            timing = f"on {prior_date.strftime('%d %b %Y')}"
        else:
            severity = "MEDIUM"
            timing = "in a prior saved report"

        flags.append(
            {
                "type": "REPEAT_INVESTIGATION",
                "severity": severity,
                "item": current_name,
                "category": "investigation",
                "reason": (
                    f"{current_name} appears similar to {prior_name}, which was recorded "
                    f"{timing}. Repeat testing soon after a prior result may not always be needed."
                ),
                "recommendation": (
                    f"Ask whether the repeat {current_name} is clinically necessary or if "
                    "the earlier result can be used instead."
                ),
                "guideline_basis": None,
                "stg_reference": None,
                "prior_test_name": prior_name,
                "prior_test_date": prior_date.strftime("%Y-%m-%d") if prior_date else None,
            }
        )

    return flags
