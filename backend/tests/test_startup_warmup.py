"""Tests for startup warmup helpers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import startup_warmup


def test_wait_for_warmup_returns_when_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(startup_warmup, "_warmup_complete", True)
    monkeypatch.setattr(startup_warmup, "_warmup_error", None)
    startup_warmup.wait_for_warmup(timeout_seconds=1)


def test_wait_for_warmup_raises_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(startup_warmup, "_warmup_complete", False)
    monkeypatch.setattr(startup_warmup, "_warmup_error", "boom")
    with pytest.raises(HTTPException) as exc:
        startup_warmup.wait_for_warmup(timeout_seconds=1)
    assert exc.value.status_code == 503
    assert "warmup failed" in str(exc.value.detail).lower()


def test_wait_for_warmup_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(startup_warmup, "_warmup_complete", False)
    monkeypatch.setattr(startup_warmup, "_warmup_error", None)
    monkeypatch.setattr(startup_warmup.time, "sleep", lambda _seconds: None)
    with pytest.raises(HTTPException) as exc:
        startup_warmup.wait_for_warmup(timeout_seconds=0.01)
    assert exc.value.status_code == 503
    assert "warming up" in str(exc.value.detail).lower()
