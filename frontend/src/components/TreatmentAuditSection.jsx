import AdvocacyScopeSection from "./AdvocacyScopeSection";
import AuditFlagCard from "./AuditFlagCard";
import { getAuditRiskMeta } from "../billUtils";

const CATEGORY_LABELS = {
  diagnosis: "Diagnosis",
  investigation: "Investigations",
  prescription: "Prescription",
  billing: "Billing",
};

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
              ? " (CRC reference book used as fallback)"
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
          Recommendations use ICMR, MoHFW Clinical Establishments Act STGs, and CRC
          Standard Treatment Guidelines where available. This is not a substitute for
          clinical judgment or legal advice.
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
