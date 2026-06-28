"""Filter and normalize ICMR document titles for clinical STG retrieval."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CURATOR_PATH = _BACKEND_ROOT / "data" / "icmr_document_curator.json"

_COVER_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"CONSENSUS\s+DOCUMENT\s+"
        r"(?:FOR\s+)?(?:THE\s+)?"
        r"(?:MANAGEMENT\s+(?:OF|ON)\s+|DIAGNOSIS\s+AND\s+(?:MANAGEMENT|TREATMENT)\s+OF\s+)"
        r"(.+?)"
        r"(?:\n|Prepared\b|Indian Council\b|Coordinated\b|$)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"CONSENSUS\s+DOCUMENT\s+ON\s+(.+?)"
        r"(?:\n|Prepared\b|Indian Council\b|Coordinated\b|$)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"GUIDELINES?\s+FOR\s+(?:THE\s+)?(?:MANAGEMENT\s+OF\s+)?(.+?)"
        r"(?:\n|Prepared\b|Indian Council\b|$)",
        re.IGNORECASE | re.DOTALL,
    ),
)

_FILENAME_ARTIFACT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bfinal\s+pdf\b", re.IGNORECASE), ""),
    (re.compile(r"\bfor\s+farrow\b", re.IGNORECASE), ""),
    (re.compile(r"\bconsensus\s+doc\b", re.IGNORECASE), ""),
    (re.compile(r"\bicmr\s*20\d{2}\b", re.IGNORECASE), ""),
    (re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b"), ""),
    (re.compile(r"\s+0(?:\s*\(\d+\))?\s*$"), ""),
    (re.compile(r"\bfinal\b", re.IGNORECASE), ""),
)


@lru_cache(maxsize=1)
def _load_curator_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return {"exclude_patterns": [], "title_aliases": {}}
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return {
        "exclude_patterns": list(payload.get("exclude_patterns") or []),
        "title_aliases": dict(payload.get("title_aliases") or {}),
    }


def _compiled_patterns(path: str) -> list[re.Pattern[str]]:
    config = _load_curator_config(path)
    patterns: list[re.Pattern[str]] = []
    for raw in config["exclude_patterns"]:
        try:
            patterns.append(re.compile(str(raw), re.IGNORECASE))
        except re.error:
            continue
    return patterns


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _to_display_case(value: str) -> str:
    if not value:
        return value
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return value
    upper_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    if upper_ratio < 0.8:
        return value
    return " ".join(word.capitalize() for word in value.split())


def extract_clinical_title_from_text(text: str) -> str | None:
    """Extract a clinical condition title from ICMR cover-page text."""
    normalized = _collapse_whitespace(text.replace("\n", " "))
    if not normalized:
        return None

    for pattern in _COVER_TITLE_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        candidate = _collapse_whitespace(match.group(1))
        candidate = re.split(
            r"\b(?:Prepared|Indian Council|Coordinated)\b",
            candidate,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" .,-")
        if len(candidate) < 3:
            continue
        return _to_display_case(candidate)
    return None


def strip_filename_artifacts(title: str) -> str:
    """Remove recurring PDF filename junk from a document title."""
    cleaned = _collapse_whitespace(title)
    if not cleaned:
        return cleaned

    for pattern, replacement in _FILENAME_ARTIFACT_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    cleaned = _collapse_whitespace(cleaned)
    return cleaned


def should_exclude_document(
    title: str,
    source_file: str = "",
    *,
    curator_path: Path | None = None,
) -> bool:
    path = str(curator_path or DEFAULT_CURATOR_PATH)
    label = f"{title} {source_file}".strip()
    if not label:
        return True
    for pattern in _compiled_patterns(path):
        if pattern.search(label):
            return True
    return False


def normalize_document_title(
    title: str,
    *,
    cover_text: str | None = None,
    curator_path: Path | None = None,
) -> str:
    path = str(curator_path or DEFAULT_CURATOR_PATH)
    config = _load_curator_config(path)
    aliases: dict[str, str] = config["title_aliases"]
    cleaned = _collapse_whitespace(title)
    if not cleaned:
        return cleaned

    for key, value in aliases.items():
        if cleaned.lower() == key.lower():
            return value

    if cover_text:
        extracted = extract_clinical_title_from_text(cover_text)
        if extracted:
            return extracted

    return strip_filename_artifacts(cleaned)
