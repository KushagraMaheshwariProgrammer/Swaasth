"""Filter and normalize ICMR document titles for clinical STG retrieval."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CURATOR_PATH = _BACKEND_ROOT / "data" / "icmr_document_curator.json"


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
    curator_path: Path | None = None,
) -> str:
    path = str(curator_path or DEFAULT_CURATOR_PATH)
    config = _load_curator_config(path)
    aliases: dict[str, str] = config["title_aliases"]
    cleaned = title.strip()
    if not cleaned:
        return cleaned
    for key, value in aliases.items():
        if cleaned.lower() == key.lower():
            return value
    return cleaned
