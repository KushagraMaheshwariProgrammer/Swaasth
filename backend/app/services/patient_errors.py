"""Patient-facing API error messages."""

from __future__ import annotations

_GENERIC_HTTP_PHRASES = frozenset(
    {
        "bad request",
        "unauthorized",
        "forbidden",
        "not found",
        "method not allowed",
        "not acceptable",
        "request timeout",
        "conflict",
        "gone",
        "length required",
        "precondition failed",
        "payload too large",
        "uri too long",
        "unsupported media type",
        "unprocessable entity",
        "too many requests",
        "internal server error",
        "not implemented",
        "bad gateway",
        "service unavailable",
        "gateway timeout",
    }
)


def patient_facing_detail(message: str | None, fallback: str) -> str:
    """Return a helpful patient message, not a generic HTTP status phrase."""
    cleaned = str(message or "").strip()
    if not cleaned:
        return fallback
    if cleaned.lower() in _GENERIC_HTTP_PHRASES:
        return fallback
    return cleaned
