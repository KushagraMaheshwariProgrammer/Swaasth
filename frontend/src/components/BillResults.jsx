import { useMemo } from "react";
import {
  computeBillSummary,
  CountUp,
  formatCurrency,
  getAuditRiskMeta,
  getAuditSeverityMeta,
  getFlagMeta,
  HOSPITAL_TYPE_OPTIONS,
} from "../billUtils";

export default function BillResults({ result, toolbar = null }) {
  const summary = useMemo(() => computeBillSummary(result), [result]);

  if (!result?.line_items?.length) {
    return null;
  }

  return (
    <>
      {result?.hospital?.name_from_bill && (
        <p className="comparison-context">
          Hospital on bill: <strong>{result.hospital.name_from_bill}</strong>
          {result.hospital.is_accredited != null && (
            <>
              {" · "}
              NABH:{" "}
              <strong>
                {result.hospital.is_accredited
                  ? `Accredited (${result.hospital.accreditation_status})`
                  : "Not found in NABH registry"}
              </strong>
              {result.hospital.matched_registry_name &&
                result.hospital.approximate_match && (
                  <> · matched as {result.hospital.matched_registry_name}</>
                )}
            </>
          )}
        </p>
      )}

      {result?.patient?.name && (
        <p className="comparison-context">
          Patient: <strong>{result.patient.name}</strong>
          {result.patient.age != null && <> · {result.patient.age} yrs</>}
          {result.patient.gender && <> · {result.patient.gender}</>}
          {result.patient.ayushman_eligible && (
            <> · <strong>Ayushman Bharat PM-JAY</strong></>
          )}
        </p>
      )}

      {result?.comparison_settings && (
        <p className="comparison-context">
          {result.comparison_settings.state_name &&
            result.comparison_settings.city && (
              <>
                Location:{" "}
                <strong>
                  {result.comparison_settings.city},{" "}
                  {result.comparison_settings.state_name}
                </strong>
                {" · "}
              </>
            )}
          Tier:{" "}
          <strong>
            {result.comparison_settings.tier_label ||
              result.comparison_settings.tier}
          </strong>
          {" · "}
          <strong>
            {HOSPITAL_TYPE_OPTIONS.find(
              (option) => option.id === result.comparison_settings.hospital_type
            )?.label || result.comparison_settings.hospital_type}
          </strong>
          {result.comparison_settings.comparison_scheme !== "hbp_pmjay" && (
            <>
              {" · "}
              <strong>
                {result.comparison_settings.rate_type_label ||
                  result.comparison_settings.rate_type}
              </strong>
            </>
          )}
          {result.comparison_settings.comparison_scheme === "hbp_pmjay" && (
            <>
              {" · "}
              <strong>PM-JAY HBP 2022 benchmark</strong>
            </>
          )}
        </p>
      )}

      {toolbar && <div className="results-toolbar">{toolbar}</div>}

      <article className="summary-banner">
        <div className="summary-stat">
          <p>Total Charged</p>
          <h3>
            <CountUp value={summary.totalCharged} isCurrency />
          </h3>
        </div>
        <div className="summary-stat summary-focus">
          <p>Overcharged By</p>
          <h3>
            <CountUp value={summary.totalOvercharged} isCurrency />
          </h3>
        </div>
        <div className="summary-stat summary-flagged">
          <p>Items Flagged</p>
          <h3>
            <CountUp value={summary.itemsFlagged} />
          </h3>
        </div>
      </article>

      <div className="results-grid">
        {result.line_items.map((item, index) => {
          const meta = getFlagMeta(item.flag);
          const isMedicine =
            item.comparison_source === "pharma" || item.category === "medicine";
          const isHbp = item.comparison_source === "hbp";
          const referenceRate = isMedicine
            ? item.pharma_rate
            : isHbp
            ? item.hbp_rate
            : item.cghs_rate;
          const referenceLabel = isMedicine
            ? "NPPA Ceiling"
            : isHbp
            ? "PM-JAY HBP Rate"
            : "CGHS Rate";
          return (
            <article
              key={`${item.item_name || "item"}-${index}`}
              className={meta.cardClass}
            >
              <div className="result-top">
                <h4>{item.item_name || "--"}</h4>
                <span className={meta.badgeClass}>{meta.badgeLabel}</span>
              </div>
              {item.matched_reference_item && (
                <p className="matched-reference">
                  Matched: {item.matched_reference_item}
                  {item.hbp_procedure_code
                    ? ` (${item.hbp_procedure_code})`
                    : item.cghs_code
                    ? ` (${item.cghs_code})`
                    : ""}
                  {item.pharma_product_id ? ` (NPPA #${item.pharma_product_id})` : ""}
                  {item.pharma_database === "nppa_via_az" && item.resolved_generic_name
                    ? ` · resolved from brand`
                    : ""}
                  {item.approximate_match ? " · approximate" : ""}
                </p>
              )}
              <div className="result-metrics">
                <div>
                  <p>Charged</p>
                  <h5>{formatCurrency(item.total_price)}</h5>
                </div>
                <div>
                  <p>{referenceLabel}</p>
                  <h5>{formatCurrency(referenceRate)}</h5>
                </div>
                <div>
                  <p>Difference</p>
                  <h5>{formatCurrency(item.price_difference)}</h5>
                </div>
              </div>
              {isMedicine && (item.resolved_generic_name || item.pharma_price_basis) && (
                <p className="rate-breakdown">
                  {item.resolved_generic_name
                    ? `Generic: ${item.resolved_generic_name}`
                    : ""}
                  {item.pharma_price_basis
                    ? `${item.resolved_generic_name ? " · " : ""}per ${item.pharma_price_basis}`
                    : ""}
                </p>
              )}
              {isHbp &&
                (item.hbp_tier_1_rate != null || item.hbp_tier_2_rate != null) && (
                  <p className="rate-breakdown">
                    Tier I {formatCurrency(item.hbp_tier_1_rate)} · Tier II{" "}
                    {formatCurrency(item.hbp_tier_2_rate)} · Tier III{" "}
                    {formatCurrency(item.hbp_tier_3_rate)}
                  </p>
                )}
              {!isMedicine &&
                !isHbp &&
                (item.non_nabh_rate != null || item.nabh_rate != null) && (
                  <p className="rate-breakdown">
                    Non-NABH {formatCurrency(item.non_nabh_rate)} · NABH{" "}
                    {formatCurrency(item.nabh_rate)} · Super speciality{" "}
                    {formatCurrency(item.super_speciality_rate)}
                  </p>
                )}
            </article>
          );
        })}
      </div>

      <section className="audit-section">
        <div className="audit-section-header">
          <h3>Suspicious / Unnecessary Charges</h3>
          {result?.audit_flags && (
            <div className="audit-summary-badges">
              <span
                className={getAuditRiskMeta(result.audit_flags.risk_level).className}
              >
                {getAuditRiskMeta(result.audit_flags.risk_level).label}
              </span>
              <span className="audit-flag-count">
                {result.audit_flags.flags_count ?? 0} flag
                {(result.audit_flags.flags_count ?? 0) === 1 ? "" : "s"}
              </span>
            </div>
          )}
        </div>

        {result?.audit_flags?.flags?.length ? (
          <div className="audit-flags-grid">
            {result.audit_flags.flags.map((flag, index) => {
              const meta = getAuditSeverityMeta(flag.severity);
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
                  <p className="audit-flag-recommendation">
                    <strong>Recommendation:</strong> {flag.recommendation}
                  </p>
                </article>
              );
            })}
          </div>
        ) : (
          <p className="audit-empty-state">
            No suspicious repetitions or unnecessary package-component charges
            detected.
          </p>
        )}
      </section>
    </>
  );
}
