import { POSSIBLE_ISSUE_NOTICE } from "../data/hedgingCopy";

export default function AdvocacyScopeSection({ advocacyScope }) {
  const scope = advocacyScope || {};
  const checked = scope.checked || [];
  const notChecked = scope.not_checked || [];

  if (!checked.length && !notChecked.length) {
    return null;
  }

  return (
    <section className="audit-section advocacy-scope-section">
      <h3>What we checked</h3>
      {checked.length > 0 && (
        <div>
          <p className="clinical-alignment-label">Checked</p>
          <ul className="clinical-alignment-list">
            {checked.map((item, index) => (
              <li key={`checked-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {notChecked.length > 0 && (
        <div>
          <p className="clinical-alignment-label">Not checked</p>
          <ul className="clinical-alignment-list">
            {notChecked.map((item, index) => (
              <li key={`not-checked-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="treatment-audit-disclaimer">
        {POSSIBLE_ISSUE_NOTICE} Swaasth does not make final medical, legal, or
        regulatory findings against any hospital or doctor. Use these questions to
        seek clarification.
      </p>
    </section>
  );
}
