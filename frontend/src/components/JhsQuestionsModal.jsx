import { useEffect, useState } from "react";
import SchemeYesNoQuestion from "./SchemeYesNoQuestion";

export const JHS_QUESTIONS = [
  {
    field: "jhsIsWorkingJournalist",
    id: "jhs-working-journalist",
    name: "jhsIsWorkingJournalist",
    label: "Is the patient a working journalist?",
  },
  {
    field: "jhsIsRetiredJournalist",
    id: "jhs-retired-journalist",
    name: "jhsIsRetiredJournalist",
    label: "Is the patient a retired journalist?",
  },
  {
    field: "jhsIsDependent",
    id: "jhs-dependent",
    name: "jhsIsDependent",
    label:
      "Is the patient a dependent family member of an eligible journalist?",
  },
  {
    field: "jhsHasHealthCard",
    id: "jhs-health-card",
    name: "jhsHasHealthCard",
    label: "Does the patient have a JHS health card?",
  },
  {
    field: "jhsHasAadhaar",
    id: "jhs-aadhaar",
    name: "jhsHasAadhaar",
    label: "Does the patient have Aadhaar?",
  },
];

export function emptyJhsAnswers() {
  return {
    jhsIsWorkingJournalist: false,
    jhsIsRetiredJournalist: false,
    jhsIsDependent: false,
    jhsHasHealthCard: false,
    jhsHasAadhaar: false,
    jhsCardNumber: "",
  };
}

export default function JhsQuestionsModal({
  open,
  onClose,
  onSave,
  initialValues = emptyJhsAnswers(),
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
      aria-labelledby="jhs-questions-title"
      onClick={onClose}
    >
      <div
        className="modal-panel eligibility-modal rajiv-aarogyasri-questions-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <h2 id="jhs-questions-title">Journalists Health Scheme (JHS)</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>
        <div className="modal-body rajiv-aarogyasri-questions-body">
          <p className="rajiv-aarogyasri-questions-intro">
            Answer the questions below for this patient. These details are used
            for JHS eligibility preview and package-rate comparison on the bill
            report.
          </p>
          <div className="rajiv-aarogyasri-questions-list">
            {JHS_QUESTIONS.map((question) => (
              <SchemeYesNoQuestion
                key={question.field}
                id={question.id}
                name={question.name}
                question={question.label}
                value={draft[question.field]}
                onChange={(nextValue) =>
                  setDraft((prev) => ({
                    ...prev,
                    [question.field]: nextValue,
                  }))
                }
              />
            ))}
            <label className="scheme-card-followup scheme-card-followup-compact">
              <span className="scheme-card-followup-question">
                JHS card number{" "}
                <span className="scheme-question-optional">(optional)</span>
              </span>
              <input
                type="text"
                value={draft.jhsCardNumber || ""}
                onChange={(event) =>
                  setDraft((prev) => ({
                    ...prev,
                    jhsCardNumber: event.target.value,
                  }))
                }
                placeholder="Enter JHS card number if available"
              />
            </label>
          </div>
        </div>
        <footer className="modal-footer rajiv-aarogyasri-questions-footer">
          <button type="button" className="secondary-btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="primary-btn"
            onClick={() => onSave(draft)}
          >
            Save answers
          </button>
        </footer>
      </div>
    </div>
  );
}
