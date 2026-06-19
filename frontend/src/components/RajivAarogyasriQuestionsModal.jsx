import { useEffect, useState } from "react";
import SchemeYesNoQuestion from "./SchemeYesNoQuestion";

export const RAJIV_AAROGYASRI_QUESTIONS = [
  {
    field: "rajivIsTelanganaResident",
    id: "rajiv-telangana-resident",
    name: "rajivIsTelanganaResident",
    label: "Is the patient a resident of Telangana?",
  },
  {
    field: "rajivHasEligibleCard",
    id: "rajiv-eligible-card",
    name: "rajivHasEligibleCard",
    label:
      "Does the patient have Aarogyasri / eligible ration card / scheme eligibility?",
  },
  {
    field: "rajivHasAadhaar",
    id: "rajiv-aadhaar",
    name: "rajivHasAadhaar",
    label: "Does the patient have Aadhaar?",
  },
  {
    field: "rajivIsCancerRelated",
    id: "rajiv-cancer-related",
    name: "rajivIsCancerRelated",
    label: "Is the treatment cancer-related?",
  },
];

export function emptyRajivAarogyasriAnswers() {
  return {
    rajivIsTelanganaResident: false,
    rajivHasEligibleCard: false,
    rajivHasAadhaar: false,
    rajivIsCancerRelated: false,
    rajivFamilyCoverageUsedAmount: "",
  };
}

export default function RajivAarogyasriQuestionsModal({
  open,
  onClose,
  onSave,
  initialValues = emptyRajivAarogyasriAnswers(),
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

  const handleSave = () => {
    onSave(draft);
  };

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="rajiv-aarogyasri-questions-title"
      onClick={onClose}
    >
      <div
        className="modal-panel eligibility-modal rajiv-aarogyasri-questions-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <h2 id="rajiv-aarogyasri-questions-title">
            Rajiv Aarogyasri / Aarogyasri Cheyutha
          </h2>
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
            for Rajiv Aarogyasri eligibility preview and package-rate comparison
            on the bill report.
          </p>
          <div className="rajiv-aarogyasri-questions-list">
            {RAJIV_AAROGYASRI_QUESTIONS.map((question) => (
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
                Do you know the family&apos;s already-used annual Aarogyasri
                coverage amount?{" "}
                <span className="scheme-question-optional">(optional)</span>
              </span>
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="Amount in ₹"
                value={draft.rajivFamilyCoverageUsedAmount}
                onChange={(event) =>
                  setDraft((prev) => ({
                    ...prev,
                    rajivFamilyCoverageUsedAmount: event.target.value,
                  }))
                }
              />
            </label>
          </div>
        </div>
        <footer className="modal-footer rajiv-aarogyasri-questions-footer">
          <button type="button" className="bill-editor-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="analyze-btn" onClick={handleSave}>
            Save answers
          </button>
        </footer>
      </div>
    </div>
  );
}
