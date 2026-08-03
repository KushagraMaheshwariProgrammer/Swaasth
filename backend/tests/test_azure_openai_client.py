from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services import azure_openai_client


def test_azure_openai_json_chat_requires_configuration(monkeypatch) -> None:
    for name in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        azure_openai_client.azure_openai_json_chat("system", "user")

    assert exc_info.value.status_code == 500
    assert "AZURE_OPENAI_API_KEY" in exc_info.value.detail
    assert "AZURE_OPENAI_ENDPOINT" in exc_info.value.detail
    assert "AZURE_OPENAI_DEPLOYMENT" in exc_info.value.detail


def test_azure_openai_json_chat_uses_configured_deployment(monkeypatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://swaasth-test.openai.azure.com/",
    )
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "swaasth-gpt-4o-mini")

    create = MagicMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"is_medical_bill": true}')
                )
            ]
        )
    )
    client_factory = MagicMock(
        return_value=SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
    )
    monkeypatch.setattr(azure_openai_client, "AzureOpenAI", client_factory)

    result = azure_openai_client.azure_openai_json_chat(
        "Return JSON.",
        "Analyze this bill.",
        max_tokens=300,
    )

    assert result == {"is_medical_bill": True}
    client_factory.assert_called_once_with(
        api_key="test-key",
        azure_endpoint="https://swaasth-test.openai.azure.com/",
        api_version="2024-10-21",
    )
    assert create.call_args.kwargs["model"] == "swaasth-gpt-4o-mini"
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}
    assert create.call_args.kwargs["max_tokens"] == 300
