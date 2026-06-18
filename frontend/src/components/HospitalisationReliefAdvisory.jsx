export default function HospitalisationReliefAdvisory({ advisory }) {
  if (!advisory) {
    return null;
  }

  const benefit = advisory.benefit || {};

  return (
    <section
      className="hrs-advisory"
      aria-label="Hospitalisation Relief Scheme advisory"
    >
      <div className="hrs-advisory-header">
        <h3>{advisory.title || "Hospitalisation Relief Scheme Advisory"}</h3>
        <span className="hrs-advisory-badge">Advisory</span>
      </div>

      <div className="hrs-advisory-card">
        <h4>Eligibility Summary</h4>
        <ul>
          {(advisory.eligibility_summary || []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>

      <div className="hrs-advisory-card">
        <h4>Benefit</h4>
        <ul>
          {benefit.daily_relief && <li>{benefit.daily_relief}</li>}
          {benefit.monthly_maximum && <li>{benefit.monthly_maximum}</li>}
        </ul>
      </div>

      <div className="hrs-advisory-card hrs-advisory-status">
        <h4>Applicant Status</h4>
        <p>{advisory.applicant_status}</p>
      </div>

      <div className="hrs-advisory-card">
        <h4>How to Apply</h4>
        <ol>
          {(advisory.how_to_apply || []).map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </div>

      <div className="hrs-advisory-card">
        <h4>Documents Required</h4>
        <ul>
          {(advisory.documents_required || []).map((doc) => (
            <li key={doc}>{doc}</li>
          ))}
        </ul>
      </div>

      <p className="hrs-advisory-note">{advisory.important_note}</p>
    </section>
  );
}
