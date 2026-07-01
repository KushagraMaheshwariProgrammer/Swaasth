"""Tests for educational legal pathway hints."""

from __future__ import annotations

from app.services.legal_case_framing import attach_legal_pathways, build_legal_pathway_for_flag


def test_billing_flag_legal_pathway() -> None:
    pathway = build_legal_pathway_for_flag(
        {"type": "DUPLICATE_ITEM", "item": "CBC", "category": "billing"}
    )
    assert pathway is not None
    assert "deficiency" in pathway["broader_concept"].lower()


def test_clinical_flag_mentions_negligence_educationally() -> None:
    pathway = build_legal_pathway_for_flag(
        {
            "type": "NOT_INDICATED_MEDICINE",
            "item": "Azithromycin",
            "category": "prescription",
        }
    )
    assert pathway is not None
    assert "negligence" in pathway["broader_concept"].lower()
    assert pathway["not_an_accusation"]


def test_attach_legal_pathways_skips_insufficient_flags() -> None:
    flags = attach_legal_pathways(
        [
            {"type": "INSUFFICIENT_STG_EVIDENCE", "item": "Fever"},
            {"type": "DUPLICATE_ITEM", "item": "CBC", "category": "billing"},
        ]
    )
    assert "legal_pathway" not in flags[0]
    assert "legal_pathway" in flags[1]
