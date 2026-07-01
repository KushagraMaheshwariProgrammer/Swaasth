import { formatCurrency } from "../billUtils";

export default function RecoverableSummary({ recoverableEstimate }) {
  const estimate = recoverableEstimate || {};
  const basis = estimate.basis || [];
  const total = Number(estimate.total || 0);

  if (!total && !basis.length) {
    return null;
  }

  return (
    <section className="audit-section action-recoverable-section">
      <h3>Potentially recoverable amount</h3>
      <p className="action-recoverable-total">{formatCurrency(total)}</p>
      <div className="action-recoverable-breakdown">
        <p>
          Above NPPA reference: {formatCurrency(estimate.overpriced_total || 0)}
        </p>
        <p>
          Jan Aushadhi savings potential:{" "}
          {formatCurrency(estimate.jan_aushadhi_savings || 0)}
        </p>
      </div>
      {basis.length > 0 && (
        <ul className="clinical-alignment-list">
          {basis.map((entry, index) => (
            <li key={`basis-${index}`}>
              {entry.item}: {formatCurrency(entry.amount)} ({entry.source})
            </li>
          ))}
        </ul>
      )}
      <p className="treatment-audit-disclaimer">{estimate.disclaimer}</p>
    </section>
  );
}
