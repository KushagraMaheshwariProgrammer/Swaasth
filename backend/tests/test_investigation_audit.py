"""Tests for investigation rationality lane."""

from __future__ import annotations

from app.services.investigation_audit import analyze_investigations


def test_guideline_support_not_identified_for_mri_without_chunks() -> None:
    flags = analyze_investigations(
        diagnosis="Dengue",
        investigation_items=["MRI Brain"],
        retrieval_chunks=[],
    )
    assert len(flags) == 1
    assert flags[0]["type"] == "GUIDELINE_SUPPORT_NOT_IDENTIFIED"
    assert "not identified" in flags[0]["reason"].lower()


def test_not_routinely_recommended_when_chunk_says_so() -> None:
    flags = analyze_investigations(
        diagnosis="Dengue",
        investigation_items=["MRI Brain"],
        retrieval_chunks=[
            {
                "condition": "Dengue",
                "section_type": "investigations",
                "text": "MRI Brain is not routinely recommended for uncomplicated dengue.",
                "page_start": 1,
            }
        ],
    )
    assert len(flags) == 1
    assert flags[0]["type"] == "INVESTIGATION_NOT_ROUTINELY_RECOMMENDED"
    assert "not routinely recommended" in flags[0]["reason"].lower()
