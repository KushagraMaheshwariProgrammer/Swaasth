import { useEffect, useState } from "react";
import {
  CGHS_BENEFICIARY_CATEGORIES,
  buildCghsEligibilityPreview,
} from "../data/cghsEligibilityCriteria";

export function emptyCghsEligibilityAnswers() {
  return {
    cghsBeneficiaryCategory: "",
    cghsResidesInCoveredCity: null,
  };
}

export default function CghsEligibilityQuestionsModal({
  open,
  onClose,
  onSave,
  initialValues = emptyCghsEligibilityAnswers(),
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

  const previewMessages = buildCghsEligibilityPreview({
    beneficiaryCategory: draft.cghsBeneficiaryCategory || null,
    residesInCoveredCity: draft.cghsResidesInCoveredCity,
  });

  const handleSave = () => {
    onSave(draft);
  };

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cghs-eligibility-questions-title"
      onClick={onClose}
    >
      <div
        className="modal-panel eligibility-modal cghs-eligibility-questions-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <h2 id="cghs-eligibility-questions-title">CGHS Eligibility Preview</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>
        <div className="modal-body cghs-eligibility-questions-body">
          <p className="cghs-eligibility-questions-intro">
            Optional self-check for advisory preview only. This does not affect
            bill comparison or confirm eligibility.
          </p>

          <label className="scheme-card-followup scheme-card-followup-compact">
            <span className="scheme-card-followup-question">
              Does the patient belong to any CGHS eligible beneficiary category?
            </span>
            <select
              value={draft.cghsBeneficiaryCategory}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  cghsBeneficiaryCategory: event.target.value,
                }))
              }
            >
              <option value="">Select category (optional)</option>
              {CGHS_BENEFICIARY_CATEGORIES.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <fieldset className="scheme-card-followup scheme-card-followup-compact">
            <legend className="scheme-card-followup-question">
              Does the patient reside in a CGHS-covered city?
            </legend>
            <div className="scheme-card-choice-group">
              {[
                { value: true, label: "Yes" },
                { value: false, label: "No" },
                { value: null, label: "Not sure" },
              ].map((option) => (
                <label key={String(option.value)} className="scheme-card-choice">
                  <input
                    type="radio"
                    name="cghsResidesInCoveredCity"
                    checked={draft.cghsResidesInCoveredCity === option.value}
                    onChange={() =>
                      setDraft((prev) => ({
                        ...prev,
                        cghsResidesInCoveredCity: option.value,
                      }))
                    }
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {previewMessages.length > 0 && (
            <div className="cghs-eligibility-preview-box">
              <h3>Advisory preview</h3>
              {previewMessages.map((message) => (
                <p key={message}>{message}</p>
              ))}
            </div>
          )}
        </div>
        <footer className="modal-footer cghs-eligibility-questions-footer">
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
