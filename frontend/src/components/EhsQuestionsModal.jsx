import { useEffect, useState } from "react";
import SchemeYesNoQuestion from "./SchemeYesNoQuestion";

export const EHS_QUESTIONS = [
  {
    field: "ehsIsGovernmentEmployee",
    id: "ehs-government-employee",
    name: "ehsIsGovernmentEmployee",
    label: "Is the patient a Telangana government employee?",
  },
  {
    field: "ehsIsPensioner",
    id: "ehs-pensioner",
    name: "ehsIsPensioner",
    label: "Is the patient a pensioner?",
  },
  {
    field: "ehsIsDependent",
    id: "ehs-dependent",
    name: "ehsIsDependent",
    label:
      "Is the patient a dependent family member of an eligible employee/pensioner?",
  },
  {
    field: "ehsHasHealthCard",
    id: "ehs-health-card",
    name: "ehsHasHealthCard",
    label: "Does the patient have an EHS health card?",
  },
];

export function emptyEhsAnswers() {
  return {
    ehsIsGovernmentEmployee: false,
    ehsIsPensioner: false,
    ehsIsDependent: false,
    ehsHasHealthCard: false,
    ehsCardNumber: "",
  };
}

export default function EhsQuestionsModal({
  open,
  onClose,
  onSave,
  initialValues = emptyEhsAnswers(),
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
      aria-labelledby="ehs-questions-title"
      onClick={onClose}
    >
      <div
        className="modal-panel eligibility-modal rajiv-aarogyasri-questions-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <h2 id="ehs-questions-title">Employees Health Scheme (EHS)</h2>
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
            for EHS eligibility preview and package-rate comparison on the bill
            report.
          </p>
          <div className="rajiv-aarogyasri-questions-list">
            {EHS_QUESTIONS.map((question) => (
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
                EHS card number{" "}
                <span className="scheme-question-optional">(optional)</span>
              </span>
              <input
                type="text"
                value={draft.ehsCardNumber || ""}
                onChange={(event) =>
                  setDraft((prev) => ({
                    ...prev,
                    ehsCardNumber: event.target.value,
                  }))
                }
                placeholder="Enter EHS card number if available"
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
