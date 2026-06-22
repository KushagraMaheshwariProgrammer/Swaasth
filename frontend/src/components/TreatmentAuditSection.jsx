import { getAuditRiskMeta, getAuditSeverityMeta } from "../billUtils";

const CATEGORY_LABELS = {
  diagnosis: "Diagnosis",
  investigation: "Investigations",
  prescription: "Prescription",
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

function FlagCard({ flag, index }) {
  const meta = getAuditSeverityMeta(flag.severity);
  const reference = flag.stg_reference;
  return (
    <article
      key={`${flag.type || "flag"}-${flag.item || "item"}-${index}`}
      className={meta.cardClass}
    >
      <div className="result-top">
        <h4>{flag.item || "--"}</h4>
        <span className={meta.badgeClass}>{meta.badgeLabel}</span>
      </div>
      <p className="audit-flag-type">{flag.type?.replaceAll("_", " ") || "--"}</p>
      <p className="audit-flag-reason">{flag.reason}</p>
      {reference && (
        <p className="audit-flag-reference">
          STG: {reference.condition || "--"}
          {reference.section ? ` · ${reference.section}` : ""}
          {reference.page != null ? ` · p.${reference.page}` : ""}
        </p>
      )}
      <p className="audit-flag-recommendation">
        <strong>Recommendation:</strong> {flag.recommendation}
      </p>
    </article>
  );
}

export default function TreatmentAuditSection({ treatmentAuditFlags }) {
  if (!treatmentAuditFlags) {
    return null;
  }

  const flags = treatmentAuditFlags.flags || [];
  const matched = treatmentAuditFlags.matched_stg_conditions || [];
  const alignment = treatmentAuditFlags.clinical_alignment || null;
  const grouped = groupFlags(flags);

  return (
    <section className="audit-section treatment-audit-section">
      <div className="audit-section-header">
        <h3>Treatment Appropriateness (STG)</h3>
        <div className="audit-summary-badges">
          <span
            className={getAuditRiskMeta(treatmentAuditFlags.risk_level).className}
          >
            {getAuditRiskMeta(treatmentAuditFlags.risk_level).label}
          </span>
          <span className="audit-flag-count">
            {treatmentAuditFlags.flags_count ?? 0} flag
            {(treatmentAuditFlags.flags_count ?? 0) === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      {matched.length > 0 && (
        <p className="comparison-settings-hint">
          Matched STG condition{matched.length === 1 ? "" : "s"}:{" "}
          <strong>{matched.join(", ")}</strong>
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
        Guideline-based indication check, not a substitute for clinical judgment.
        Based on CRC Standard Treatment Guidelines, 7th ed. (Wolters Kluwer).
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
              <h4>{label}</h4>
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
          No tests, procedures, or medicines flagged as unnecessary for this
          diagnosis based on the retrieved STG excerpts.
        </p>
      )}
    </section>
  );
}
