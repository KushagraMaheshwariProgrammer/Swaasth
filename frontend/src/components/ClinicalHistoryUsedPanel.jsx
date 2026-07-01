export default function ClinicalHistoryUsedPanel({ clinicalHistoryUsed, patientId = null }) {
  if (!clinicalHistoryUsed) {
    return null;
  }

  const included = clinicalHistoryUsed.included || [];
  const excluded = clinicalHistoryUsed.excluded || [];
  const hasIncluded = included.length > 0;
  const hasExcluded = excluded.length > 0;

  if (!hasIncluded && !hasExcluded) {
    return (
      <section className="clinical-history-used-panel">
        <h3>Patient history</h3>
        <p className="clinical-history-hint">
          No prior history was available for this audit.
          {patientId && (
            <>
              {" "}
              <a href={`/patients/${patientId}`}>Edit patient profile</a> to add
              medical history or legacy documents.
            </>
          )}
        </p>
      </section>
    );
  }

  return (
    <section className="clinical-history-used-panel">
      <h3>Patient history considered</h3>
      {hasIncluded && (
        <ul className="clinical-history-included-list">
          {included.map((item, index) => (
            <li key={`included-${index}`}>
              <strong>{item.label || item.name || "History item"}</strong>
              {item.relevance_reason && (
                <span className="clinical-history-reason"> — {item.relevance_reason}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {hasExcluded && (
        <div className="clinical-history-excluded">
          <h4>Not relevant to this visit</h4>
          <ul>
            {excluded.map((item, index) => (
              <li key={`excluded-${index}`}>
                <strong>{item.label || item.name || "History item"}</strong>
                {item.relevance_reason && (
                  <span className="clinical-history-reason"> — {item.relevance_reason}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
