export default function LegalPathwayModal({ pathway, flagLabel, onClose }) {
  if (!pathway) {
    return null;
  }

  return (
    <div className="modal-overlay legal-pathway-overlay" role="dialog" aria-modal="true">
      <div className="modal-card legal-pathway-modal">
        <header className="legal-pathway-header">
          <h2>Possible legal pathway (educational)</h2>
          {flagLabel && <p className="legal-pathway-flag-label">{flagLabel}</p>}
          <button type="button" className="modal-close" onClick={onClose}>
            Close
          </button>
        </header>

        <section className="legal-pathway-body">
          <p>
            <strong>Broader legal concept:</strong> {pathway.broader_concept}
          </p>
          <p>
            <strong>Specific complaint angle:</strong> {pathway.specific_angle}
          </p>
          <p>
            <strong>What is usually required:</strong> {pathway.what_must_be_proven}
          </p>
          <p className="legal-pathway-not-accusation">
            <em>{pathway.not_an_accusation}</em>
          </p>
        </section>

        <p className="treatment-audit-disclaimer legal-pathway-footer">
          {pathway.disclaimer ||
            "Educational summary only — not legal advice. Consult a qualified advocate before alleging medical negligence or deficiency in service."}
        </p>
      </div>
    </div>
  );
}
