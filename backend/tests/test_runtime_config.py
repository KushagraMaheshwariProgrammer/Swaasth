"""Tests for production config guards."""

from __future__ import annotations

import logging

from app.services import runtime_config


def test_log_critical_config_status_warns_when_missing(
    monkeypatch, caplog
) -> None:
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_PATH", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    monkeypatch.setattr(
        runtime_config,
        "_BACKEND_ROOT",
        runtime_config._BACKEND_ROOT / "missing-dir-for-tests",
    )
    with caplog.at_level(logging.ERROR):
        runtime_config.log_critical_config_status()
    joined = " ".join(caplog.messages).lower()
    assert "firebase" in joined
    assert "azure openai" in joined


def test_firebase_configured_accepts_json_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        '{"type":"service_account","private_key":"x","client_email":"a@b.c"}',
    )
    assert runtime_config._firebase_configured() is True


def test_azure_openai_configured_requires_all(monkeypatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    assert runtime_config._azure_openai_configured() is False
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    assert runtime_config._azure_openai_configured() is True
