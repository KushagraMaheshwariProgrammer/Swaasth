import { formatCurrency } from "../billUtils";
import ReportActions from "./ReportActions";
import RestrictedMedicinesSection from "./RestrictedMedicinesSection";

const STATUS_META = {
  "Above Approved Rate": { cls: "status-pill status-red", card: "abh-item-card abh-item-above" },
  "Within Approved Rate": { cls: "status-pill status-green", card: "abh-item-card abh-item-ok" },
  "Below Approved Rate": { cls: "status-pill status-green", card: "abh-item-card abh-item-ok" },
  "Manual Verification Required": {
    cls: "status-pill status-amber",
    card: "abh-item-card abh-item-manual",
  },
  "Rate Not Found": { cls: "status-pill status-neutral", card: "abh-item-card abh-item-unverified" },
  "Consumable At Actual": { cls: "status-pill status-blue", card: "abh-item-card abh-item-consumable" },
};

const HOSPITAL_TYPE_LABELS = {
  non_nabh: "Non-NABH",
  nabh: "NABH",
  nabh_super: "NABH Super Specialty",
};

const PAYMENT_BASIS_LABELS = {
  package: "EHS package rates",
  package_plus_consumables: "Package rates + consumables at actual",
  actual: "Actual claims with scrutiny",
};

function statusMeta(status) {
  return STATUS_META[status] || STATUS_META["Rate Not Found"];
}

