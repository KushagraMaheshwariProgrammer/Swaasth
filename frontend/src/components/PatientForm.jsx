import { useState } from "react";
import EligibilityCriteriaModal from "./EligibilityCriteriaModal";

export const GENDER_OPTIONS = [
  { id: "male", label: "Male" },
  { id: "female", label: "Female" },
  { id: "other", label: "Other" },
  { id: "prefer_not_to_say", label: "Prefer not to say" },
];

export const emptyPatientForm = () => ({
  name: "",
  age: "",
  gender: "",
  ayushmanEligible: false,
  savePastBills: false,
});

export function genderLabel(gender) {
  return (
    GENDER_OPTIONS.find((option) => option.id === gender)?.label || gender || "—"
  );
}

export default function PatientForm({
  form,
  setForm,
  onSubmit,
  onCancel,
  submitLabel,
  saving,
  error,
  info,
  isCreate = false,
}) {
  const [showEligibility, setShowEligibility] = useState(false);

  return (
    <form className="patient-form" onSubmit={onSubmit}>
      <label className="setting-field setting-field-full">
        <span>Patient name</span>
        <input
          type="text"
          value={form.name}
          required
          placeholder="Full name"
          onChange={(event) =>
            setForm((prev) => ({ ...prev, name: event.target.value }))
          }
        />
      </label>
      <div className="comparison-settings-grid">
        <label className="setting-field">
          <span>Age</span>
          <input
            type="number"
            min="0"
            max="150"
            required
            value={form.age}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, age: event.target.value }))
            }
          />
        </label>
        <label className="setting-field">
          <span>Gender</span>
          <select
            required
            value={form.gender}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, gender: event.target.value }))
            }
          >
            <option value="">Select gender</option>
            {GENDER_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="patient-checkbox">
        <input
          type="checkbox"
          checked={form.ayushmanEligible}
          onChange={(event) =>
            setForm((prev) => ({
              ...prev,
              ayushmanEligible: event.target.checked,
            }))
          }
        />
        <span>Patient is eligible for Ayushman Bharat scheme</span>
      </label>
      {isCreate && (
        <label className="patient-checkbox">
          <input
            type="checkbox"
            checked={form.savePastBills}
            onChange={(event) =>
              setForm((prev) => ({
                ...prev,
                savePastBills: event.target.checked,
              }))
            }
          />
          <span>
            Allow Swaasth to save this patient&apos;s past bills so they can be
            viewed later.
          </span>
        </label>
      )}
      <button
        type="button"
        className="eligibility-learn-btn"
        onClick={() => setShowEligibility(true)}
      >
        Learn eligibility criteria
      </button>
      <EligibilityCriteriaModal
        open={showEligibility}
        onClose={() => setShowEligibility(false)}
      />
      {info && <p className="auth-info">{info}</p>}
      {error && <p className="error-text">{error}</p>}
      <div className="patient-form-actions">
        {onCancel && (
          <button
            type="button"
            className="bill-editor-secondary"
            onClick={onCancel}
            disabled={saving}
          >
            Cancel
          </button>
        )}
        <button type="submit" className="analyze-btn" disabled={saving}>
          {saving ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
