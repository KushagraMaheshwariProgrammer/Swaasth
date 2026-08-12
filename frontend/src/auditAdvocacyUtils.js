export const FLAG_DISPLAY_LABELS = {
  UNNECESSARY_TEST: "Clarify why this test was billed",
  UNNECESSARY_PROCEDURE: "Clarify why this procedure was billed",
  INVESTIGATION_NOT_ROUTINELY_RECOMMENDED: "Clarify why this investigation was ordered",
  NOT_INDICATED_MEDICINE: "Ask treating doctor about this medicine",
  PRESCRIBED_NOT_IN_STG: "Ask treating doctor about this prescription",
  INSUFFICIENT_STG_EVIDENCE: "Guideline match unclear — ask for clarification",
  GUIDELINE_SUPPORT_NOT_IDENTIFIED: "Guideline match unclear — ask for clarification",
  INSUFFICIENT_CLINICAL_DATA: "More documentation needed for billing review",
  DIAGNOSIS_UNSUPPORTED: "Ask how diagnosis was documented",
  DIAGNOSIS_TEST_MISMATCH: "Ask doctor to reconcile diagnosis and test results",
  MISSING_REQUIRED_INVESTIGATION: "Ask whether an expected test was done or billed",
  PRESCRIPTION_CLINICAL_MISMATCH: "Ask treating doctor about this prescription choice",
  EXCESSIVE_WORKUP: "Ask why this workup appears on the billed case",
  DUPLICATE_ITEM: "Repeated bill item",
  NEAR_DUPLICATE_ITEM: "Possibly duplicate bill item",
  PACKAGE_COMPONENT_CHARGED_SEPARATELY: "Package and component both billed",
  PREAUTH_AMOUNT_ABOVE_APPROVED: "Bill above pre-authorization amount",
  PREAUTH_ITEM_OUTSIDE_AUTHORIZATION: "Item not clearly listed in pre-authorization",
  DUPLICATE_THERAPEUTIC_CLASS: "Ask about duplicate medicine class on bill",
  BROADER_SPECTRUM_ANTIBIOTIC: "Ask treating doctor about this antibiotic choice",
  DRUG_INTERACTION: "Ask treating doctor or pharmacist about these medicines together",
  BRAND_WITHOUT_GENERIC_QUESTION: "Branded medicine with generic alternative",
  MEDICINE_PRICE_DISCREPANCY: "Possible medicine overcharge",
};

export function flagDisplayLabel(flagType) {
  if (!flagType) {
    return "Item worth clarifying";
  }
  return FLAG_DISPLAY_LABELS[flagType] || flagType.replaceAll("_", " ").toLowerCase();
}

export function getAuditConfidenceMeta(confidence) {
  if (confidence === "HIGH") {
    return {
      label: "High confidence",
      badgeClass: "status-pill status-red",
      hint: "Strong guideline basis for this clarification question.",
    };
  }
  if (confidence === "MEDIUM") {
    return {
      label: "Medium confidence",
      badgeClass: "status-pill status-amber",
      hint: "Unusual compared with typical practice; worth clarifying with your doctor.",
    };
  }
  return {
    label: "Low confidence",
    badgeClass: "status-pill status-neutral",
    hint: "Needs physician review; ask for clarification, not an accusation.",
  };
}

export function collectPatientQuestions(report) {
  if (report?.patient_questions?.length) {
    return report.patient_questions;
  }
  const merged = [];
  const seen = new Set();
  for (const source of [
    report?.treatment_audit_flags?.patient_questions,
    report?.audit_flags?.patient_questions,
  ]) {
    for (const item of source || []) {
      const key = (item.question || "").toLowerCase().trim();
      if (!key || seen.has(key)) {
        continue;
      }
      seen.add(key);
      merged.push(item);
    }
  }
  return merged;
}
