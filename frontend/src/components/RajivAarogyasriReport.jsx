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
  if (text.includes("active") || text.includes("matched")) {
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

export default function RajivAarogyasriReport({ report }) {
  if (!report?.selected) {
    return null;
  }

  const eligibility = report.eligibility_snapshot || {};
  const hospital = report.hospital_verification || {};
  const comparisons = report.package_comparisons || [];
  const packageSearch = report.package_search || {};
  const advisories = report.advisories || [];
  const advisoryDebug = report.advisory_debug || [];
  const showDebug = import.meta.env.DEV && advisoryDebug.length > 0;

  return (
    <section
      className="rajiv-aarogyasri-report"
      aria-label="Rajiv Aarogyasri / Aarogyasri Cheyutha verification"
    >
      <div className="rajiv-aarogyasri-header">
        <h3>Rajiv Aarogyasri / Aarogyasri Cheyutha Verification</h3>
        <span className="rajiv-aarogyasri-badge">Scheme verification</span>
      </div>

      <div className="rajiv-aarogyasri-card">
        <h4>A. Scheme Status</h4>
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
          <h4>B. Hospital Verification</h4>
          <span className={statusBadgeClass(hospital.status)}>
            {hospital.status || "Unknown"}
          </span>
        </div>
        <ul className="rajiv-meta-list">
          <li>
            OCR hospital name: <strong>{hospital.ocr_hospital_name || "—"}</strong>
          </li>
          <li>
            Matched Aarogyasri hospital:{" "}
            <strong>{hospital.matched_hospital_name || "—"}</strong>
          </li>
          <li>
            Match confidence: {confidenceLabel(hospital.confidence_score)}
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

      <div className="rajiv-aarogyasri-card">
        <div className="rajiv-section-heading">
          <h4>C. Aarogyasri Package Search / Comparison</h4>
          <span className={statusBadgeClass(packageSearch.package_match_status)}>
            {packageSearch.package_match_status || "unknown"}
          </span>
        </div>

        {(packageSearch.searched_terms || []).length > 0 && (
          <>
            <p className="rajiv-package-meta">
              <strong>Searched terms:</strong>{" "}
              {packageSearch.searched_terms.join(" · ")}
            </p>
            {(packageSearch.source_files_searched || []).length > 0 && (
              <p className="rajiv-package-meta">
                <strong>Source files:</strong>{" "}
                {packageSearch.source_files_searched.join(", ")}
              </p>
            )}
          </>
        )}

        {packageSearch.matched_package_name && (
          <p className="rajiv-package-match">
            Matched package: {packageSearch.matched_package_name}
            {packageSearch.matched_package_code
              ? ` (${packageSearch.matched_package_code})`
              : ""}
            {packageSearch.matched_search_term
              ? ` · via “${packageSearch.matched_search_term}”`
              : ""}
            {packageSearch.confidence_score != null
              ? ` · ${confidenceLabel(packageSearch.confidence_score)} confidence`
              : ""}
          </p>
        )}

        {packageSearch.not_matched_message && (
          <p className="rajiv-fallback-note">{packageSearch.not_matched_message}</p>
        )}

        {(packageSearch.closest_matches || []).length > 0 && (
          <div className="rajiv-closest-matches">
            <p className="rajiv-package-meta">
              <strong>Closest package matches:</strong>
            </p>
            <ul className="rajiv-meta-list">
              {packageSearch.closest_matches.map((match, index) => (
                <li key={`${match.package_code || match.package_name}-${index}`}>
                  {match.package_name}
                  {match.specialty ? ` · ${match.specialty}` : ""}
                  {match.approved_rate != null
                    ? ` · ${formatCurrency(match.approved_rate)}`
                    : ""}
                  {match.confidence_score != null
                    ? ` · ${confidenceLabel(match.confidence_score)}`
                    : ""}
                </li>
              ))}
            </ul>
          </div>
        )}

        {comparisons.length > 0 && (
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
                    <p>Reference rate</p>
                    <h5>{formatCurrency(item.approved_rate)}</h5>
                  </div>
                  <div>
                    <p>Excess</p>
                    <h5>{formatCurrency(item.excess_amount)}</h5>
                  </div>
                </div>
                {item.matched_package_name && !item.fallback_used && (
                  <p className="rajiv-package-match">
                    Aarogyasri package: {item.matched_package_name}
                    {item.matched_package_code
                      ? ` (${item.matched_package_code})`
                      : ""}
                  </p>
                )}
                {item.fallback_used && (
                  <p className="rajiv-fallback-note">
                    CGHS fallback benchmark only — Aarogyasri package was not matched
                    for this line item.
                  </p>
                )}
                {item.match_reason && (
                  <p className="rajiv-package-meta">{item.match_reason}</p>
                )}
              </article>
            ))}
          </div>
        )}
      </div>

      {advisories.length > 0 && (
        <div className="rajiv-aarogyasri-card">
          <h4>D. Advisories</h4>
          <div className="rajiv-advisory-grid">
            {advisories.map((advisory) => (
              <article
                key={`${advisory.title}-${advisory.effective_date || "na"}`}
                className="rajiv-advisory-card"
              >
                <div className="rajiv-section-heading">
                  <strong>{advisory.title}</strong>
                  {advisory.effective_date && (
                    <span className="rajiv-advisory-date">
                      effective {advisory.effective_date}
                    </span>
                  )}
                </div>
                <p>{advisory.message}</p>
              </article>
            ))}
          </div>
        </div>
      )}

      {showDebug && (
        <div className="rajiv-aarogyasri-card rajiv-debug-card">
          <h4>E. Advisory Debug</h4>
          <ul className="rajiv-meta-list">
            {advisoryDebug.map((rule) => (
              <li key={rule.rule_key}>
                <strong>{rule.title}</strong> ·{" "}
                {rule.triggered ? "triggered" : "not triggered"} · {rule.trigger_reason}
                {rule.input_checked ? (
                  <>
                    <br />
                    <span className="rajiv-debug-input">{rule.input_checked}</span>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="rajiv-disclaimer">{report.disclaimer}</p>
    </section>
  );
}