function confidenceLabel(value) {
  if (!value && value !== 0) {
    return "—";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

export default function AarogyaResults({ report, toolbar = null }) {
  if (!report?.comparison?.items) {
    return null;
  }

  const patient = report.patient || {};
  const hospital = report.hospital || {};
  const matched = hospital.matched_hospital || {};
  const bill = report.bill || {};
  const summary = report.comparison.summary || {};
  const items = report.comparison.items || [];
  const janAushadhiMatches = report?.jan_aushadhi?.matches ?? [];

  const specialities = matched.specialities?.length
    ? matched.specialities.join(", ")
    : matched.specialities_text || "—";

  return (
    <div className="abh-report">
      <header className="abh-report-header">
        <h2>Aarogya Bhadratha Rate Comparison</h2>
        <p className="abh-empanel-badge">
          This hospital is empanelled under the Aarogya Bhadratha Scheme.
        </p>
      </header>

      {toolbar && <div className="results-toolbar">{toolbar}</div>}

      {janAushadhiMatches.length > 0 && (
        <section className="jan-aushadhi-banner" aria-label="Jan Aushadhi scheme advisory">
          <div className="jan-aushadhi-banner-header">
            <h3>Jan Aushadhi — subsidized medicines available</h3>
            <span className="jan-aushadhi-count">
              {janAushadhiMatches.length} on your bill
            </span>
          </div>
          <p className="jan-aushadhi-intro">
            The Government of India sells the following medicine
            {janAushadhiMatches.length === 1 ? "" : "s"} from your bill at
            subsidized rates under the{" "}
            <strong>
              {report.jan_aushadhi?.scheme_name ||
                "Pradhan Mantri Bhartiya Janaushadhi Pariyojana (PMBJP)"}
            </strong>{" "}
            (Jan Aushadhi scheme).
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
            {report.jan_aushadhi?.advisory ||
              "Visit your nearest Jan Aushadhi Kendra (medical store) to purchase these medicines at the subsidized MRP."}
          </p>
        </section>
      )}

      <section className="abh-info-card">
        <div className="abh-info-grid">
          <div>
            <span className="abh-info-label">Patient</span>
            <strong>{patient.name || "—"}</strong>
          </div>
          <div>
            <span className="abh-info-label">Hospital (from bill / OCR)</span>
            <strong>{hospital.ocr_hospital_name || "—"}</strong>
          </div>
          <div>
            <span className="abh-info-label">Matched empanelled hospital</span>
            <strong>{matched.name || "—"}</strong>
          </div>
          <div>
            <span className="abh-info-label">District</span>
            <strong>{matched.district || "—"}</strong>
          </div>
          <div className="abh-info-wide">
            <span className="abh-info-label">Address</span>
            <strong>{matched.address || "—"}</strong>
          </div>
          <div className="abh-info-wide">
            <span className="abh-info-label">Speciality</span>
            <strong>{specialities}</strong>
          </div>
          <div>
            <span className="abh-info-label">Hospital code</span>
            <strong>{matched.hospital_code || `Ref ${matched.ref_no || "—"}`}</strong>
          </div>
          <div>
            <span className="abh-info-label">Bill date</span>
            <strong>{bill.bill_date || "—"}</strong>
          </div>
          <div>
            <span className="abh-info-label">Empanelment status</span>
            <strong className="abh-status-empanelled">Empanelled</strong>
          </div>
          <div>
            <span className="abh-info-label">Match confidence</span>
            <strong>
              {confidenceLabel(hospital.match_confidence)} ({hospital.match_method || "—"})
            </strong>
          </div>
          <div>
            <span className="abh-info-label">Original bill total</span>
            <strong>{formatCurrency(bill.original_total)}</strong>
          </div>
        </div>
      </section>

      {/* Hospital Type & Payment Basis */}
      {(summary.hospital_type || summary.payment_basis) && (
        <section className="abh-payment-info">
          <div className="abh-payment-grid">
            {summary.hospital_type && (
              <div>
                <span className="abh-info-label">Hospital Type</span>
                <strong>{HOSPITAL_TYPE_LABELS[summary.hospital_type] || summary.hospital_type}</strong>
              </div>
            )}
            {summary.payment_basis && (
              <div>
                <span className="abh-info-label">Payment Basis</span>
                <strong>{PAYMENT_BASIS_LABELS[summary.payment_basis] || summary.payment_basis}</strong>
              </div>
            )}
          </div>
          {summary.hospital_type === "nabh_super" && (
            <p className="abh-payment-note">
              For NABH Super Specialty hospitals, surgical procedures use package rates.
              Consumables (implants, stents, mesh) are reimbursed at actual cost on top of the package.
            </p>
          )}
        </section>
      )}

      <article className="summary-banner abh-summary">
        <div className="summary-stat">
          <p>Total Charged</p>
          <h3>{formatCurrency(summary.total_charged)}</h3>
        </div>
        <div className="summary-stat">
          <p>Approved (matched)</p>
          <h3>{formatCurrency(summary.total_approved_matched)}</h3>
        </div>
        <div className="summary-stat summary-focus">
          <p>Possible Excess</p>
          <h3>{formatCurrency(summary.total_possible_excess)}</h3>
        </div>
      </article>

      {/* Per-Case Ceiling Information */}
      {summary.per_case_ceiling && (
        <section className={`abh-ceiling-info ${summary.ceiling_exceeded ? "abh-ceiling-exceeded" : "abh-ceiling-ok"}`}>
          <div className="abh-ceiling-header">
            <h4>Per-Case Ceiling (G.O.Ms.No.101)</h4>
            {summary.has_major_ailment && (
              <span className="abh-major-badge">Major Ailment</span>
            )}
          </div>
          <div className="abh-ceiling-grid">
            <div>
              <span className="abh-info-label">Ceiling Limit</span>
              <strong>{formatCurrency(summary.per_case_ceiling)}</strong>
              <span className="abh-ceiling-type">
                {summary.has_major_ailment
                  ? "(Heart surgery, kidney transplant, cancer, or neuro-surgery)"
                  : "(General ailments)"}
              </span>
            </div>
            <div>
              <span className="abh-info-label">Approved Total</span>
              <strong>{formatCurrency(summary.total_approved_matched)}</strong>
            </div>
            <div>
              <span className="abh-info-label">Status</span>
              {summary.ceiling_exceeded ? (
                <strong className="abh-ceiling-warn">
                  Exceeds ceiling by {formatCurrency(summary.ceiling_excess)}
                </strong>
              ) : (
                <strong className="abh-ceiling-pass">Within ceiling</strong>
              )}
            </div>
          </div>
          {summary.major_ailment_categories?.length > 0 && (
            <p className="abh-major-categories">
              Major ailment detected: {summary.major_ailment_categories.join(", ")}
            </p>
          )}
          {summary.ceiling_exceeded && (
            <p className="abh-ceiling-note">
              The bill exceeds the per-case ceiling. The CEO of EHS may review
              amounts above the package limit on a case-by-case basis.
            </p>
          )}
        </section>
      )}

      {/* Consumables Summary (NABH Super Specialty) */}
      {summary.consumables_at_actual?.length > 0 && (
        <section className="abh-consumables-summary">
          <h4>Consumables at Actual Cost</h4>
          <ul>
            {summary.consumables_at_actual.map((item, idx) => (
              <li key={idx}>
                {item.item_name}: <strong>{formatCurrency(item.amount)}</strong>
              </li>
            ))}
          </ul>
          <p className="abh-consumables-total">
            Total consumables: <strong>{formatCurrency(summary.total_consumables_actual)}</strong>
          </p>
        </section>
      )}

      <p className="abh-matched-note">
        The approved total only includes items that were reliably matched with
        the Aarogya Bhadratha rates database.
      </p>

      <div className="abh-summary-chips">
        <span>{summary.matched_items ?? 0} matched</span>
        <span>{summary.unmatched_items ?? 0} unmatched</span>
        <span>{summary.manual_verification_items ?? 0} need verification</span>
        {summary.percentage_difference != null && (
          <span>{summary.percentage_difference}% vs approved</span>
        )}
        {summary.total_below_approved > 0 && (
          <span>{formatCurrency(summary.total_below_approved)} below approved</span>
        )}
      </div>

      <div className="abh-item-list">
        {items.map((item, index) => {
          const meta = statusMeta(item.status);
          const isMedicine =
            item.comparison_source === "pharma" || item.category === "medicine";
          return (
            <article key={`${item.item_name || "item"}-${index}`} className={meta.card}>
              <div className="abh-item-top">
                <h4>{item.item_name || "—"}</h4>
                <span className={meta.cls}>{item.status}</span>
              </div>
              {item.matched_name ? (
                <p className="matched-reference">
                  Matched: {item.matched_name}
                  {item.matched_code ? ` (${item.matched_code})` : ""}
                  {isMedicine ? " · NPPA ceiling price" : ""}
                  {item.pharma_database === "nppa_via_az" && item.resolved_generic_name
                    ? ` · resolved from brand`
                    : ""}
                  {!isMedicine && item.match_confidence
                    ? ` · ${confidenceLabel(item.match_confidence)} ${item.match_method || ""}`
                    : ""}
                </p>
              ) : (
                <p className="matched-reference abh-unverified-note">
                  {item.note ||
                    (isMedicine
                      ? "Medicine not found in the NPPA ceiling price list."
                      : "Rate not found in the Aarogya Bhadratha rates database.")}
                </p>
              )}
              {item.jan_aushadhi_available && (
                <p className="matched-reference jan-aushadhi-item-note">
                  Jan Aushadhi available
                  {item.jan_aushadhi_generic_name
                    ? `: ${item.jan_aushadhi_generic_name}`
                    : ""}
                  {item.jan_aushadhi_mrp != null
                    ? ` · MRP ${formatCurrency(item.jan_aushadhi_mrp)}`
                    : ""}
                  {item.jan_aushadhi_unit_size ? ` per ${item.jan_aushadhi_unit_size}` : ""}
                </p>
              )}
              <div className="result-metrics">
                <div>
                  <p>Qty</p>
                  <h5>{item.quantity}</h5>
                </div>
                <div>
                  <p>Charged</p>
                  <h5>{formatCurrency(item.total_price)}</h5>
                </div>
                <div>
                  <p>{isMedicine ? "NPPA ceiling" : "Approved"}</p>
                  <h5>{formatCurrency(isMedicine ? item.pharma_rate : item.approved_amount)}</h5>
                </div>
                <div>
                  <p>Excess</p>
                  <h5>{formatCurrency(item.excess_amount)}</h5>
                </div>
              </div>
              {item.status === "Manual Verification Required" && item.note && (
                <p className="abh-manual-note">{item.note}</p>
              )}
            </article>
          );
        })}
      </div>

      {/* Annual Family Limits Advisory */}
      <section className="abh-annual-advisory">
        <h4>Annual Family Limits (Advisory)</h4>
        <p>
          Under the Aarogya Bhadratha Scheme, the total reimbursement for a family
          (member + spouse + up to 3 children under 25 + parents) in a financial year is:
        </p>
        <ul className="abh-annual-tiers">
          <li>
            <strong>Up to {formatCurrency(summary.annual_cap_auto || 800000)}</strong> — Automatic coverage
          </li>
          <li>
            <strong>{formatCurrency(summary.annual_cap_auto || 800000)} to {formatCurrency(summary.annual_cap_dgp || 1500000)}</strong> — Requires DGP approval
          </li>
          <li>
            <strong>Beyond {formatCurrency(summary.annual_cap_dgp || 1500000)}</strong> — Requires Trust Board approval
          </li>
        </ul>
        <p className="abh-annual-note">
          This app does not track cumulative family spending. Verify your family&apos;s
          annual claim status with the EHS office for accurate coverage information.
        </p>
      </section>

      <RestrictedMedicinesSection
        restrictedMedicineFlags={report?.restricted_medicine_flags}
      />

      <p className="abh-disclaimer">{report.disclaimer}</p>

      <ReportActions report={report} className="abh-report-actions" />
    </div>
  );
}
