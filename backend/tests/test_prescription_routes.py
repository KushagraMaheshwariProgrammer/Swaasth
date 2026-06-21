"""Tests for prescription upload route."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_list_stg_conditions_returns_503_without_index(monkeypatch) -> None:
    class EmptyStore:
        toc = []

    monkeypatch.setattr(
        "app.prescription_routes.get_stg_index_store",
        lambda: EmptyStore(),
    )
    response = client.get("/api/stg/conditions")
    assert response.status_code == 503


def test_analyze_treatment_requires_diagnosis() -> None:
    response = client.post(
        "/analyze-treatment",
        json={"diagnosis": "", "medicines": [{"name": "Paracetamol"}]},
    )
    assert response.status_code == 400
