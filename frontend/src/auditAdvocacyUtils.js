export const FLAG_DISPLAY_LABELS = {
  UNNECESSARY_TEST: "Not routinely recommended",
  UNNECESSARY_PROCEDURE: "Not routinely recommended",
  INVESTIGATION_NOT_ROUTINELY_RECOMMENDED: "Not routinely recommended",
  NOT_INDICATED_MEDICINE: "Not in guideline for this scenario",
  PRESCRIBED_NOT_IN_STG: "Not listed in guideline",
  INSUFFICIENT_STG_EVIDENCE: "Guideline support not identified",
  GUIDELINE_SUPPORT_NOT_IDENTIFIED: "Guideline support not identified",
  INSUFFICIENT_CLINICAL_DATA: "Needs more clinical information",
  DUPLICATE_ITEM: "Repeated bill item",
  NEAR_DUPLICATE_ITEM: "Possibly duplicate bill item",
  PACKAGE_COMPONENT_CHARGED_SEPARATELY: "Package and component both billed",
  DUPLICATE_THERAPEUTIC_CLASS: "Duplicate therapeutic class",
  BROADER_SPECTRUM_ANTIBIOTIC: "Broader-spectrum antibiotic than typical",
  DRUG_INTERACTION: "Possible drug interaction",
  BRAND_WITHOUT_GENERIC_QUESTION: "Branded medicine with generic alternative",
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
      hint: "Strong guideline basis for this question.",
    };
  }
  if (confidence === "MEDIUM") {
    return {
      label: "Medium confidence",
      badgeClass: "status-pill status-amber",
      hint: "Unusual compared with typical practice; worth clarifying.",
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
