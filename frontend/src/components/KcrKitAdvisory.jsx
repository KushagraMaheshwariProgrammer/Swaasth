export default function KcrKitAdvisory({ advisory }) {
  if (!advisory) {
    return null;
  }

  const statusMessages = advisory.applicant_status_messages || [
    advisory.applicant_status,
  ].filter(Boolean);
  const badgeClass =
    advisory.status_badge === "May Be Eligible"
      ? "scheme-advisory-badge scheme-advisory-badge-success"
      : "scheme-advisory-badge scheme-advisory-badge-warning";

  return (
    <section
      className="scheme-advisory"
      aria-label="KCR Kit advisory"
    >
      <div className="scheme-advisory-header">
        <h3>{advisory.title || "KCR Kit / Pregnancy Nutrition Kit Advisory"}</h3>
        <span className={badgeClass}>
          {advisory.status_badge || "Advisory"}
        </span>
      </div>

      {advisory.description && (
        <p className="scheme-advisory-description">{advisory.description}</p>
      )}

      <div className="scheme-advisory-card">
        <h4>Eligibility Summary</h4>
        <ul>
          {(advisory.eligibility_summary || []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>

      <div className="scheme-advisory-card">
        <h4>Exclusions</h4>
        <ul>
          {(advisory.exclusions || []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>

      <div className="scheme-advisory-card scheme-advisory-status">
        <h4>Applicant Status</h4>
        <ul className="scheme-advisory-status-list">
          {statusMessages.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      </div>

      <div className="scheme-advisory-card">
        <h4>Application Process</h4>
        <ol>
          {(advisory.application_process || []).map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </div>

      <div className="scheme-advisory-card">
        <h4>Documents Required</h4>
        <ul>
          {(advisory.documents_required || []).map((doc) => (
            <li key={doc}>{doc}</li>
          ))}
        </ul>
      </div>

      <p className="scheme-advisory-note">{advisory.important_note}</p>
    </section>
  );
}
