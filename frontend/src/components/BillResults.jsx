import { useMemo } from "react";
import {
  computeBillSummary,
  CountUp,
  displayableBillLineItems,
  formatCurrency,
  getAuditRiskMeta,
  getFlagMeta,
  HOSPITAL_TYPE_OPTIONS,
} from "../billUtils";
import { POSSIBLE_ISSUE_NOTICE, POSSIBLE_OVERCHARGE_LABEL } from "../data/hedgingCopy";
import { formatPatientAge, getPatientAge } from "../utils/patientAge";
import AdvocacyScopeSection from "./AdvocacyScopeSection";
import AuditFlagCard from "./AuditFlagCard";
import ClinicalHistoryUsedPanel from "./ClinicalHistoryUsedPanel";
import CombinedNarrative from "./CombinedNarrative";
import PatientQuestionsSection from "./PatientQuestionsSection";
import ReportActions from "./ReportActions";
import ClinicianSharePanel from "./ClinicianSharePanel";
import TreatmentAuditSection from "./TreatmentAuditSection";
import RestrictedMedicinesSection from "./RestrictedMedicinesSection";

export default function BillResults({ result, toolbar = null, onReportUpdate }) {
  const displayableItems = useMemo(
    () => displayableBillLineItems(result?.line_items),
    [result?.line_items]
  );
  const summary = useMemo(() => computeBillSummary(result), [result]);

  const janAushadhiMatches = result?.jan_aushadhi?.matches ?? [];
  const hasLineItems = Boolean(result?.line_items?.length);

  return (
    <>
      {!hasLineItems && (
        <>
          {toolbar}
          <p className="auth-info">
            No bill line items are available for this report yet.
          </p>
        </>
      )}

      {hasLineItems && janAushadhiMatches.length > 0 && (
        <section className="jan-aushadhi-banner" aria-label="Jan Aushadhi advisory">
          <div className="jan-aushadhi-banner-header">
            <h3>Jan Aushadhi — subsidized medicines available</h3>
            <span className="jan-aushadhi-count">
              {janAushadhiMatches.length} on your bill
            </span>
          </div>
          <p className="jan-aushadhi-intro">
            The following billed medicines also appear in the Jan Aushadhi
            catalogue. This is information to discuss with your prescriber — not
            a recommendation to substitute a prescribed brand.
          </p>
          <ul className="jan-aushadhi-match-list">
            {janAushadhiMatches.map((match, index) => (
              <li key={`${match.bill_item_name || "item"}-${index}`}>
                <strong>{match.bill_item_name}</strong>
                {match.generic_name && match.generic_name !== match.bill_item_name && (
                  <> · matched as {match.generic_name}</>
                )}
                {match.mrp != null && (
                  <>
                    {" "}
                    · Jan Aushadhi MRP: <strong>{formatCurrency(match.mrp)}</strong>
                    {match.unit_size ? ` per ${match.unit_size}` : ""}
                  </>
                )}
                {match.approximate_match ? " · approximate match" : ""}
              </li>
            ))}
          </ul>
          <p className="jan-aushadhi-advisory">
            {result.jan_aushadhi?.advisory ||
              "Ask your prescriber or pharmacist whether a Jan Aushadhi generic equivalent is appropriate before changing any medicine."}
          </p>
        </section>
      )}

      {hasLineItems && result?.rates_source?.nppa_list_date && (
        <p className="comparison-context">
          Medicine ceiling-price comparisons are as per the NPPA ceiling price
          list dated <strong>{result.rates_source.nppa_list_date}</strong>.
        </p>
      )}

      {hasLineItems && result?.hospital?.name_from_bill && (
        <p className="comparison-context">
          Hospital on bill: <strong>{result.hospital.name_from_bill}</strong>
        </p>
      )}

      {hasLineItems && result?.patient?.name && (
        <p className="comparison-context">
          Patient: <strong>{result.patient.name}</strong>
          {getPatientAge(result.patient) != null && (
            <> · {formatPatientAge(result.patient)}</>
          )}
          {result.patient.gender && <> · {result.patient.gender}</>}
        </p>
      )}

      {hasLineItems && result?.comparison_settings && (
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
          <strong>
            {HOSPITAL_TYPE_OPTIONS.find(
              (option) => option.id === result.comparison_settings.hospital_type
            )?.label || result.comparison_settings.hospital_type}
          </strong>
        </p>
      )}

      {hasLineItems && toolbar && <div className="results-toolbar">{toolbar}</div>}

      {hasLineItems && displayableItems.length > 0 && (
        <>
          <article className="summary-banner">
            <div className="summary-stat">
              <p>Total Charged</p>
              <h3>
                <CountUp value={summary.totalCharged} isCurrency />
              </h3>
            </div>
            <div className="summary-stat summary-focus">
              <p>{POSSIBLE_OVERCHARGE_LABEL}</p>
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
          <p className="treatment-audit-disclaimer">{POSSIBLE_ISSUE_NOTICE}</p>

          <div className="results-grid">
            {displayableItems.map((item, index) => {
              const meta = getFlagMeta(item.flag);
              const isMedicine =
                item.comparison_source === "pharma" || item.category === "medicine";
              const referenceRate = isMedicine ? item.pharma_rate : null;
              const referenceLabel = isMedicine ? "NPPA Ceiling" : "Reference";

              return (
                <article
                  key={`${item.item_name || "item"}-${index}`}
                  className={meta.cardClass}
                >
                  <div className="result-top">
                    <h4>{item.item_name || "--"}</h4>
                    <span className={meta.badgeClass}>{meta.badgeLabel}</span>
                  </div>
                  {item.flag === "overpriced" && (
                    <p className="treatment-audit-disclaimer">{POSSIBLE_ISSUE_NOTICE}</p>
                  )}
                  {item.matched_reference_item && (
                    <p className="matched-reference">
                      Matched: {item.matched_reference_item}
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
                    {isMedicine && (
                      <>
                        <div>
                          <p>{referenceLabel}</p>
                          <h5>{formatCurrency(referenceRate)}</h5>
                        </div>
                        <div>
                          <p>Difference</p>
                          <h5>{formatCurrency(item.price_difference)}</h5>
                        </div>
                      </>
                    )}
                  </div>
                  {item.jan_aushadhi_available && (
                    <p className="jan-aushadhi-item-note">
                      Available under Jan Aushadhi at subsidized rates
                      {item.jan_aushadhi_mrp != null
                        ? ` (MRP ${formatCurrency(item.jan_aushadhi_mrp)}${
                            item.jan_aushadhi_unit_size
                              ? ` per ${item.jan_aushadhi_unit_size}`
                              : ""
                          })`
                        : ""}
                      . Visit a Jan Aushadhi Kendra.
                    </p>
                  )}
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
                </article>
              );
            })}
          </div>
        </>
      )}

      <PatientQuestionsSection report={result} />
      <CombinedNarrative narrative={result?.action_plan?.combined_narrative} />

      <section className="audit-section">
        <div className="audit-section-header">
          <h3>Items worth clarifying (billing)</h3>
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
            {result.audit_flags.flags.map((flag, index) => (
              <AuditFlagCard key={`${flag.type || "flag"}-${index}`} flag={flag} index={index} />
            ))}
          </div>
        ) : (
          <p className="audit-empty-state">
            No billing patterns flagged for clarification.
          </p>
        )}
      </section>

      <TreatmentAuditSection
        treatmentAuditFlags={result?.treatment_audit_flags}
        report={result}
      />

      <ClinicalHistoryUsedPanel
        clinicalHistoryUsed={
          result?.clinical_history_used ||
          result?.treatment_audit_flags?.clinical_history_used
        }
        patientId={result?.patient?.id}
      />

      <AdvocacyScopeSection advocacyScope={result?.advocacy_scope} />

      <RestrictedMedicinesSection
        restrictedMedicineFlags={result?.restricted_medicine_flags}
      />

      <ClinicianSharePanel report={result} onReportUpdate={onReportUpdate} />

      <ReportActions report={result} />
    </>
  );
}
