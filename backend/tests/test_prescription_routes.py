"""Tests for prescription upload route."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_list_stg_conditions_returns_503_without_index(monkeypatch) -> None:
    class EmptyStore:
        toc = []

        def condition_names(self):
            return []

    monkeypatch.setattr(
        "app.prescription_routes.get_stg_index_store",
        lambda: EmptyStore(),
    )
    monkeypatch.setattr(
        "app.prescription_routes.get_primary_guidelines_store",
        lambda: EmptyStore(),
    )
    response = client.get("/api/stg/conditions")
    assert response.status_code == 503


def test_list_stg_conditions_merges_primary_and_crc(monkeypatch) -> None:
    class PrimaryStore:
        toc = [{"condition": "HYPERTENSION"}]

        def condition_names(self):
            return ["HYPERTENSION"]

    class CrcStore:
        toc = [{"condition": "Malaria"}]

        def condition_names(self):
            return ["Malaria", "hypertension"]

    monkeypatch.setattr(
        "app.prescription_routes.get_primary_guidelines_store",
        lambda: PrimaryStore(),
    )
    monkeypatch.setattr(
        "app.prescription_routes.get_stg_index_store",
        lambda: CrcStore(),
    )
    response = client.get("/api/stg/conditions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["sources"]["primary"] == 1
    assert payload["sources"]["crc"] == 2


def test_analyze_treatment_requires_diagnosis() -> None:
    response = client.post(
        "/analyze-treatment",
        json={"diagnosis": "", "medicines": [{"name": "Paracetamol"}]},
    )
    assert response.status_code == 400


def test_analyze_treatment_accepts_clinical_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.prescription_routes.analyze_treatment",
        lambda **kwargs: {
            "flags": [],
            "flags_count": 0,
            "risk_level": "LOW",
            "matched_stg_conditions": [],
            "clinical_alignment": {
                "diagnosis_supported": None,
                "supporting_evidence": [],
                "missing_evidence": [],
            },
        },
    )
    response = client.post(
        "/analyze-treatment",
        json={
            "diagnosis": "Malaria",
            "symptoms": [{"name": "fever", "duration": "3 days"}],
            "test_results": [{"test_name": "Malaria RDT", "result": "negative"}],
            "medicines": [{"name": "Chloroquine"}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["clinical_context"]["symptoms"][0]["name"] == "fever"
    assert payload["clinical_context"]["test_results"][0]["test_name"] == "Malaria RDT"


def test_upload_clinical_document_lab_report(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.prescription_routes.extract_document_text",
        lambda file_bytes, file_type: "Lab report text",
    )
    monkeypatch.setattr(
        "app.prescription_routes.extract_lab_report_with_groq",
        lambda text: {
            "is_lab_report": True,
            "test_results": [
                {"test_name": "Malaria RDT", "result": "negative"},
            ],
            "lab_name": "City Lab",
            "report_date": "2026-01-01",
        },
    )

    response = client.post(
        "/upload-clinical-document",
        data={"document_type": "lab_report"},
        files={"file": ("lab.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_type"] == "lab_report"
    assert payload["clinical_context"]["test_results"][0]["test_name"] == "Malaria RDT"
