import { getAuditRiskMeta, getAuditSeverityMeta } from "../billUtils";

export default function TreatmentAuditSection({ treatmentAuditFlags }) {
  if (!treatmentAuditFlags) {
    return null;
  }

  const flags = treatmentAuditFlags.flags || [];
  const matched = treatmentAuditFlags.matched_stg_conditions || [];

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

      <p className="treatment-audit-disclaimer">
        Guideline-based indication check, not a substitute for clinical judgment.
        Based on CRC Standard Treatment Guidelines, 7th ed. (Wolters Kluwer).
      </p>

      {flags.length ? (
        <div className="audit-flags-grid">
          {flags.map((flag, index) => {
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
                <p className="audit-flag-type">
                  {flag.type?.replaceAll("_", " ") || "--"}
                </p>
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
          })}
        </div>
      ) : (
        <p className="audit-empty-state">
          No tests, procedures, or medicines flagged as unnecessary for this
          diagnosis based on the retrieved STG excerpts.
        </p>
      )}
    </section>
  );
}
