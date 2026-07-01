const STATUS_META = {
  hold: {
    label: "Hold payment on flagged items",
    className: "discharge-banner discharge-hold",
  },
  caution: {
    label: "Proceed with caution",
    className: "discharge-banner discharge-caution",
  },
  pay_ok: {
    label: "No high-priority billing holds",
    className: "discharge-banner discharge-ok",
  },
};

export default function DischargeGuidance({ dischargeGuidance }) {
  const guidance = dischargeGuidance || {};
  const status = guidance.status || "pay_ok";
  const meta = STATUS_META[status] || STATUS_META.pay_ok;
  const reasons = guidance.reasons || [];

  return (
    <section className={`audit-section ${meta.className}`}>
      <h3>Before you pay or discharge</h3>
      <p className="discharge-status-label">{meta.label}</p>
      {reasons.length > 0 && (
        <ul className="clinical-alignment-list">
          {reasons.map((reason, index) => (
            <li key={`reason-${index}`}>{reason}</li>
          ))}
        </ul>
      )}
      {guidance.emergency_note && (
        <p className="discharge-emergency-note">{guidance.emergency_note}</p>
      )}
    </section>
  );
}
