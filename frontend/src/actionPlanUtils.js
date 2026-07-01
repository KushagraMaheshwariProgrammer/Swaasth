import { collectPatientQuestions } from "./auditAdvocacyUtils";

const TIER_A_TYPES = new Set([
  "DUPLICATE_ITEM",
  "PACKAGE_COMPONENT_CHARGED_SEPARATELY",
  "BILLED_NOT_PRESCRIBED",
  "MEDICINE_PRICE_DISCREPANCY",
]);

const TIER_B_TYPES = new Set([
  "NEAR_DUPLICATE_ITEM",
  "UNREALISTIC_REPETITION",
  "LAB_REPETITION",
  "INSUFFICIENT_CLINICAL_DATA",
  "PREAUTH_AMOUNT_ABOVE_APPROVED",
  "PREAUTH_ITEM_OUTSIDE_AUTHORIZATION",
]);

const LOW_TYPES = new Set([
  "INSUFFICIENT_STG_EVIDENCE",
  "INSUFFICIENT_CLINICAL_DATA",
  "GUIDELINE_SUPPORT_NOT_IDENTIFIED",
]);

const CLINICAL_CATEGORIES = new Set(["diagnosis", "investigation", "prescription"]);

export function getActionTierMeta(tier) {
  if (tier === "A") {
    return {
      label: "Ask now",
      badgeClass: "status-pill status-red",
      hint: "Strong factual basis — clarify before paying if possible.",
    };
  }
  if (tier === "B") {
    return {
      label: "Verify first",
      badgeClass: "status-pill status-amber",
      hint: "Worth confirming before final payment.",
    };
  }
  return {
    label: "Document only",
    badgeClass: "status-pill status-neutral",
    hint: "Note for your records; discuss with your doctor.",
  };
}

function collectFlags(report) {
  const flags = [];
  for (const source of [report?.audit_flags?.flags, report?.treatment_audit_flags?.flags]) {
    for (const flag of source || []) {
      if (flag && typeof flag === "object") {
        flags.push(flag);
      }
    }
  }
  return flags;
}

function fallbackTier(flag, lineItems) {
  const type = flag.type || "";
  const confidence = flag.confidence || "LOW";
  if (LOW_TYPES.has(type)) {
    return "C";
  }
  if (TIER_A_TYPES.has(type)) {
    return "A";
  }
  if (TIER_B_TYPES.has(type)) {
    return "B";
  }
  const itemName = (flag.item || "").toLowerCase();
  const matched = (lineItems || []).find((line) => {
    const name = (line.item_name || "").toLowerCase();
    return name && (name === itemName || name.includes(itemName) || itemName.includes(name));
  });
  if (matched?.flag === "overpriced" && Number(matched.price_difference) > 0) {
    return "A";
  }
  if (
    CLINICAL_CATEGORIES.has(flag.category || "") &&
    confidence === "HIGH" &&
    flag.citation_verified !== true
  ) {
    return "B";
  }
  if (confidence === "HIGH") {
    return "A";
  }
  if (confidence === "MEDIUM") {
    return "B";
  }
  return "C";
}

function computeRecoverable(lineItems) {
  let overpricedTotal = 0;
  let janSavings = 0;
  const basis = [];
  for (const line of lineItems || []) {
    if (line.flag === "overpriced" && Number(line.price_difference) > 0) {
      overpricedTotal += Number(line.price_difference);
      basis.push({
        item: line.item_name,
        amount: Number(line.price_difference),
        source: "NPPA ceiling price comparison",
      });
    }
    if (line.jan_aushadhi_available) {
      const billed = Number(line.total_price || 0);
      const jaMrp = Number(line.jan_aushadhi_mrp || 0);
      if (billed > jaMrp && jaMrp > 0) {
        const savings = billed - jaMrp;
        janSavings += savings;
        basis.push({
          item: line.item_name,
          amount: savings,
          source: "Jan Aushadhi MRP comparison",
        });
      }
    }
  }
  return {
    overpriced_total: Math.round(overpricedTotal * 100) / 100,
    jan_aushadhi_savings: Math.round(janSavings * 100) / 100,
    total: Math.round((overpricedTotal + janSavings) * 100) / 100,
    basis,
    disclaimer:
      "Amounts are estimates based on reference rates. Verify with the hospital before acting.",
  };
}

