import { useEffect, useState } from "react";
import YesNoNotSureSelector from "./YesNoNotSureSelector";

export function emptyPmjayAnswers() {
  return {
    pmjayHasAyushmanCard: null,
  };
}

export default function PmjayQuestionsModal({
  open,
  onClose,
  onSave,
  initialValues = emptyPmjayAnswers(),
}) {
  const [draft, setDraft] = useState(initialValues);

  useEffect(() => {
    if (open) {
      setDraft(initialValues);
    }
  }, [open, initialValues]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="pmjay-questions-title"
      onClick={onClose}
    >
      <div
        className="modal-panel eligibility-modal pmjay-questions-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <h2 id="pmjay-questions-title">Ayushman Bharat / PM-JAY</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>
        <div className="modal-body pmjay-questions-body">
          <p className="pmjay-questions-intro">
            Optional self-check for advisory preview only. Patient state is taken
            from the registration form; bill location is used during comparison.
          </p>

          <YesNoNotSureSelector
            id="pmjay-card-question"
            label="Does the patient have an Ayushman Bharat / PM-JAY card?"
            name="pmjayHasAyushmanCard"
            value={draft.pmjayHasAyushmanCard}
            onChange={(nextValue) =>
              setDraft((prev) => ({
                ...prev,
                pmjayHasAyushmanCard: nextValue,
              }))
            }
          />
        </div>
        <footer className="modal-footer pmjay-questions-footer">
          <button type="button" className="bill-editor-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="analyze-btn"
            onClick={() => onSave(draft)}
          >
            Save answers
          </button>
        </footer>
      </div>
    </div>
  );
}
