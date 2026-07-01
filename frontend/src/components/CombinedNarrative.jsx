export default function CombinedNarrative({ narrative }) {
  const summary = narrative?.summary || "";
  if (!summary) {
    return null;
  }

  return (
    <section className="audit-section combined-narrative-section">
      <h3>Plain-language summary</h3>
      <p>{summary}</p>
      {narrative.disclaimer && (
        <p className="treatment-audit-disclaimer">{narrative.disclaimer}</p>
      )}
    </section>
  );
}
