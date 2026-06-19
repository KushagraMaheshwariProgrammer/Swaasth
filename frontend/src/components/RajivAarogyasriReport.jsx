import { formatCurrency } from "../billUtils";

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
  if (text.includes("active")) {
    return "rajiv-status-badge rajiv-status-success";
  }
  return "rajiv-status-badge";
}

export default function RajivAarogyasriReport({ report }) {
  if (!report?.selected) {
    return null;
  }

  const eligibility = report.eligibility_snapshot || {};
  const hospital = report.hospital_verification || {};
  const comparisons = report.package_comparisons || [];
  const advisories = report.advisories || [];

  return (
    <section
      className="rajiv-aarogyasri-report"
      aria-label="Rajiv Aarogyasri / Aarogyasri Cheyutha report"
    >
      <div className="rajiv-aarogyasri-header">
        <h3>Rajiv Aarogyasri / Aarogyasri Cheyutha</h3>
        <span className="rajiv-aarogyasri-badge">Package Rate Comparison</span>
      </div>

      <div className="rajiv-aarogyasri-card">
        <h4>Scheme Status</h4>
        <ul className="rajiv-meta-list">
          <li>Telangana resident: {yesNo(eligibility.telangana_resident)}</li>
          <li>
            Eligible card/scheme eligibility: {yesNo(eligibility.has_eligible_card)}
          </li>
          <li>Aadhaar: {yesNo(eligibility.has_aadhaar)}</li>
          <li>
            Cancer-related treatment: {yesNo(eligibility.cancer_related)}
          </li>
          {eligibility.family_coverage_used_amount != null && (
            <li>
              Family used coverage amount:{" "}
              {formatCurrency(eligibility.family_coverage_used_amount)}
            </li>
          )}
        </ul>
        {(report.eligibility_preview || []).length > 0 && (
          <div className="rajiv-eligibility-preview">
            {(report.eligibility_preview || []).map((message) => (
              <p key={message}>{message}</p>
            ))}
          </div>
        )}
      </div>

      <div className="rajiv-aarogyasri-card">
        <div className="rajiv-section-heading">
          <h4>Hospital Verification</h4>
          <span className={statusBadgeClass(hospital.status)}>
            {hospital.status || "Unknown"}
          </span>
        </div>
        <ul className="rajiv-meta-list">
          <li>
            OCR hospital name: <strong>{hospital.ocr_hospital_name || "—"}</strong>
          </li>
          <li>
            Matched hospital:{" "}
            <strong>{hospital.matched_hospital_name || "—"}</strong>
          </li>
          <li>
            Match confidence:{" "}
            {hospital.confidence_score != null
              ? `${Math.round(hospital.confidence_score * 100)}%`
              : "—"}
          </li>
          <li>
            Location:{" "}
            {[hospital.city, hospital.district, hospital.state]
              .filter(Boolean)
              .join(", ") || "—"}
          </li>
          <li>Hospital type: {hospital.hospital_type || "—"}</li>
          <li>Empanelled status: {hospital.empanelled_status || "—"}</li>
          {hospital.specialities && (
            <li>Specialities: {hospital.specialities}</li>
          )}
          {hospital.match_reason && (
            <li className="rajiv-match-reason">Match reason: {hospital.match_reason}</li>
          )}
        </ul>
      </div>

      {comparisons.length > 0 && (
        <div className="rajiv-aarogyasri-card">
          <h4>Aarogyasri Package Comparison</h4>
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
                    <h5>{formatCurrency(item.charged_amount)}</h5>
                  </div>
                  <div>
                    <p>Approved rate</p>
                    <h5>{formatCurrency(item.approved_rate)}</h5>
                  </div>
                  <div>
                    <p>Excess</p>
                    <h5>{formatCurrency(item.excess_amount)}</h5>
                  </div>
                </div>
                {item.matched_package_name && (
                  <p className="rajiv-package-match">
                    Matched package: {item.matched_package_name}
                    {item.matched_package_code
                      ? ` (${item.matched_package_code})`
                      : ""}
                  </p>
                )}
                {item.specialty && (
                  <p className="rajiv-package-meta">Specialty: {item.specialty}</p>
                )}
                {item.source_file && (
                  <p className="rajiv-package-meta">Source: {item.source_file}</p>
                )}
                {item.confidence_score != null && (
                  <p className="rajiv-package-meta">
                    Confidence: {Math.round(item.confidence_score * 100)}%
                  </p>
                )}
                {item.fallback_used && (
                  <p className="rajiv-fallback-note">
                    CGHS fallback used because Aarogyasri package was not matched.
                  </p>
                )}
              </article>
            ))}
          </div>
        </div>
      )}

      {advisories.length > 0 && (
        <div className="rajiv-aarogyasri-card">
          <h4>Advisories</h4>
          <ul className="rajiv-advisory-list">
            {advisories.map((advisory) => (
              <li key={`${advisory.title}-${advisory.effective_date || "na"}`}>
                <strong>{advisory.title}</strong>
                {advisory.effective_date && (
                  <span className="rajiv-advisory-date">
                    {" "}
                    · effective {advisory.effective_date}
                  </span>
                )}
                <p>{advisory.message}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="rajiv-disclaimer">{report.disclaimer}</p>
    </section>
  );
}
