"""Legal-language guardrails for generated action / dispute copy.

Any string that will be shown to the patient as an "action", complaint template,
or escalation step must be routed through :func:`sanitize_text` so that
accusatory or legally loaded wording (fraud, negligence, scam, ...) can never
leak out of the system. The layer is deliberately conservative: it replaces
banned terms with neutral, factual phrasing rather than emitting them.
"""

from __future__ import annotations

import re
from typing import Any

# Shared hedging copy for reports, complaint drafts, and overcharge flags.
POSSIBLE_ISSUE_NOTICE = "Possible issue — verify before acting."
POSSIBLE_OVERCHARGE_LABEL = "Possible overcharge"

# Clinical / guideline-comparison findings — keep in sync with frontend hedgingCopy.
CLINICAL_FINDING_DISCLAIMER = (
    "Possible finding for discussion with your doctor — not a diagnosis, "
    "treatment plan, or prescription advice."
)
DISCUSS_WITH_DOCTOR = (
    "Discuss this with your doctor before changing any treatment, test, or medicine."
)
CLINICAL_SECTION_DISCLAIMER = (
    f"{CLINICAL_FINDING_DISCLAIMER} Swaasth compares uploaded documents against "
    "published ICMR, MoHFW Clinical Establishments Act STGs, and CRC Standard "
    "Treatment Guidelines where available. It does not diagnose, treat, or "
    "prescribe. Every clinical finding should be reviewed with a qualified doctor."
)
AI_GENERATED_NOTICE = (
    "Generated with AI assistance — verify before relying. "
    "This is not a medical diagnosis, treatment advice, or legal finding."
)

# Banned term -> neutral replacement. Whole-word, case-insensitive matching.
_REPLACEMENTS: dict[str, str] = {
    "fraud": "billing discrepancy",
    "frauds": "billing discrepancies",
    "fraudulent": "questionable",
    "fraudulently": "questionably",
    "cheat": "overcharge",
    "cheated": "overcharged",
    "cheating": "overcharging",
    "cheats": "overcharges",
    "negligence": "concern",
    "negligent": "concerning",
    "malpractice": "concern",
    "malpractices": "concerns",
    "criminal": "serious",
    "criminally": "seriously",
    "scam": "billing discrepancy",
    "scams": "billing discrepancies",
    "scammed": "overcharged",
    "illegal": "not as expected",
    "illegally": "not as expected",
    "unlawful": "not as expected",
    "extortion": "overcharge",
    "corrupt": "improper",
    "corruption": "impropriety",
    "sue": "file a formal complaint against",
    "sued": "filed a formal complaint against",
    "suing": "filing a formal complaint against",
    "lawsuit": "formal complaint",
    "lawsuits": "formal complaints",
    "litigation": "formal complaint process",
    "liar": "unclear statement",
    "lying": "unclear",
}

# Public frozenset of banned terms (all keys of the replacement map).
LEGAL_BANNED_TERMS: frozenset[str] = frozenset(_REPLACEMENTS.keys())

_TERM_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in sorted(LEGAL_BANNED_TERMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _match_case(original: str, replacement: str) -> str:
    """Preserve simple capitalization of the matched token in the replacement."""
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def sanitize_text(text: str | None) -> str:
    """Return ``text`` with any banned legal terms replaced by neutral phrasing.

    Newlines and general spacing are preserved so multi-line complaint templates
    keep their structure.
    """
    if text is None:
        return ""
    value = str(text)

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        replacement = _REPLACEMENTS.get(token.lower(), "concern")
        return _match_case(token, replacement)

    return _TERM_PATTERN.sub(_replace, value)


def find_banned_terms(text: str | None) -> list[str]:
    """Return the sorted list of banned terms present in ``text`` (may be empty)."""
    if text is None:
        return []
    found = {match.group(0).lower() for match in _TERM_PATTERN.finditer(str(text))}
    return sorted(found)


def assert_safe(text: str | None) -> None:
    """Raise ``ValueError`` if ``text`` still contains any banned legal term."""
    found = find_banned_terms(text)
    if found:
        raise ValueError(f"Text contains banned legal terms: {found}")


def sanitize_value(value: Any) -> Any:
    """Recursively sanitize strings inside dicts and lists."""
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_value(item) for key, item in value.items()}
    return value


def assert_payload_safe(value: Any) -> None:
    """Raise ``ValueError`` if any string in ``value`` still contains a banned term."""
    if isinstance(value, str):
        assert_safe(value)
        return
    if isinstance(value, list):
        for item in value:
            assert_payload_safe(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            assert_payload_safe(item)

