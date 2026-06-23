import { getAuditSeverityMeta } from "../billUtils";

function formatConfidence(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

function buildTypeLine(flag) {
  const parts = [flag.restriction_type, flag.schedule_or_category].filter(Boolean);
  return parts.join(" · ");
}

function FlagCard({ flag, index }) {
  const meta = getAuditSeverityMeta(
    String(flag.severity || "Medium").toUpperCase()
  );
  const title = flag.matched_medicine_name || flag.detected_text || "--";
  const typeLine = buildTypeLine(flag);

  return (
    <article
      key={`${flag.matched_medicine_name || "medicine"}-${index}`}
      className={`restricted-medicine-card ${meta.cardClass}`}
    >
      <div className="result-top">
        <h4>{title}</h4>
        <span className={meta.badgeClass}>{meta.badgeLabel}</span>
      </div>
      {typeLine && <p className="audit-flag-type">{typeLine}</p>}
      {flag.reason && <p className="audit-flag-reason">{flag.reason}</p>}
      <p className="restricted-medicine-meta">
        {formatConfidence(flag.confidence_score)} match
        {flag.detected_text &&
        flag.detected_text !== title &&
        flag.detected_text !== flag.matched_medicine_name
          ? ` · detected as “${flag.detected_text}”`
          : ""}
        {flag.matched_alias_or_brand &&
        flag.matched_alias_or_brand !== title &&
        normalize(flag.matched_alias_or_brand) !== normalize(title)
          ? ` · via ${flag.matched_alias_or_brand}`
          : ""}
      </p>
    </article>
  );
}

function normalize(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

export default function RestrictedMedicinesSection({ restrictedMedicineFlags }) {
  if (!restrictedMedicineFlags) {
    return null;
  }

  const flags = restrictedMedicineFlags.flags || [];
  const detected = Boolean(restrictedMedicineFlags.detected && flags.length);

  return (
    <section
      className={`audit-section restricted-medicines-section ${
        detected ? "restricted-medicines-warning" : "restricted-medicines-safe"
      }`}
      aria-label="Restricted medicines check"
    >
      <div className="audit-section-header">
        <h3>Restricted Medicines Check</h3>
        {detected && (
          <span className="restricted-medicine-count">
            {flags.length} detected
          </span>
        )}
      </div>

      {detected ? (
        <>
          <p className="restricted-medicine-intro">
            {restrictedMedicineFlags.advisory ||
              "A medicine on this document matches the restricted medicines list."}
          </p>
          <div className="audit-flags-grid">
            {flags.map((flag, index) => (
              <FlagCard key={`restricted-${index}`} flag={flag} index={index} />
            ))}
          </div>
          {(restrictedMedicineFlags.disclaimer ||
            restrictedMedicineFlags.manual_verification_note) && (
            <p className="restricted-medicine-disclaimer">
              {[restrictedMedicineFlags.disclaimer, restrictedMedicineFlags.manual_verification_note]
                .filter(Boolean)
                .join(" ")}
            </p>
          )}
        </>
      ) : (
        <p className="audit-empty-state">
          No restricted medicines were detected from the OCR text.
        </p>
      )}
    </section>
  );
}
