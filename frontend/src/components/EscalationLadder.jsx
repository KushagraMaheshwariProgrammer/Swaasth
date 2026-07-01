export default function EscalationLadder({ escalationLadder }) {
  const steps = escalationLadder || [];
  if (!steps.length) {
    return null;
  }

  return (
    <section className="audit-section escalation-ladder-section">
      <h3>Escalation ladder</h3>
      <p className="treatment-audit-disclaimer">
        Procedural steps only — not a guarantee of outcome. Verify timelines with
        the relevant authority.
      </p>
      <ol className="escalation-steps">
        {steps.map((step) => (
          <li key={`step-${step.step}`} className="escalation-step-card">
            <p className="escalation-step-title">
              {step.step}. {step.title}
            </p>
            <p>
              <strong>When:</strong> {step.when}
            </p>
            <p>
              <strong>Typical timeline:</strong> {step.typical_timeline}
            </p>
            {step.what_to_attach?.length > 0 && (
              <div>
                <p className="clinical-alignment-label">What to attach</p>
                <ul className="clinical-alignment-list">
                  {step.what_to_attach.map((doc, index) => (
                    <li key={`attach-${step.step}-${index}`}>{doc}</li>
                  ))}
                </ul>
              </div>
            )}
            {step.disclaimer && (
              <p className="escalation-step-disclaimer">{step.disclaimer}</p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
