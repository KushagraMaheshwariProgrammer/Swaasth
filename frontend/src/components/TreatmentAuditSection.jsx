import {
  flagDisplayLabel,
  getAuditConfidenceMeta,
} from "../auditAdvocacyUtils";
import { getAuditRiskMeta, getAuditSeverityMeta } from "../billUtils";
import AdvocacyScopeSection from "./AdvocacyScopeSection";

const CATEGORY_LABELS = {
  diagnosis: "Diagnosis",
  investigation: "Investigations",
  prescription: "Prescription",
  billing: "Billing",
};

const CLINICAL_CATEGORIES = new Set(["diagnosis", "investigation", "prescription"]);

function alignmentLabel(supported) {
  if (supported === true) {
    return { text: "Supported by reported clinical evidence", className: "clinical-align-yes" };
  }
  if (supported === false) {
    return { text: "Not supported by reported clinical evidence", className: "clinical-align-no" };
  }
  return { text: "Insufficient clinical data to assess", className: "clinical-align-unknown" };
}

function groupFlags(flags) {
  const groups = {
    diagnosis: [],
    investigation: [],
    prescription: [],
    billing: [],
    other: [],
  };
  for (const flag of flags) {
    const category = flag.category || "other";
    if (groups[category]) {
      groups[category].push(flag);
    } else {
      groups.other.push(flag);
    }
  }
  return groups;
}

function isClinicalFlag(flag) {
  return CLINICAL_CATEGORIES.has(flag?.category || "");
}

function getDisplayConfidenceMeta(flag) {
  if (
    isClinicalFlag(flag) &&
    flag?.confidence === "HIGH" &&
    flag?.citation_verified !== true
  ) {
    return {
      ...getAuditConfidenceMeta("MEDIUM"),
      label: "Verify with doctor",
      hint:
        "This clinical point was not backed by a verified STG citation in the retrieved excerpts.",
    };
  }
  return getAuditConfidenceMeta(flag.confidence);
}

function stgReferenceParts(reference) {
  if (!reference || typeof reference !== "object") {
    return [];
  }
  return [
    reference.condition,
    reference.section,
    reference.page ? `p. ${reference.page}` : "",
  ].filter(Boolean);
}

function FlagCard({ flag, index }) {
  const severityMeta = getAuditSeverityMeta(flag.severity);
  const confidenceMeta = getDisplayConfidenceMeta(flag);
  const typeLabel = flag.display_label || flagDisplayLabel(flag.type);
  const referenceParts = stgReferenceParts(flag.stg_reference);
  return (
    <article
      key={`${flag.type || "flag"}-${flag.item || "item"}-${index}`}
      className={severityMeta.cardClass}
    >
      <div className="result-top">
        <h4>{flag.item || "--"}</h4>
        <span className={confidenceMeta.badgeClass}>{confidenceMeta.label}</span>
      </div>
      <p className="audit-confidence-hint">{confidenceMeta.hint}</p>
      <p className="audit-flag-type">{typeLabel}</p>
      <p className="audit-flag-reason">{flag.reason}</p>
      {referenceParts.length > 0 && (
        <p className="audit-flag-reference-chip">
          STG reference: <strong>{referenceParts.join(" · ")}</strong>
        </p>
      )}
      {flag.guideline_basis && (
        <p className="audit-flag-reference">
          <strong>Why this matters:</strong> {flag.guideline_basis}
        </p>
      )}
      <p className="audit-flag-recommendation">
        <strong>Suggested question:</strong> {flag.recommendation}
      </p>
    </article>
  );
}

export default function TreatmentAuditSection({ treatmentAuditFlags, report = null }) {
  if (!treatmentAuditFlags && !report?.patient_questions?.length) {
    return null;
  }

  const flags = treatmentAuditFlags?.flags || [];
  const matched = treatmentAuditFlags?.matched_stg_conditions || [];
  const alignment = treatmentAuditFlags?.clinical_alignment || null;
  const grouped = groupFlags(flags);
  const advocacyScope =
    treatmentAuditFlags?.advocacy_scope || report?.advocacy_scope || null;

  return (
    <>
      <section className="audit-section treatment-audit-section">
        <div className="audit-section-header">
          <h3>Treatment appropriateness check</h3>
          {treatmentAuditFlags && (
            <div className="audit-summary-badges">
              <span
                className={getAuditRiskMeta(treatmentAuditFlags.risk_level).className}
              >
                {getAuditRiskMeta(treatmentAuditFlags.risk_level).label}
              </span>
              <span className="audit-flag-count">
                {treatmentAuditFlags.flags_count ?? 0} finding
                {(treatmentAuditFlags.flags_count ?? 0) === 1 ? "" : "s"}
              </span>
            </div>
          )}
        </div>

        {matched.length > 0 && (
          <p className="comparison-settings-hint">
            Matched condition{matched.length === 1 ? "" : "s"}:{" "}
            <strong>{matched.join(", ")}</strong>
          </p>
        )}

        {(treatmentAuditFlags?.guideline_sources || []).length > 0 && (
          <p className="comparison-settings-hint">
            Guideline sources:{" "}
            <strong>{treatmentAuditFlags.guideline_sources.join(", ")}</strong>
            {treatmentAuditFlags.used_fallback
              ? " (CRC guidelines used as fallback)"
              : ""}
          </p>
        )}

        {alignment && (
          <div className="clinical-alignment-panel">
            <h4>Clinical alignment</h4>
            <p className={alignmentLabel(alignment.diagnosis_supported).className}>
              Diagnosis supported?{" "}
              <strong>{alignmentLabel(alignment.diagnosis_supported).text}</strong>
            </p>
            {(alignment.supporting_evidence || []).length > 0 && (
              <div>
                <p className="clinical-alignment-label">Supporting evidence</p>
                <ul className="clinical-alignment-list">
                  {alignment.supporting_evidence.map((item, index) => (
                    <li key={`support-${index}`}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {(alignment.missing_evidence || []).length > 0 && (
              <div>
                <p className="clinical-alignment-label">Missing or conflicting evidence</p>
                <ul className="clinical-alignment-list">
                  {alignment.missing_evidence.map((item, index) => (
                    <li key={`missing-${index}`}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <p className="treatment-audit-disclaimer">
          Recommendations are based on ICMR and CRC Standard Treatment Guidelines where
          available. This is not a substitute for clinical judgment.
        </p>

        {flags.length ? (
          Object.entries(grouped).map(([category, categoryFlags]) => {
            if (!categoryFlags.length) {
              return null;
            }
            const label =
              category === "other" ? "Other" : CATEGORY_LABELS[category] || category;
            return (
              <div key={category} className="treatment-audit-group">
                <h4>{label} (details)</h4>
                <div className="audit-flags-grid">
                  {categoryFlags.map((flag, index) => (
                    <FlagCard key={`${category}-${index}`} flag={flag} index={index} />
                  ))}
                </div>
              </div>
            );
          })
        ) : (
          <p className="audit-empty-state">
            No items flagged for clarification based on the retrieved government
            guideline excerpts.
          </p>
        )}
      </section>

      <AdvocacyScopeSection advocacyScope={advocacyScope} />
    </>
  );
}