function dischargeFromItems(actionItems) {
  const tierABilling = actionItems.filter(
    (item) =>
      item.tier === "A" &&
      (item.category === "billing" ||
        item.category === "prescription" ||
        TIER_A_TYPES.has(item.type))
  );
  const tierB = actionItems.filter((item) => item.tier === "B");
  if (tierABilling.length) {
    return {
      status: "hold",
      reasons: [
        "One or more billing items should be clarified before final payment.",
        ...tierABilling.slice(0, 3).map((item) => `Review: ${item.display_label || item.item}`),
      ],
      emergency_note:
        "If urgent care is needed, do not delay treatment because of billing questions.",
    };
  }
  if (tierB.length) {
    return {
      status: "caution",
      reasons: ["Some items need verification before you finalize payment."],
      emergency_note:
        "If urgent care is needed, do not delay treatment because of billing questions.",
    };
  }
  return {
    status: "pay_ok",
    reasons: ["No high-priority billing flags were identified."],
    emergency_note:
      "If urgent care is needed, do not delay treatment because of billing questions.",
  };
}

function buildFallbackNarrative(report, actionItems, recoverable) {
  const patientName = report?.patient?.name || "the patient";
  const hospitalName = report?.hospital?.name_from_bill || "the hospital";
  const topItems = actionItems
    .filter((item) => item.tier === "A" || item.tier === "B")
    .slice(0, 3)
    .map((item) => item.display_label || item.item || item.type);
  const concernText = topItems.length
    ? topItems.join(", ")
    : "the listed clarification points";
  const amountText =
    recoverable.total > 0
      ? ` The reference-rate math suggests about INR ${Math.round(
          recoverable.total
        ).toLocaleString("en-IN")} may be worth verifying.`
      : "";
  return {
    summary:
      `For ${patientName}, Swaasth found ${
        actionItems.length || "no"
      } clarification point${actionItems.length === 1 ? "" : "s"} in the documents from ${hospitalName}. ` +
      `The main points to verify are ${concernText}.${amountText} Use this as a factual summary for discussion; it is not a medical or legal conclusion.`,
    disclaimer:
      "This narrative is informational only. Verify facts and consult qualified professionals before acting.",
  };
}

export function buildFallbackActionPlan(report) {
  if (report?.action_plan) {
    return report.action_plan;
  }
  const lineItems = report?.line_items || [];
  const flags = collectFlags(report);
  const actionItems = flags.map((flag) => {
    const tier = fallbackTier(flag, lineItems);
    return {
      type: flag.type,
      item: flag.item,
      display_label: flag.display_label,
      confidence: flag.confidence,
      tier,
      category: flag.category,
      action: flag.recommendation || `Ask the hospital to explain ${flag.item || "this item"}.`,
      attachments: [],
    };
  });
  const tierSummary = { A: 0, B: 0, C: 0 };
  for (const item of actionItems) {
    tierSummary[item.tier] = (tierSummary[item.tier] || 0) + 1;
  }
  const recoverable = computeRecoverable(lineItems);
  const questions = collectPatientQuestions(report);
  return {
    action_items: actionItems,
    tier_summary: tierSummary,
    recoverable_estimate: recoverable,
    discharge_guidance: dischargeFromItems(actionItems),
    escalation_ladder: [],
    complaint_templates: [],
    evidence_pack_items: actionItems
      .filter((item) => item.tier === "A" || item.tier === "B")
      .map((item) => ({
        ...item,
        bill_line: null,
        reference_rate: null,
        stg_excerpt: null,
        questions: questions
          .filter((q) => q.flag_type === item.type || q.item === item.item)
          .map((q) => q.question),
      })),
    combined_narrative: buildFallbackNarrative(report, actionItems, recoverable),
    disclaimer:
      "Swaasth provides procedural assistance only. Not medical or legal advice.",
    guardrails: { banned_terms_filtered: true },
  };
}

export function resolveActionPlan(report) {
  return buildFallbackActionPlan(report);
}

export function hasActionablePlan(report) {
  const plan = resolveActionPlan(report);
  return Boolean(
    plan?.action_items?.length ||
      plan?.recoverable_estimate?.total > 0 ||
      plan?.complaint_templates?.length ||
      plan?.escalation_ladder?.length
  );
}
