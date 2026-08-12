import AdvocacyScopeSection from "./AdvocacyScopeSection";
import AuditFlagCard from "./AuditFlagCard";
import { collectPatientQuestions } from "../auditAdvocacyUtils";
import { getAuditRiskMeta } from "../billUtils";
import { CLINICAL_SECTION_DISCLAIMER } from "../data/hedgingCopy";

const CATEGORY_LABELS = {
  diagnosis: "Diagnosis (for discussion)",
  investigation: "Investigations (for discussion)",
  prescription: "Prescription (for discussion)",
  billing: "Billing",
};

function alignmentLabel(alignment) {
  const consistent =
    alignment?.documents_consistent ||
    (alignment?.diagnosis_supported === true
      ? "yes"
      : alignment?.diagnosis_supported === false
        ? "unclear"
        : "not_assessable");
  if (consistent === "yes") {
    return {
      text: "Documents appear consistent with the stated diagnosis under retrieved guideline excerpts (clarification only — not a diagnosis)",
      className: "clinical-align-yes",
    };
  }
  if (consistent === "unclear") {
    return {
      text: "Consistency is unclear from the uploaded documents — ask your treating doctor to reconcile the records",
      className: "clinical-align-no",
    };
  }
  return {
    text: "Not enough clinical documentation on file to compare",
    className: "clinical-align-unknown",
  };
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

export default function TreatmentAuditSection({ treatmentAuditFlags, report = null }) {
  if (!treatmentAuditFlags && collectPatientQuestions(report).length === 0) {
    return null;
  }

  const flags = treatmentAuditFlags?.flags || [];
  const matched = treatmentAuditFlags?.matched_stg_conditions || [];
  const alignment = treatmentAuditFlags?.clinical_alignment || null;
  const grouped = groupFlags(flags);
  const advocacyScope =
    treatmentAuditFlags?.advocacy_scope || report?.advocacy_scope || null;
  const isClinicalReview = report?.report_kind === "clinical";
  const sectionDisclaimer =
    treatmentAuditFlags?.disclaimer || CLINICAL_SECTION_DISCLAIMER;

  return (
    <>
      <section className="audit-section treatment-audit-section">
        <div className="audit-section-header">
          <h3>
            {isClinicalReview
              ? "Guideline comparison (documents)"
              : "Guideline comparison (treatment documents)"}
          </h3>
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
              ? " (CRC reference book used as fallback)"
              : ""}
          </p>
        )}

        {alignment && (
          <div className="clinical-alignment-panel">
            <h4>Guideline alignment with reported evidence</h4>
            <p className={alignmentLabel(alignment).className}>
              Stated diagnosis vs uploaded documents:{" "}
              <strong>{alignmentLabel(alignment).text}</strong>
            </p>
            <p className="treatment-audit-disclaimer">
              This panel compares uploaded documents to guideline excerpts. It is
              not a medical diagnosis or confirmation of disease. Discuss with your
              doctor.
            </p>
            {(alignment.supporting_evidence || []).length > 0 && (
              <div>
                <p className="clinical-alignment-label">Supporting evidence on file</p>
                <ul className="clinical-alignment-list">
                  {alignment.supporting_evidence.map((item, index) => (
                    <li key={`support-${index}`}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {(alignment.missing_evidence || []).length > 0 && (
              <div>
                <p className="clinical-alignment-label">
                  Missing or conflicting evidence on file
                </p>
                <ul className="clinical-alignment-list">
                  {alignment.missing_evidence.map((item, index) => (
                    <li key={`missing-${index}`}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <p className="treatment-audit-disclaimer">{sectionDisclaimer}</p>

        {flags.length ? (
          Object.entries(grouped).map(([category, categoryFlags]) => {
            if (!categoryFlags.length) {
              return null;
            }
            const label =
              category === "other" ? "Other" : CATEGORY_LABELS[category] || category;
            return (
              <div key={category} className="treatment-audit-group">
                <h4>{label}</h4>
                <div className="audit-flags-grid">
                  {categoryFlags.map((flag, index) => (
                    <AuditFlagCard key={`${category}-${index}`} flag={flag} index={index} />
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
