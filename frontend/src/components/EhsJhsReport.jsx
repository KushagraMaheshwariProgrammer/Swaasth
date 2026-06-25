import { formatCurrency } from "../billUtils";
import {
  formatDisplayName,
  formatEmpanelmentStatusLabel,
  formatHospitalLocation,
  formatHospitalTypeBadge,
} from "../lib/hospitalDisplay";
import { formatEhsSpecialitiesForDisplay } from "../lib/ehsSpecialities";

function yesNo(value) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "—";
}

function statusBadgeClass(status) {
  const text = String(status || "").toLowerCase();
  if (text.includes("within") || text.includes("below")) {
    return "rajiv-status-badge rajiv-status-success";
  }
  if (text.includes("excess")) {
    return "rajiv-status-badge rajiv-status-warning";
  }
  if (text.includes("fallback")) {
    return "rajiv-status-badge rajiv-status-info";
  }
  if (text.includes("not found") || text.includes("manual")) {
    return "rajiv-status-badge rajiv-status-muted";
  }
  if (text === "empanelled" || text.includes("matched")) {
    return "rajiv-status-badge rajiv-status-success";
  }
  return "rajiv-status-badge";
}

function confidenceLabel(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

function hospitalStatusLabel(status) {
  const text = String(status || "").replaceAll("_", " ");
  if (!text) {
    return "Unknown";
  }
  return text.replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function EhsJhsReport({ report }) {
  if (!report?.selected) {
    return null;
  }

  const schemeType = report.scheme_type || "EHS";
  const title =
    schemeType === "JHS"
      ? "Journalists Health Scheme Verification"
      : "Employees Health Scheme Verification";
  const eligibility = report.eligibility_snapshot || {};
  const hospital = report.hospital_verification || {};
  const comparisons = report.package_comparisons || [];
  const advisories = report.advisories || [];
  const location = formatHospitalLocation(
    hospital.municipality,
    hospital.mandal,
    hospital.district
  );
  const specialities = formatEhsSpecialitiesForDisplay(hospital);

  return (
    <section
      className="rajiv-aarogyasri-report ehs-jhs-report"
      aria-label={`${schemeType} verification`}
    >
      <div className="rajiv-aarogyasri-header">
        <h3>{title}</h3>
        <span className="rajiv-aarogyasri-badge">{schemeType} verification</span>
      </div>

      <div className="rajiv-aarogyasri-card">
        <h4>A. Eligibility Snapshot</h4>
        {schemeType === "EHS" ? (
          <ul className="rajiv-meta-list">
            <li>
              Telangana government employee: {yesNo(eligibility.government_employee)}
            </li>
            <li>Pensioner: {yesNo(eligibility.pensioner)}</li>
            <li>Dependent family member: {yesNo(eligibility.dependent)}</li>
            <li>EHS health card: {yesNo(eligibility.has_health_card)}</li>
            {eligibility.card_number && (
              <li>EHS card number: {eligibility.card_number}</li>
            )}
          </ul>
        ) : (
          <ul className="rajiv-meta-list">
            <li>
              Working journalist: {yesNo(eligibility.working_journalist)}
            </li>
            <li>Retired journalist: {yesNo(eligibility.retired_journalist)}</li>
            <li>Dependent family member: {yesNo(eligibility.dependent)}</li>
            <li>JHS health card: {yesNo(eligibility.has_health_card)}</li>
            <li>Aadhaar: {yesNo(eligibility.has_aadhaar)}</li>
            {eligibility.card_number && (
              <li>JHS card number: {eligibility.card_number}</li>
            )}
          </ul>
        )}
      </div>

      <div className="rajiv-aarogyasri-card">
        <div className="rajiv-section-heading">
          <h4>B. Hospital Empanelment Check</h4>
          <span className={statusBadgeClass(hospital.status)}>
            {hospitalStatusLabel(hospital.status)}
          </span>
        </div>
        <ul className="rajiv-meta-list">
          <li>
            Hospital on bill:{" "}
            <strong>{formatDisplayName(hospital.ocr_hospital_name) || "—"}</strong>
          </li>
          <li>
            Matched hospital:{" "}
            <strong>{formatDisplayName(hospital.matched_hospital_name) || "—"}</strong>
          </li>
          <li>Match confidence: {confidenceLabel(hospital.confidence_score)}</li>
          <li>Location: {location || "—"}</li>
          <li>
            Hospital type: {formatHospitalTypeBadge(hospital.hospital_type) || "—"}
          </li>
          <li>
            Empanelment status:{" "}
            {formatEmpanelmentStatusLabel(hospital.empanelment_status) || "—"}
          </li>
          <li>Source: EHS/JHS hospital data</li>
          {specialities.hasSpecialities && (
            <li>
              Specialities:{" "}
              {specialities.detailsText ||
                "Specialities available — verify with hospital/helpdesk"}
            </li>
          )}
          {hospital.match_reason && (
            <li className="rajiv-match-reason">
              Match reason: {hospital.match_reason}
            </li>
          )}
        </ul>
      </div>

      <div className="rajiv-aarogyasri-card">
        <h4>C. Package Comparison</h4>
        {comparisons.length === 0 ? (
          <p className="rajiv-fallback-note">
            No bill line items available for package comparison.
          </p>
        ) : (
          <div className="rajiv-comparison-grid">
            {comparisons.map((item, index) => (
              <article
                key={`${item.bill_item_name || "item"}-${index}`}
                className="rajiv-comparison-item"
              >
                <div className="rajiv-section-heading">
                  <strong>{item.bill_item_name || "—"}</strong>
                  <span className={statusBadgeClass(item.status)}>
                    {item.status || "—"}
                  </span>
                </div>
                <div className="rajiv-comparison-metrics">
                  <div>
                    <p>Charged</p>
                    <strong>{formatCurrency(item.charged_amount)}</strong>
                  </div>
                  <div>
                    <p>{item.fallback_used ? "CGHS benchmark" : "Approved rate"}</p>
                    <strong>{formatCurrency(item.approved_rate)}</strong>
                  </div>
                  <div>
                    <p>Excess</p>
                    <strong>{formatCurrency(item.excess_amount)}</strong>
                  </div>
                </div>
                {item.matched_package_name && !item.fallback_used && (
                  <p className="rajiv-package-meta">
                    Matched package: {item.matched_package_name}
                    {item.matched_package_code
                      ? ` (${item.matched_package_code})`
                      : ""}
                    {item.category_or_specialty
                      ? ` · ${item.category_or_specialty}`
                      : ""}
                  </p>
                )}
                {item.fallback_used && (
                  <p className="rajiv-fallback-note">
                    EHS/JHS package not matched — CGHS shown as general benchmark
                    only.
                  </p>
                )}
                {item.source_file && (
                  <p className="rajiv-package-meta">
                    Source: {item.source_file}
                    {item.source_sheet ? ` · ${item.source_sheet}` : ""}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </div>

      {advisories.length > 0 && (
        <div className="rajiv-aarogyasri-card">
          <h4>D. Advisories</h4>
          <ul className="rajiv-advisory-list">
            {advisories.map((message, index) => (
              <li key={`${message}-${index}`}>{message}</li>
            ))}
          </ul>
        </div>
      )}

      {report.disclaimer && (
        <p className="rajiv-disclaimer">
          <strong>E. Disclaimer:</strong> {report.disclaimer}
        </p>
      )}
    </section>
  );
}
