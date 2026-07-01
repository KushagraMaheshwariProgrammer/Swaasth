"""Legal-language guardrails for generated action / dispute copy.

Any string that will be shown to the patient as an "action", complaint template,
or escalation step must be routed through :func:`sanitize_text` so that
accusatory or legally loaded wording (fraud, negligence, scam, ...) can never
leak out of the system. The layer is deliberately conservative: it replaces
banned terms with neutral, factual phrasing rather than emitting them.
"""

from __future__ import annotations

import re

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
