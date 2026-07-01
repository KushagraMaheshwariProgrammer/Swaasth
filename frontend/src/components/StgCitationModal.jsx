export default function StgCitationModal({ citation, flagLabel, onClose }) {
  if (!citation) {
    return null;
  }

  const source = citation.source || {};
  const reference = citation.reference || {};
  const refParts = [
    reference.condition,
    reference.section,
    reference.page_label || (reference.page ? `p. ${reference.page}` : ""),
  ].filter(Boolean);

  return (
    <div className="modal-overlay stg-citation-overlay" role="dialog" aria-modal="true">
      <div className="modal-card stg-citation-modal">
        <header className="stg-citation-header">
          <h2>Guideline excerpt</h2>
          {flagLabel && <p className="stg-citation-flag-label">{flagLabel}</p>}
          <button type="button" className="modal-close" onClick={onClose}>
            Close
          </button>
        </header>

        <section className="stg-citation-source">
          <p>
            <strong>Source:</strong> {source.display_name || source.corpus_label || "Guidelines"}
          </p>
          {source.authority && (
            <p>
              <strong>Authority:</strong> {source.authority}
            </p>
          )}
          {source.folder_hint && (
            <p className="stg-citation-folder">
              <strong>Corpus:</strong> {source.folder_hint}
            </p>
          )}
          {refParts.length > 0 && (
            <p>
              <strong>Reference:</strong> {refParts.join(" · ")}
            </p>
          )}
          {source.credibility_note && (
            <p className="treatment-audit-disclaimer">{source.credibility_note}</p>
          )}
        </section>

        <section className="stg-citation-body">
          <h3>Full paragraph used for this finding</h3>
          <blockquote className="stg-citation-text">{citation.full_text}</blockquote>
        </section>

        {(source.legal_use_examples || []).length > 0 && (
          <section className="stg-citation-examples">
            <h3>How this source is used in disputes (examples)</h3>
            <ul>
              {source.legal_use_examples.map((example) => (
                <li key={example}>{example}</li>
              ))}
            </ul>
          </section>
        )}

        <p className="treatment-audit-disclaimer stg-citation-footer">
          Reproduce and verify against the original document before filing any complaint.
          This excerpt supports a clarification question, not a final medical or legal finding.
        </p>
      </div>
    </div>
  );
}
