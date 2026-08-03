"""Tests for the legal-strength action plan: tiers, math, guardrails, wiring."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.action_plan import build_action_plan
from app.services.action_tiers import assign_action_tier
from app.services.legal_guardrails import (
    LEGAL_BANNED_TERMS,
    POSSIBLE_ISSUE_NOTICE,
    assert_safe,
    find_banned_terms,
    sanitize_text,
)

client = TestClient(app)


# --------------------------------------------------------------------------- #
# Guardrails
# --------------------------------------------------------------------------- #


def test_banned_terms_cover_expected_words() -> None:
    for term in ("fraud", "cheat", "negligence", "malpractice", "scam", "illegal", "sue"):
        assert term in LEGAL_BANNED_TERMS


def test_sanitize_text_removes_banned_terms() -> None:
    dirty = "This looks like fraud and negligence; I will sue for malpractice."
    clean = sanitize_text(dirty)
    assert find_banned_terms(clean) == []
    assert_safe(clean)


def test_sanitize_text_preserves_newlines() -> None:
    assert "\n" in sanitize_text("Line one\nLine two")


# --------------------------------------------------------------------------- #
# Tier assignment
# --------------------------------------------------------------------------- #


def test_tier_a_hard_billing_math() -> None:
    for flag_type in (
        "DUPLICATE_ITEM",
        "PACKAGE_COMPONENT_CHARGED_SEPARATELY",
        "BILLED_NOT_PRESCRIBED",
    ):
        flag = {"type": flag_type, "confidence": "MEDIUM", "category": "billing"}
        assert assign_action_tier(flag) == "A"


def test_tier_a_overpriced_with_reference_else_b() -> None:
    flag = {"type": "MEDICINE_PRICE_DISCREPANCY", "confidence": "HIGH", "category": "billing"}
    assert assign_action_tier(flag, line_item={"pharma_rate": 40}) == "A"
    assert assign_action_tier(flag, line_item={"pharma_rate": None}) == "B"


def test_tier_a_high_grounded_clinical() -> None:
    flag = {
        "type": "UNNECESSARY_TEST",
        "confidence": "HIGH",
        "category": "investigation",
        "stg_reference": {"condition": "Dengue", "section": "Investigations", "page": 12},
    }
    assert assign_action_tier(flag) == "A"


def test_tier_b_medium_and_near_duplicate() -> None:
    assert assign_action_tier(
        {"type": "NEAR_DUPLICATE_ITEM", "confidence": "MEDIUM", "category": "billing"}
    ) == "B"
    assert assign_action_tier(
        {"type": "PRESCRIBED_NOT_IN_STG", "confidence": "MEDIUM", "category": "prescription"}
    ) == "B"


def test_tier_c_low_and_insufficient() -> None:
    assert assign_action_tier(
        {"type": "INSUFFICIENT_STG_EVIDENCE", "confidence": "LOW"}
    ) == "C"
    assert assign_action_tier(
        {"type": "UNNECESSARY_TEST", "confidence": "LOW", "category": "investigation"}
    ) == "C"


# --------------------------------------------------------------------------- #
# build_action_plan: recoverable math
# --------------------------------------------------------------------------- #


def _overpriced_line(name: str, diff: float, total: float) -> dict:
    return {
        "item_name": name,
        "category": "medicine",
        "flag": "overpriced",
        "price_difference": diff,
        "total_price": total,
        "pharma_rate": total - diff,
        "matched_reference_item": name,
    }


def test_recoverable_estimate_sums_overpriced_and_jan_aushadhi() -> None:
    line_items = [
        _overpriced_line("Medicine A", 30.0, 100.0),
        _overpriced_line("Medicine B", 20.0, 80.0),
        {
            "item_name": "Medicine C",
            "category": "medicine",
            "flag": "acceptable",
            "price_difference": -5.0,
            "total_price": 60.0,
            "jan_aushadhi_available": True,
            "jan_aushadhi_mrp": 40.0,
        },
    ]
    plan = build_action_plan(flags=[], line_items=line_items, jan_aushadhi=None)
    estimate = plan["recoverable_estimate"]
    assert estimate["overpriced_total"] == 50.0
    assert estimate["jan_aushadhi_savings"] == 20.0
    assert estimate["total"] == 70.0
    assert estimate["disclaimer"]
    assert len(estimate["basis"]) == 3


def test_recoverable_estimate_ignores_negative_diffs() -> None:
    line_items = [
        {
            "item_name": "Cheap medicine",
            "category": "medicine",
            "flag": "overpriced",
            "price_difference": -10.0,
            "total_price": 20.0,
        }
    ]
    plan = build_action_plan(flags=[], line_items=line_items, jan_aushadhi=None)
    assert plan["recoverable_estimate"]["overpriced_total"] == 0.0


# --------------------------------------------------------------------------- #
# build_action_plan: discharge status transitions
# --------------------------------------------------------------------------- #


def test_discharge_hold_on_tier_a_billing() -> None:
    flags = [
        {"type": "DUPLICATE_ITEM", "confidence": "MEDIUM", "category": "billing", "item": "CBC"}
    ]
    plan = build_action_plan(flags=flags, line_items=[], jan_aushadhi=None)
    assert plan["discharge_guidance"]["status"] == "hold"
    assert plan["discharge_guidance"]["emergency_note"]


def test_discharge_hold_counts_billing_math_flag_regardless_of_category() -> None:
    # BILLED_NOT_PRESCRIBED is billing math even if labeled with a clinical category.
    flags = [
        {
            "type": "BILLED_NOT_PRESCRIBED",
            "confidence": "MEDIUM",
            "category": "prescription",
            "item": "MRI",
        }
    ]
    plan = build_action_plan(flags=flags, line_items=[], jan_aushadhi=None)
    assert plan["discharge_guidance"]["status"] == "hold"


def test_discharge_caution_on_tier_b_only() -> None:
    flags = [
        {"type": "NEAR_DUPLICATE_ITEM", "confidence": "MEDIUM", "category": "billing", "item": "X-ray"}
    ]
    plan = build_action_plan(flags=flags, line_items=[], jan_aushadhi=None)
    assert plan["discharge_guidance"]["status"] == "caution"


def test_discharge_pay_ok_when_no_actionable_flags() -> None:
    flags = [{"type": "INSUFFICIENT_STG_EVIDENCE", "confidence": "LOW", "item": "MRI"}]
    plan = build_action_plan(flags=flags, line_items=[], jan_aushadhi=None)
    assert plan["discharge_guidance"]["status"] == "pay_ok"


# --------------------------------------------------------------------------- #
# build_action_plan: templates, guardrails, escalation ladder
# --------------------------------------------------------------------------- #


def test_complaint_templates_contain_zero_banned_terms() -> None:
    flags = [
        {
            "type": "DUPLICATE_ITEM",
            "confidence": "MEDIUM",
            "category": "billing",
            "item": "CBC",
            # Deliberately inject banned language to prove sanitization.
            "recommendation": "This is fraud, ask about the scam.",
        },
        {
            "type": "MEDICINE_PRICE_DISCREPANCY",
            "confidence": "HIGH",
            "category": "billing",
            "item": "Medicine A",
        },
    ]
    plan = build_action_plan(flags=flags, line_items=[], jan_aushadhi=None)
    templates = plan["complaint_templates"]
    assert templates, "expected templates for Tier A/B flags"
    for template in templates:
        assert template["requires_confirmation"] is True
        assert POSSIBLE_ISSUE_NOTICE in template["disclaimer"]
        assert find_banned_terms(template["subject"]) == []
        assert find_banned_terms(template["body"]) == []
        assert "possible" in template["body"].lower()
        assert "verif" in template["body"].lower()
        for label in template["included_flags"]:
            assert find_banned_terms(label) == []
    for item in plan["action_items"]:
        assert find_banned_terms(item["action"]) == []
    assert plan["guardrails"]["banned_terms_filtered"] is True
    assert POSSIBLE_ISSUE_NOTICE in plan["disclaimer"]


def test_no_templates_when_only_tier_c() -> None:
    flags = [{"type": "INSUFFICIENT_CLINICAL_DATA", "confidence": "LOW", "item": "MRI"}]
    plan = build_action_plan(flags=flags, line_items=[], jan_aushadhi=None)
    assert plan["complaint_templates"] == []


def test_escalation_ladder_advocate_gated_on_high_dispute() -> None:
    small = build_action_plan(flags=[], line_items=[], jan_aushadhi=None)
    small_titles = " ".join(step["title"].lower() for step in small["escalation_ladder"])
    assert "advocate" not in small_titles

    big_line = _overpriced_line("Expensive drug", 30000.0, 60000.0)
    big = build_action_plan(flags=[], line_items=[big_line], jan_aushadhi=None)
    big_titles = " ".join(step["title"].lower() for step in big["escalation_ladder"])
    assert "advocate" in big_titles


def test_action_plan_contract_shape() -> None:
    plan = build_action_plan(flags=[], line_items=[], jan_aushadhi=None)
    for key in (
        "action_items",
        "tier_summary",
        "recoverable_estimate",
        "discharge_guidance",
        "escalation_ladder",
        "complaint_templates",
        "evidence_pack_items",
        "disclaimer",
        "guardrails",
    ):
        assert key in plan
    assert set(plan["tier_summary"].keys()) == {"A", "B", "C"}


# --------------------------------------------------------------------------- #
# Response wiring
# --------------------------------------------------------------------------- #


def test_compare_bill_includes_action_plan() -> None:
    res = client.post(
        "/compare-bill",
        json={
            "line_items": [
                {
                    "item_name": "Paracetamol 500mg",
                    "quantity": 10,
                    "unit_price": 5,
                    "total_price": 50,
                    "category": "medicine",
                }
            ],
            "state_ut_name": "Maharashtra",
            "city": "Mumbai",
            "hospital_type": "general",
            "hospital_name": "Test Hospital",
        },
    )
    assert res.status_code == 200, res.text
    action_plan = res.json().get("action_plan")
    assert action_plan is not None
    assert "tier_summary" in action_plan
    assert action_plan["guardrails"]["banned_terms_filtered"] is True


def test_analyze_treatment_includes_action_plan(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.prescription_routes.analyze_treatment",
        lambda **kwargs: {
            "flags": [
                {
                    "type": "ANTIBIOTIC_NOT_INDICATED",
                    "confidence": "MEDIUM",
                    "category": "clinical",
                    "severity": "medium",
                    "message": "Antibiotic may not be indicated for common cold.",
                }
            ],
            "flags_count": 1,
            "risk_level": "MEDIUM",
            "matched_stg_conditions": [],
            "patient_questions": [],
        },
    )
    res = client.post(
        "/analyze-treatment",
        json={
            "diagnosis": "Common cold",
            "medicines": [{"name": "Azithromycin 500mg"}],
        },
    )
    assert res.status_code == 200, res.text
    assert res.json().get("action_plan") is not None


# --------------------------------------------------------------------------- #
# Dispute-pack PDF smoke test
# --------------------------------------------------------------------------- #


def test_dispute_pack_pdf_renders() -> None:
    flags = [
        {
            "type": "DUPLICATE_ITEM",
            "confidence": "MEDIUM",
            "category": "billing",
            "item": "CBC",
            "recommendation": "Ask hospital for justification.",
        }
    ]
    action_plan = build_action_plan(
        flags=flags,
        line_items=[_overpriced_line("Medicine A", 30.0, 100.0)],
        jan_aushadhi=None,
    )
    report = {
        "report_kind": "dispute_pack",
        "patient": {"name": "Test Patient"},
        "hospital": {"name_from_bill": "City Hospital"},
        "action_plan": action_plan,
    }
    res = client.post("/api/reports/render-pdf", json=report)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"
    assert "dispute-Test-Patient.pdf" in res.headers.get("content-disposition", "")
