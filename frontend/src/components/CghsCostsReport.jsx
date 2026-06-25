import { formatCurrency } from "../billUtils";

function cardBadgeClass(row) {
  if (row?.generic_pharmacy) {
    return "rajiv-status-badge rajiv-status-info";
  }
  if (row?.fallback_used) {
    return "rajiv-status-badge rajiv-status-info";
  }
  if (row?.selected_rate != null && row?.extraction_method !== "tier_cghs") {
    return "rajiv-status-badge rajiv-status-success";
  }
  if (row?.status?.includes("Manual")) {
    return "rajiv-status-badge rajiv-status-muted";
  }
  if (row?.status?.includes("Excess")) {
    return "rajiv-status-badge rajiv-status-warning";
  }
  if (row?.status?.includes("Within")) {
    return "rajiv-status-badge rajiv-status-success";
  }
  return "rajiv-status-badge rajiv-status-muted";
}

function cardBadgeLabel(row) {
  if (row?.generic_pharmacy) {
    return "Verify Medicine Pricing";
  }
  if (row?.fallback_used) {
    return "Existing CGHS Fallback Used";
  }
  if (row?.selected_rate != null && row?.extraction_method !== "tier_cghs") {
    return "City-wise CGHS Match";
  }
  if (row?.status === "Manual Verification Required") {
    return "Manual Verification Required";
  }
  return row?.status || "No Data";
}

function formatRateType(value) {
  if (!value) {
    return null;
  }
  const mapping = {
    nabh: "NABH",
    non_nabh: "Non-NABH",
    cghs: "CGHS Rate",
  };
  return mapping[String(value).toLowerCase()] || value;
}

function confidenceLabel(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

export default function CghsCostsReport({ report }) {
  if (!report?.enabled) {
    return null;
  }

  const comparisons = report.comparisons || [];
  const advisories = report.advisories || [];
  const debugItems = report.match_debug || [];
  const dataSourceDisplay =
    report.data_source_display || "CGHS city-wise costs data";

  return (
    <section
      className="rajiv-aarogyasri-report cghs-costs-report"
      aria-label="CGHS city-wise cost verification"
    >
      <div className="rajiv-aarogyasri-header">
        <h3>CGHS City-wise Cost Comparison</h3>
        <span className="rajiv-aarogyasri-badge">CGHS city costs</span>
      </div>

      <div className="rajiv-aarogyasri-card">
        <div className="rajiv-section-heading">
          <h4>City &amp; Data Coverage</h4>
          {report.limited_city_data && (
            <span className="rajiv-status-badge rajiv-status-warning">
              Limited City Data
            </span>
          )}
        </div>
        <ul className="rajiv-meta-list">
          <li>
            City searched: <strong>{report.city_used || "—"}</strong>
          </li>
          <li>
            Clean city rows available:{" "}
            <strong>{report.city_rows_count ?? "—"}</strong>
          </li>
          <li>
            City data searched:{" "}
            <strong>{report.city_data_available ? "Yes" : "No"}</strong>
          </li>
          <li>
            Data source: <strong>{dataSourceDisplay}</strong>
          </li>
        </ul>
      </div>

      {comparisons.length > 0 && (
        <div className="rajiv-aarogyasri-card">
          <h4>Line Item Comparisons</h4>
          <div className="rajiv-comparison-grid">
            {comparisons.map((row, index) => {
              const rateType =
                row.rate_type_display ||
                formatRateType(row.rate_type_used);
              const sourceDisplay =
                row.source_display || row.source_label || "—";

              return (
                <article
                  key={`${row.bill_item_name || "item"}-${index}`}
                  className="rajiv-comparison-card"
                >
                  <div className="rajiv-section-heading">
                    <h5>{row.bill_item_name || "—"}</h5>
                    <span className={cardBadgeClass(row)}>
                      {cardBadgeLabel(row)}
                    </span>
                  </div>
                  <div className="result-metrics">
                    <div>
                      <p>Charged</p>
                      <h5>{formatCurrency(row.charged_amount)}</h5>
                    </div>
                    <div>
                      <p>CGHS Rate</p>
                      <h5>{formatCurrency(row.selected_rate)}</h5>
                    </div>
                    <div>
                      <p>Excess</p>
                      <h5>{formatCurrency(row.excess_amount)}</h5>
                    </div>
                  </div>
                  {row.matched_procedure_name && (
                    <p className="matched-reference">
                      Matched: {row.matched_procedure_name}
                      {row.match_reason ? ` · ${row.match_reason}` : ""}
                      {row.confidence_score != null
                        ? ` · ${confidenceLabel(row.confidence_score)} confidence`
                        : ""}
                    </p>
                  )}
                  <ul className="rajiv-meta-list cghs-source-meta">
                    {rateType && (
                      <li>
                        Rate type: <strong>{rateType}</strong>
                      </li>
                    )}
                    <li>
                      Source: <strong>{sourceDisplay}</strong>
                    </li>
                    {row.source_city && (
                      <li>
                        City: <strong>{row.source_city}</strong>
                      </li>
                    )}
                    {row.source_page && (
                      <li>
                        Page: <strong>{row.source_page}</strong>
                      </li>
                    )}
                  </ul>
                  {row.detail_text && (
                    <p className="rate-breakdown">{row.detail_text}</p>
                  )}
                  {row.source_file_internal && (
                    <details className="cghs-source-details">
                      <summary>View source details</summary>
                      <p className="rate-breakdown">
                        Original source PDF: {row.source_file_internal}
                      </p>
                    </details>
                  )}
                </article>
              );
            })}
          </div>
        </div>
      )}

      {advisories.length > 0 && (
        <div className="rajiv-aarogyasri-card">
          <h4>Advisories</h4>
          <ul className="rajiv-advisory-list">
            {advisories.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        </div>
      )}

      {import.meta.env.DEV && debugItems.length > 0 && (
        <div className="rajiv-aarogyasri-card">
          <h4>Match Debug (dev only)</h4>
          <ul className="rajiv-meta-list">
            {debugItems.map((entry) => (
              <li key={entry.bill_item_name}>
                <strong>{entry.bill_item_name}</strong>: city=
                {entry.normalized_city || "—"}, rows={entry.city_rows_count}, terms=
                {(entry.searched_terms || []).join(" | ") || "—"}
                {entry.fallback_reason ? ` · ${entry.fallback_reason}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
