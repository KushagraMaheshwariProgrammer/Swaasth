import { useEffect, useState } from "react";
import SchemeYesNoQuestion from "./SchemeYesNoQuestion";

export const KCR_KIT_QUESTIONS = [
  {
    field: "kcrIsPregnant",
    id: "kcr-pregnant",
    name: "kcrIsPregnant",
    label: "Is the patient pregnant?",
  },
  {
    field: "kcrIsTelanganaResident",
    id: "kcr-telangana-resident",
    name: "kcrIsTelanganaResident",
    label: "Is the patient a resident of Telangana?",
  },
  {
    field: "kcrIncomeBelow10000",
    id: "kcr-income",
    name: "kcrIncomeBelow10000",
    label: "Is the family monthly income below ₹10,000?",
  },
  {
    field: "kcrGovernmentHospitalTreatment",
    id: "kcr-government-hospital",
    name: "kcrGovernmentHospitalTreatment",
    label: "Is the patient receiving treatment from a government hospital?",
  },
  {
    field: "kcrMoreThanTwoLiveChildren",
    id: "kcr-children",
    name: "kcrMoreThanTwoLiveChildren",
    label: "Does the patient have more than two live children?",
  },
  {
    field: "kcrAadhaarTelangana",
    id: "kcr-aadhaar",
    name: "kcrAadhaarTelangana",
    label: "Does the patient’s Aadhaar belong to Telangana?",
  },
  {
    field: "kcrIdentifiedByAnganwadiWorker",
    id: "kcr-anganwadi",
    name: "kcrIdentifiedByAnganwadiWorker",
    label: "Was the patient identified/referred by an Anganwadi Worker?",
    optional: true,
  },
];

export function emptyKcrKitAnswers() {
  return {
    kcrIsPregnant: false,
    kcrIsTelanganaResident: false,
    kcrIncomeBelow10000: false,
    kcrGovernmentHospitalTreatment: false,
    kcrMoreThanTwoLiveChildren: false,
    kcrAadhaarTelangana: false,
    kcrIdentifiedByAnganwadiWorker: false,
  };
}

export default function KcrKitQuestionsModal({
  open,
  onClose,
  onSave,
  initialValues = emptyKcrKitAnswers(),
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
      aria-labelledby="kcr-kit-questions-title"
      onClick={onClose}
    >
      <div
        className="modal-panel eligibility-modal kcr-kit-questions-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <h2 id="kcr-kit-questions-title">
            KCR Kit / Pregnancy Nutrition Kit
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
        <div className="modal-body kcr-kit-questions-body">
          <p className="kcr-kit-questions-intro">
            Answer the questions below for this patient. These details are used
            in the KCR Kit advisory on the bill report.
          </p>
          <div className="kcr-kit-questions-list">
            {KCR_KIT_QUESTIONS.map((question) => (
              <SchemeYesNoQuestion
                key={question.field}
                id={question.id}
                name={question.name}
                question={question.label}
                optional={question.optional}
                value={draft[question.field]}
                onChange={(nextValue) =>
                  setDraft((prev) => ({
                    ...prev,
                    [question.field]: nextValue,
                  }))
                }
              />
            ))}
          </div>
        </div>
        <footer className="modal-footer kcr-kit-questions-footer">
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
